from typing import List, Tuple
from datetime import datetime, timezone
import streamlit as st

from src.backend.utils.logging import logger
from src.backend.db.core import init_connection

conn = init_connection()

STANDARD_CONCEPTS = "standard_concepts"
SOURCE_CONCEPTS = "source_concepts"


def fetch_standard_concepts(
    collection_name: str,
    domain_filter: str | None = None,
    batch_size: int = 100,
):
    query = """
        SELECT c.concept_id, c.concept_name, c.domain_id, c.vocabulary_id, 
            c.concept_class_id, c.concept_code, ca.atc7_codes
        FROM concept c
        LEFT JOIN concept_atc7 ca ON c.concept_id = ca.concept_id
        LEFT JOIN embedded_concepts ec ON c.concept_id = ec.concept_id 
            AND ec.collection_name = %s
            AND ec.concept_type = 'standard'
        WHERE c.standard_concept = 'S'
        AND ec.concept_id IS NULL
        AND LOWER(c.concept_class_id) NOT LIKE %s
        AND LOWER(c.concept_class_id) NOT LIKE %s
    """

    params = [
        collection_name,
        "%box%",
        "%marketed%",
    ]

    if domain_filter:
        query += " AND c.domain_id = %s"
        params.append(domain_filter)

    with conn.cursor() as cursor:
        cursor.execute(query, params)

        while True:
            batch = cursor.fetchmany(batch_size)
            if not batch:
                break
            yield batch  # yield each batch to caller


def update_embedded_concepts_table(
    batch: List[Tuple],
    table_type: str,
    collection_name: str,
    embedding_model_name: str,
) -> None:
    """Update the embedded_concepts table to track what has been embedded."""

    values = []
    now = datetime.now(timezone.utc)

    if table_type == STANDARD_CONCEPTS:
        for row in batch:
            concept_id = row[0]
            values.append(
                (
                    concept_id,
                    collection_name,
                    embedding_model_name,
                    now,
                    "standard",
                    None,
                )
            )
    elif table_type == SOURCE_CONCEPTS:
        for row in batch:
            source_id = row[0]
            source_vocabulary_id = row[3]
            values.append(
                (
                    source_id,
                    collection_name,
                    embedding_model_name,
                    now,
                    "source",
                    source_vocabulary_id,
                )
            )
    else:
        raise ValueError(f"Unknown table_type: {table_type}")

    try:
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO embedded_concepts 
                    (concept_id, collection_name, embedding_model, embedded_at, concept_type, source_vocabulary_id) 
                VALUES (%s, %s, %s, %s, %s, %s) 
                ON CONFLICT (concept_id, collection_name, concept_type) DO UPDATE SET 
                    embedding_model = EXCLUDED.embedding_model, 
                    embedded_at = EXCLUDED.embedded_at,
                    source_vocabulary_id = EXCLUDED.source_vocabulary_id
                """,
                values,
            )
        conn.commit()
    except Exception as e:
        logger.error("Failed to update embedded concepts table", exc_info=True)
        conn.rollback()
        raise


@st.cache_data(ttl=60)
def get_embedding_status(
    collection_name: str, domain_filter: str | None = None
) -> dict:
    """Get embedding status for concepts"""

    query = """
        SELECT 
            COUNT(*) as total_concepts,
            COUNT(ec.concept_id) as embedded_concepts
        FROM concept sc
        LEFT JOIN embedded_concepts ec ON sc.concept_id = ec.concept_id 
            AND ec.concept_type = 'standard'
        WHERE sc.standard_concept = 'S'
        AND (ec.collection_name = %s OR ec.collection_name IS NULL)
        AND LOWER(sc.concept_class_id) NOT LIKE %s
        AND LOWER(sc.concept_class_id) NOT LIKE %s
        """
    params = [collection_name, "%box%", "%marketed%"]

    if domain_filter:
        query += " AND sc.domain_id = %s"
        params.append(domain_filter)

    with conn.cursor() as c:
        c.execute(query, params)
        result = c.fetchone()
        return {
            "total": result[0],
            "embedded": result[1],
            "pending": result[0] - result[1],
            "percentage": (result[1] / result[0] * 100) if result[0] > 0 else 0,
        }


def reset_embeddings_status(collection_name: str):
    logger.info(f"Resetting embeddings status for collection: {collection_name}")

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM embedded_concepts
                WHERE collection_name = %s
                """,
                (collection_name,)
            )
        conn.commit()
    except Exception as e:
        logger.error("Failed to reset embeddings status", exc_info=True)
        conn.rollback()
        raise