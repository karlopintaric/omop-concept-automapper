import os
import streamlit as st
import pandas as pd
from src.backend.db.core import (
    init_connection,
    get_db_connection,
    format_db_response,
    read_query_from_sql_file,
)

from contextlib import closing
import math
import re


def get_connection():
    """Get database connection - lazy initialization for Streamlit"""
    if not hasattr(get_connection, "_conn"):
        get_connection._conn = init_connection()
    return get_connection._conn


conn = get_connection()


def seed_database(conn=None):
    """Seed the database with initial schema"""
    if conn is None:
        # Use context manager for CLI usage
        with get_db_connection() as db_conn:
            _execute_seed_query(db_conn)
    else:
        # Direct connection passed (for Streamlit or other usage)
        _execute_seed_query(conn)


def _execute_seed_query(conn):
    """Execute the seed query"""
    module_dir = os.path.dirname(__file__)
    query_path = os.path.join(module_dir, "data", "seed.sql")
    seed_query = read_query_from_sql_file(query_path)

    with closing(conn.cursor()) as cursor:
        cursor.execute(seed_query)
        conn.commit()


def import_source_concepts(csv_path: str, vocabulary_id: int):
    df = pd.read_csv(csv_path)

    # Ensure required columns exist
    required_columns = ["source_value", "source_concept_name"]
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    # Insert data in batches
    batch_size = 1000
    with closing(conn.cursor()) as cursor:
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


@st.cache_data
def get_total_pages(vocabulary_id: int, per_page: int):
    with closing(conn.cursor()) as c:
        c.execute(
            """
            SELECT COUNT(*) 
            FROM source_concepts 
            WHERE 
                mapped = FALSE
                AND source_vocabulary_id = %s
            """,
            (vocabulary_id,),
        )

        total_items = c.fetchone()[0]

    return math.ceil(total_items / per_page)


@st.cache_data
def get_standard_domains():
    with closing(conn.cursor()) as c:
        c.execute(
            """
            SELECT DISTINCT
                domain_id 
            FROM concept
            WHERE standard_concept = 'S'
            ORDER BY
                domain_id
            """
        )

        data = c.fetchall()
        domains = [domain[0] for domain in data]

    return domains


@st.cache_data(ttl=30, max_entries=1)
def get_unmapped_source_concepts(vocabulary_id: int, page: int = 1, per_page: int = 50):
    offset = (page - 1) * per_page

    with closing(conn.cursor()) as c:
        c.execute(
            """
            SELECT
                sc.source_id,
                sc.source_value, 
                sc.source_concept_name,
                sc.source_vocabulary_id, 
                sc.freq,
                COALESCE(COUNT(ssm.concept_id), 0) AS mapped_concepts
            FROM source_concepts sc
            LEFT JOIN 
                source_standard_map ssm ON sc.source_id = ssm.source_id
            WHERE 
                sc.source_vocabulary_id = %s
                AND ssm.source_id IS NULL  -- Only unmapped concepts
            GROUP BY
                sc.source_id,
                sc.source_value, 
                sc.source_concept_name,
                sc.source_vocabulary_id, 
                sc.freq  
            ORDER BY sc.freq DESC
            LIMIT %s OFFSET %s
            """,
            (vocabulary_id, per_page, offset),
        )

        columns = [column[0] for column in c.description]
        data = c.fetchall()

        response = format_db_response(data, columns)

    return response


@st.cache_data(ttl=30)
def get_unmapped_concepts(vocabulary_id: int):
    with closing(conn.cursor()) as c:
        c.execute(
            """
            SELECT
                sc.source_id,
                sc.source_value, 
                sc.source_concept_name,
                sc.source_vocabulary_id
            FROM source_concepts sc
            LEFT JOIN 
                source_standard_map ssm ON sc.source_id = ssm.source_id
            WHERE
                ssm.source_id IS NULL  -- Only unmapped concepts
                AND sc.source_vocabulary_id = %s
            ORDER BY
                sc.freq DESC
            """,
            (vocabulary_id,),
        )

        columns = [column[0] for column in c.description]
        data = c.fetchall()

        response = format_db_response(data, columns)

    return response


