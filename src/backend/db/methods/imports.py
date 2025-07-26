from psycopg import Connection
import pandas as pd
import streamlit as st

from src.backend.db.core import format_db_response, init_connection

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

    # Insert data in batches
    batch_size = 1000
    with conn.cursor() as cursor:
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i : i + batch_size]
            values = []

            for _, row in batch.iterrows():
                values.append(
                    (
                        row["source_value"],
                        row["source_concept_name"],
                        vocabulary_id,
                        row.get("freq", 1),  # Default frequency to 1 if not provided
                        False,  # mapped = False by default
                    )
                )

            cursor.executemany(
                """INSERT INTO source_concepts 
                   (source_value, source_concept_name, source_vocabulary_id, freq, mapped) 
                   VALUES (%s, %s, %s, %s, %s)""",
                values,
            )

        conn.commit()

    return len(df)


def import_vocabulary_with_copy(
    table_name: str,
    file_path: str,
):
    # Create the COPY command using CDM VocabImport syntax
    copy_command = f"COPY {table_name} FROM '{file_path}' WITH DELIMITER E'\\t' CSV HEADER QUOTE E'\\b'"

    try:
        with conn.cursor() as cursor:
            # Get count before import
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count_before = cursor.fetchone()[0]

            # Execute the COPY command
            cursor.execute(copy_command)

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

            conn.commit()

            return records_imported

    except Exception as e:
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
                records_imported = import_vocabulary_with_copy(
                    table, file_info["path"], conn
                )
                results[table] = {
                    "status": "success",
                    "records_imported": records_imported,
                    "error": None,
                }
            except Exception as e:
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
