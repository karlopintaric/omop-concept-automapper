from psycopg import Connection
import streamlit as st

from src.backend.db.core import format_db_response, init_connection

conn = init_connection()


@st.cache_data(ttl=60)
def get_unmapped_source_concepts(
    vocabulary_id: int, page: int | None = None, per_page: int = 50
):
    with conn.cursor() as c:
        base_query = """
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
                AND ssm.source_id IS NULL
            GROUP BY
                sc.source_id,
                sc.source_value, 
                sc.source_concept_name,
                sc.source_vocabulary_id, 
                sc.freq  
            ORDER BY sc.freq DESC
        """

        params = [vocabulary_id]

        if page is not None:
            offset = (page - 1) * per_page
            base_query += " LIMIT %s OFFSET %s"
            params.extend([per_page, offset])

        c.execute(base_query, params)

        columns = [col[0] for col in c.description]
        data = c.fetchall()

        return format_db_response(data, columns)


@st.cache_data(ttl=60)
def get_mapped_concepts(
    vocabulary_id: int,
):
    with conn.cursor() as c:
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


def save_mapping_audit(
    mappings: list[dict],
    mapping_method: str,
    target_domains: list = None,
):
    with conn.cursor() as cursor:
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


def map_concepts(mappings: list):
    with conn.cursor() as cursor:
        # Get unique source IDs from mappings
        source_ids = list(set([mapping["source_id"] for mapping in mappings]))

        # Remove existing mappings for these source concepts (for remapping)
        if source_ids:
            placeholders = ",".join(["%s" for _ in source_ids])
            cursor.execute(
                f"DELETE FROM source_standard_map WHERE source_id IN ({placeholders})",
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

        conn.commit()


def unmap_concepts(
    source_ids: list,
):
    """Remove mappings for given source concept IDs"""
    with conn.cursor() as cursor:
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