@st.cache_data(ttl=30)
def get_mapped_concepts(vocabulary_id: int):
    with closing(conn.cursor()) as c:
        c.execute(
            """
            SELECT
                sc.source_id,
                sc.source_value,
                sc.source_concept_name,
                st.concept_name,
                st.concept_id,
                st.domain_id,
                sc.freq
            FROM source_concepts sc
            JOIN source_standard_map ssm ON sc.source_id = ssm.source_id
            JOIN concept st ON ssm.concept_id = st.concept_id
            WHERE sc.source_vocabulary_id = %s
            ORDER BY sc.freq DESC
            """,
            (vocabulary_id,),
        )

        columns = [column[0] for column in c.description]
        data = c.fetchall()

        response = format_db_response(data, columns)

    return response


def map_concepts(mappings: list, is_manual: bool = True):
    with closing(conn.cursor()) as cursor:
        # Get unique source IDs from mappings
        source_ids = list(set([mapping["source_id"] for mapping in mappings]))

        # Remove existing mappings for these source concepts (for remapping)
        if source_ids:
            placeholders = ",".join(["%s" for _ in source_ids])
            cursor.execute(
                f"DELETE FROM source_standard_map WHERE source_id IN ({placeholders})",
                source_ids,
            )
            cursor.execute(
                f"DELETE FROM auto_mapping_audit WHERE source_id IN ({placeholders})",
                source_ids,
            )

        # Insert new mappings
        values = [(mapping["source_id"], mapping["concept_id"]) for mapping in mappings]
        cursor.executemany(
            "INSERT INTO source_standard_map (source_id, concept_id) VALUES (%s, %s)",
            values,
        )

        # Update mapped status for source concepts
        placeholders = ",".join(["%s" for _ in source_ids])
        cursor.execute(
            f"UPDATE source_concepts SET mapped = TRUE WHERE source_id IN ({placeholders})",
            source_ids,
        )

        # Save audit trail for manual mappings
        if is_manual:
            audit_values = []
            for mapping in mappings:
                audit_values.append(
                    (
                        mapping["source_id"],
                        mapping["concept_id"],
                        None,  # No confidence score for manual mappings
                        "manual",
                        None,  # No target domains for manual mappings
                    )
                )

            cursor.executemany(
                """
                INSERT INTO auto_mapping_audit (source_id, concept_id, confidence_score, mapping_method, target_domains)
                VALUES (%s, %s, %s, %s, %s)
                """,
                audit_values,
            )

        conn.commit()


def unmap_concepts(source_ids: list):
    """Remove mappings for given source concept IDs"""
    with closing(conn.cursor()) as cursor:
        placeholders = ",".join(["%s" for _ in source_ids])

        cursor.execute(
            f"DELETE FROM source_standard_map WHERE source_id IN ({placeholders})",
            source_ids,
        )

        cursor.execute(
            f"UPDATE source_concepts SET mapped = FALSE WHERE source_id IN ({placeholders})",
            source_ids,
        )

        conn.commit()


@st.cache_data
def get_concept_from_id(concept_id: int):
    """Get concept details by concept ID"""
    with closing(conn.cursor()) as c:
        c.execute(
            """
            SELECT 
                concept_id,
                concept_name,
                concept_class_id,
                domain_id,
                vocabulary_id,
                concept_code,
                standard_concept
            FROM concept
            WHERE concept_id = %s
            """,
            (concept_id,),
        )

        columns = [column[0] for column in c.description]
        data = c.fetchall()

        response = format_db_response(data, columns)

    return response


@st.cache_data(ttl=30)
def get_embedding_status(table_type: str = "standard_concepts"):
    """Get embedding status for concepts"""
    with closing(conn.cursor()) as c:
        if table_type == "standard_concepts":
            c.execute(
                """
                SELECT 
                    COUNT(*) as total_concepts,
                    COUNT(ec.concept_id) as embedded_concepts
                FROM concept sc
                LEFT JOIN embedded_concepts ec ON sc.concept_id = ec.concept_id 
                    AND ec.concept_type = 'standard'
                WHERE sc.standard_concept = 'S'
                """
            )
        else:  # source_concepts
            c.execute(
                """
                SELECT 
                    COUNT(*) as total_concepts,
                    COUNT(ec.concept_id) as embedded_concepts
                FROM source_concepts sc
                LEFT JOIN embedded_concepts ec ON sc.source_id = ec.concept_id 
                    AND ec.concept_type = 'source'
                """
            )

        result = c.fetchone()
        return {
            "total": result[0],
            "embedded": result[1],
            "percentage": (result[1] / result[0] * 100) if result[0] > 0 else 0,
        }


