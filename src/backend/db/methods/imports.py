import pandas as pd
import streamlit as st

from src.backend.db.core import format_db_response, init_connection
from src.backend.utils.logging import logger

conn = init_connection()


def import_source_concepts(
    csv_path: str,
    vocabulary_id: int,
):
    df = pd.read_csv(csv_path)

    # Ensure required columns exist
    required_columns = ["source_value", "source_concept_name"]
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    # Check if concept_id column exists for existing mappings
    has_concept_id_column = "concept_id" in df.columns

    # Insert data in batches
    batch_size = 1000
    with conn.cursor() as cursor:
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i : i + batch_size]
            values = []
            mapping_data = []

            for _, row in batch.iterrows():
                # Parse concept_id column if it exists
                concept_ids = []

                if has_concept_id_column and pd.notna(row.get("concept_id")):
                    concept_id_str = str(row["concept_id"]).strip()
                    if concept_id_str:
                        # Handle multiple concept IDs separated by semicolons
                        for cid in concept_id_str.split(";"):
                            cid = cid.strip()
                            if cid.isdigit():
                                concept_ids.append(int(cid))

                values.append(
                    (
                        row["source_value"],
                        row["source_concept_name"],
                        vocabulary_id,
                        row.get("freq", 1),
                    )
                )
                mapping_data.append(concept_ids)

            # Insert source concepts
            cursor.executemany(
                """INSERT INTO source_concepts 
                   (source_value, source_concept_name, source_vocabulary_id, freq) 
                   VALUES (%s, %s, %s, %s) RETURNING source_id""",
                values,
            )

            # Get the inserted source_ids
            source_ids = [row[0] for row in cursor.fetchall()]

            # Insert mappings for valid concept IDs
            mapping_values = []
            if any(mapping_data):
                # Get all unique concept IDs to validate
                all_concept_ids = list(
                    set([cid for concepts in mapping_data for cid in concepts])
                )

                if all_concept_ids:
                    # Check which concept IDs exist
                    placeholders = ",".join(["%s"] * len(all_concept_ids))
                    cursor.execute(
                        f"SELECT concept_id FROM concept WHERE concept_id IN ({placeholders})",
                        all_concept_ids,
                    )
                    valid_concept_ids = {row[0] for row in cursor.fetchall()}

                    # Create mappings for valid concept IDs only
                    for idx, concept_ids in enumerate(mapping_data):
                        source_id = source_ids[idx]
                        for concept_id in concept_ids:
                            if concept_id in valid_concept_ids:
                                mapping_values.append((source_id, concept_id))

            # Insert valid mappings
            if mapping_values:
                cursor.executemany(
                    "INSERT INTO source_standard_map (source_id, concept_id) VALUES (%s, %s)",
                    mapping_values,
                )

        conn.commit()

    return len(df)


