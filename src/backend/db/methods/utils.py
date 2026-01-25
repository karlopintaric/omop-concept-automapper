import math
import re

import streamlit as st
from src.backend.db.core import format_db_response, init_connection


conn = init_connection()


@st.cache_data
def get_total_pages(
    vocabulary_id: int,
    per_page: int,
):
    with conn.cursor() as c:
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
def get_concept_from_id(
    concept_id: int,
):
    """Get concept details by concept ID"""
    with conn.cursor() as c:
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


def find_atc7_codes_for_drug_concepts():
    """
    Find all ATC7 codes for drug domain concepts using concept relationships and ancestors.
    This function traces through the OMOP relationships to find ATC codes.
    """

    # Query to find ATC codes through relationships and ancestors
    # Fancy recursive AI written query go brrr
    atc_query = """
        SELECT 
            c_drug.concept_id AS drug_concept_id,
            ARRAY_AGG(DISTINCT c_atc.concept_code) AS atc_codes
        FROM concept c_drug
        JOIN concept_ancestor ca 
            ON c_drug.concept_id = ca.descendant_concept_id
        JOIN concept c_atc 
            ON ca.ancestor_concept_id = c_atc.concept_id
        WHERE 
            -- 1. Define the Drug side
            c_drug.domain_id = 'Drug'
            AND c_drug.standard_concept = 'S'
            
            -- 2. Define the ATC side
            AND c_atc.vocabulary_id = 'ATC'
            
            -- 3. Filter for specific ATC level. 
            AND LENGTH(c_atc.concept_code) = 7 
        GROUP BY 
            c_drug.concept_id
    """

    results = []
    with conn.cursor() as cursor:
        cursor.execute(atc_query)
        results = cursor.fetchall()

    return results


def store_atc7_codes_in_db(
    atc7_results,
):
    """Store ATC7 codes for drug concepts in the database"""

    with conn.cursor() as cursor:
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
    atc7_results = find_atc7_codes_for_drug_concepts()

    stored_count = 0
    if atc7_results:
        stored_count = store_atc7_codes_in_db(atc7_results)

    return stored_count


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


def get_auto_mapping_statistics(
    vocabulary_id: int = None,
):
    """Get auto-mapping statistics, optionally filtered by vocabulary"""
    with conn.cursor() as cursor:
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
    with conn.cursor() as cursor:
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


@st.cache_data(ttl=60)
def get_atc7_statistics():
    """Get ATC7 statistics"""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_drugs_with_atc7,
                AVG(array_length(atc7_codes, 1)) as avg_atc7_per_drug
            FROM concept_atc7
        """)
        return cursor.fetchone()


@st.cache_data(ttl=60)
def get_source_vocabulary_ids():
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT source_vocabulary_id 
            FROM source_concepts 
            ORDER BY source_vocabulary_id
        """)
        return [row[0] for row in cursor.fetchall()]


@st.cache_data(ttl=60)
def get_concept_atc7_count():
    """Get ATC7 concept count"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM concept_atc7")
        return cursor.fetchone()[0]