def find_atc7_codes_for_drug_concepts():
    """
    Find all ATC7 codes for drug domain concepts using concept relationships and ancestors.
    This function traces through the OMOP relationships to find ATC codes.
    """

    # Query to find ATC codes through relationships and ancestors
    # Fancy recursive AI written query go brrr
    atc_query = """
        WITH RECURSIVE atc_hierarchy AS (
            -- Find direct ATC relationships
            SELECT DISTINCT 
                c1.concept_id as drug_concept_id,
                c2.concept_code as atc_code
            FROM concept c1
            JOIN concept_relationship cr ON c1.concept_id = cr.concept_id_1
            JOIN concept c2 ON cr.concept_id_2 = c2.concept_id
            WHERE c1.domain_id = 'Drug' 
            AND c1.standard_concept = 'S'
            AND c2.vocabulary_id = 'ATC'
            AND cr.relationship_id IN ('Maps to', 'RxNorm has ing', 'Mapped from')
            AND cr.invalid_reason IS NULL
            
            UNION
            
            -- Find ATC codes through concept_ancestor table
            SELECT DISTINCT 
                c1.concept_id as drug_concept_id,
                c2.concept_code as atc_code
            FROM concept c1
            JOIN concept_ancestor ca ON c1.concept_id = ca.descendant_concept_id
            JOIN concept c2 ON ca.ancestor_concept_id = c2.concept_id
            WHERE c1.domain_id = 'Drug' 
            AND c1.standard_concept = 'S'
            AND c2.vocabulary_id = 'ATC'
            AND LENGTH(c2.concept_code) = 7
        )
        SELECT 
            drug_concept_id,
            ARRAY_AGG(DISTINCT atc_code) as atc7_codes
        FROM atc_hierarchy 
        WHERE LENGTH(atc_code) = 7
        GROUP BY drug_concept_id
    """

    results = []
    with closing(conn.cursor()) as cursor:
        cursor.execute(atc_query)
        results = cursor.fetchall()

    return results


def store_atc7_codes_in_db(atc7_results):
    """Store ATC7 codes for drug concepts in the database"""

    with closing(conn.cursor()) as cursor:
        # Clear existing ATC7 data
        cursor.execute("DELETE FROM concept_atc7")

        # Insert new ATC7 data
        values = []
        for concept_id, atc7_codes in atc7_results:
            values.append((concept_id, atc7_codes))

        if values:
            cursor.executemany(
                """INSERT INTO concept_atc7 (concept_id, atc7_codes) 
                   VALUES (%s, %s)""",
                values,
            )

        conn.commit()

    return len(values)


def process_drug_atc7_codes():
    print("Finding ATC7 codes for drug concepts...")
    atc7_results = find_atc7_codes_for_drug_concepts()

    print(f"Found ATC7 codes for {len(atc7_results)} drug concepts")

    if atc7_results:
        stored_count = store_atc7_codes_in_db(atc7_results)
        print(f"Stored ATC7 codes for {stored_count} drug concepts")

    return len(atc7_results)