def import_vocabulary_with_copy(
    table_name: str,
    file_path: str,
):
    """Import vocabulary data using upsert logic to handle duplicates"""

    # Define temp table and conflict resolution strategies
    temp_table = f"temp_{table_name}"

    # Simple conflict column definitions - just the key columns
    conflict_configs = {
        "concept": "concept_id",
        "concept_relationship": "concept_id_1, concept_id_2, relationship_id",
        "concept_ancestor": "ancestor_concept_id, descendant_concept_id",
    }

    if table_name not in conflict_configs:
        raise ValueError(f"Unsupported table for upsert: {table_name}")

    conflict_columns = conflict_configs[table_name]

    try:
        with conn.cursor() as cursor:
            # Get count before import
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count_before = cursor.fetchone()[0]

            logger.info(
                f"Starting upsert import for {table_name} (current count: {count_before})"
            )

            # Create temporary table with same structure as main table
            cursor.execute(
                f"CREATE TEMP TABLE {temp_table} (LIKE {table_name} INCLUDING ALL)"
            )

            # Load data into temporary table using COPY
            copy_command = f"COPY {temp_table} FROM '{file_path}' WITH DELIMITER E'\\t' CSV HEADER QUOTE E'\\b'"
            cursor.execute(copy_command)

            # Get count of records in temp table
            cursor.execute(f"SELECT COUNT(*) FROM {temp_table}")
            temp_count = cursor.fetchone()[0]
            logger.info(f"Loaded {temp_count} records into temporary table")

            # Get all columns and build dynamic upsert query
            cursor.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table_name}' AND table_schema = 'public'
                ORDER BY ordinal_position
            """)
            all_columns = [row[0] for row in cursor.fetchall()]
            conflict_column_list = [col.strip() for col in conflict_columns.split(",")]
            update_columns = [
                col for col in all_columns if col not in conflict_column_list
            ]

            update_set_clause = ", ".join(
                [f"{col} = EXCLUDED.{col}" for col in update_columns]
            )
            upsert_query = f"""
                INSERT INTO {table_name} 
                SELECT * FROM {temp_table}
                ON CONFLICT ({conflict_columns}) 
                DO UPDATE SET {update_set_clause}
            """

            # Execute upsert
            cursor.execute(upsert_query)
            upserted_count = cursor.rowcount

            # Clean up temporary table
            cursor.execute(f"DROP TABLE {temp_table}")

            # Get count after import
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count_after = cursor.fetchone()[0]

            records_imported = count_after - count_before

            # Log the import
            cursor.execute(
                """
                INSERT INTO vocabulary_imports 
                (table_name, file_path, records_imported, status)
                VALUES (%s, %s, %s, %s)
            """,
                (table_name, file_path, records_imported, "completed"),
            )

            logger.info(
                f"Upserted {upserted_count} records ({records_imported} net new) into {table_name} from {file_path}"
            )
            conn.commit()

            return records_imported

    except Exception as e:
        logger.error(f"Error importing {table_name}", exc_info=True)
        conn.rollback()

        # Log the error
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO vocabulary_imports 
                    (table_name, file_path, records_imported, status, error_message)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (table_name, file_path, 0, "failed", str(e)),
                )
                conn.commit()
        except Exception:
            pass  # Don't fail if we can't log the error

        raise e


@st.cache_data(ttl=60)
def get_vocabulary_import_status():
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT 
                table_name,
                MAX(import_date) as last_import,
                SUM(records_imported) as total_records,
                COUNT(*) as import_count,
                MAX(CASE WHEN status = 'failed' THEN error_message END) as last_error
            FROM vocabulary_imports
            WHERE status = 'completed'
            GROUP BY table_name
            ORDER BY table_name
        """)

        columns = [column[0] for column in cursor.description]
        data = cursor.fetchall()

        return format_db_response(data, columns)


@st.cache_data(ttl=60)
def get_vocabulary_table_counts():
    tables = ["concept", "concept_relationship", "concept_ancestor"]
    counts = {}

    with conn.cursor() as cursor:
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cursor.fetchone()[0]

    return counts


def check_vocabulary_files_exist(vocabulary_path: str = "/app/vocabulary"):
    """Check which vocabulary files exist in the mounted directory"""
    import os

    expected_files = {
        "concept": "CONCEPT.csv",
        "concept_relationship": "CONCEPT_RELATIONSHIP.csv",
        "concept_ancestor": "CONCEPT_ANCESTOR.csv",
    }

    file_status = {}

    for table, filename in expected_files.items():
        file_path = os.path.join(vocabulary_path, filename)
        file_status[table] = {
            "filename": filename,
            "path": file_path,
            "exists": os.path.exists(file_path),
            "size": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
        }

    return file_status


def import_all_vocabulary_tables(vocabulary_path: str = "/app/vocabulary"):
    file_status = check_vocabulary_files_exist(vocabulary_path)
    results = {}

    for table, file_info in file_status.items():
        if file_info["exists"]:
            try:
                records_imported = import_vocabulary_with_copy(table, file_info["path"])
                results[table] = {
                    "status": "success",
                    "records_imported": records_imported,
                    "error": None,
                }
            except Exception as e:
                logger.error(f"Error importing {table}", exc_info=True)
                results[table] = {
                    "status": "failed",
                    "records_imported": 0,
                    "error": str(e),
                }
        else:
            results[table] = {
                "status": "skipped",
                "records_imported": 0,
                "error": f"File not found: {file_info['filename']}",
            }

    return results