def get_atc7_codes_for_concept(concept_id: int):
    """Get ATC7 codes for a specific concept"""
    with closing(conn.cursor()) as cursor:
        cursor.execute(
            "SELECT atc7_codes FROM concept_atc7 WHERE concept_id = %s", (concept_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else []


def extract_atc7_codes_from_source(source_value: str) -> list:
    # ATC7 pattern: Letter, 2 digits, 2 letters, 2 digits - must be at the very beginning
    atc7_pattern = r"^([A-Z]\d{2}[A-Z]{2}\d{2})"

    # Only check source_value for ATC7 code at the beginning
    if source_value:
        # Clean the string but preserve the beginning structure
        cleaned_value = source_value.strip().upper()
        match = re.match(atc7_pattern, cleaned_value)
        if match:
            return [match.group(1)]

    return []


def import_vocabulary_with_copy(table_name: str, file_path: str):
    # Create the COPY command using CDM VocabImport syntax
    copy_command = f"COPY {table_name} FROM '{file_path}' WITH DELIMITER E'\\t' CSV HEADER QUOTE E'\\b'"

    try:
        with closing(conn.cursor()) as cursor:
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
            with closing(conn.cursor()) as cursor:
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


@st.cache_data(ttl=30)
def get_vocabulary_import_status():
    with closing(conn.cursor()) as cursor:
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


@st.cache_data(ttl=30)
def get_vocabulary_table_counts():
    tables = ["concept", "concept_relationship", "concept_ancestor"]
    counts = {}

    with closing(conn.cursor()) as cursor:
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


def save_auto_mapping_audit(
    mappings: list, mapping_method: str, target_domains: list = None
):
    with closing(conn.cursor()) as cursor:
        values = []
        for mapping in mappings:
            values.append(
                (
                    mapping["source_id"],
                    mapping["concept_id"],
                    mapping.get("confidence_score"),
                    mapping_method,
                    target_domains or [],
                )
            )

        cursor.executemany(
            """
            INSERT INTO auto_mapping_audit (source_id, concept_id, confidence_score, mapping_method, target_domains)
            VALUES (%s, %s, %s, %s, %s)
            """,
            values,
        )

        conn.commit()


def get_auto_mapping_statistics(vocabulary_id: int = None):
    """Get auto-mapping statistics, optionally filtered by vocabulary"""
    with closing(conn.cursor()) as cursor:
        if vocabulary_id:
            cursor.execute(
                """
                SELECT 
                    mapping_method,
                    COUNT(*) as mapping_count,
                    AVG(confidence_score) as avg_confidence,
                    MIN(confidence_score) as min_confidence,
                    MAX(confidence_score) as max_confidence
                FROM auto_mapping_audit ama
                JOIN source_concepts sc ON ama.source_id = sc.source_id
                WHERE sc.source_vocabulary_id = %s
                GROUP BY mapping_method
                ORDER BY mapping_count DESC
                """,
                (vocabulary_id,),
            )
        else:
            cursor.execute(
                """
                SELECT 
                    mapping_method,
                    COUNT(*) as mapping_count,
                    AVG(confidence_score) as avg_confidence,
                    MIN(confidence_score) as min_confidence,
                    MAX(confidence_score) as max_confidence
                FROM auto_mapping_audit
                GROUP BY mapping_method
                ORDER BY mapping_count DESC
                """
            )

        columns = [column[0] for column in cursor.description]
        data = cursor.fetchall()

        return format_db_response(data, columns)


def get_recent_auto_mappings(vocabulary_id: int = None, limit: int = 100):
    """Get recent auto-mapping results with details"""
    with closing(conn.cursor()) as cursor:
        if vocabulary_id:
            cursor.execute(
                """
                SELECT 
                    sc.source_concept_name,
                    c.concept_name as mapped_concept_name,
                    ama.confidence_score,
                    ama.mapping_method,
                    ama.target_domains,
                    ama.created_at
                FROM auto_mapping_audit ama
                JOIN source_concepts sc ON ama.source_id = sc.source_id
                JOIN concept c ON ama.concept_id = c.concept_id
                WHERE sc.source_vocabulary_id = %s
                ORDER BY ama.created_at DESC
                LIMIT %s
                """,
                (vocabulary_id, limit),
            )
        else:
            cursor.execute(
                """
                SELECT 
                    sc.source_concept_name,
                    c.concept_name as mapped_concept_name,
                    ama.confidence_score,
                    ama.mapping_method,
                    ama.target_domains,
                    ama.created_at
                FROM auto_mapping_audit ama
                JOIN source_concepts sc ON ama.source_id = sc.source_id
                JOIN concept c ON ama.concept_id = c.concept_id
                ORDER BY ama.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )

        columns = [column[0] for column in cursor.description]
        data = cursor.fetchall()

        return format_db_response(data, columns)


@st.cache_data(ttl=30)
def get_atc7_statistics():
    """Get ATC7 statistics"""
    with closing(conn.cursor()) as cursor:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_drugs_with_atc7,
                AVG(array_length(atc7_codes, 1)) as avg_atc7_per_drug
            FROM concept_atc7
        """)
        return cursor.fetchone()


@st.cache_data(ttl=30)
def get_source_vocabulary_ids():
    with closing(conn.cursor()) as cursor:
        cursor.execute("""
            SELECT DISTINCT source_vocabulary_id 
            FROM source_concepts 
            ORDER BY source_vocabulary_id
        """)
        return [row[0] for row in cursor.fetchall()]


@st.cache_data(ttl=30)
def get_concept_atc7_count():
    """Get ATC7 concept count"""
    with closing(conn.cursor()) as cursor:
        cursor.execute("SELECT COUNT(*) FROM concept_atc7")
        return cursor.fetchone()[0]
