import os
from contextlib import closing
from src.backend.db.core import get_db_connection, read_query_from_sql_file


def seed_database_cli():
    """Seed the database with initial schema (CLI version)"""
    module_dir = os.path.dirname(os.path.dirname(__file__))
    query_path = os.path.join(module_dir, "db", "seed.sql")
    seed_query = read_query_from_sql_file(query_path)

    with get_db_connection() as conn:
        with closing(conn.cursor()) as cursor:
            cursor.execute(seed_query)
            conn.commit()


def get_database_stats():
    """Get database statistics (CLI version)"""
    with get_db_connection() as conn:
        with closing(conn.cursor()) as cursor:
            stats = {}

            # Count concepts
            cursor.execute("SELECT COUNT(*) FROM concept")
            stats["total_concepts"] = cursor.fetchone()[0]

            # Count standard concepts
            cursor.execute("SELECT COUNT(*) FROM concept WHERE standard_concept = 'S'")
            stats["standard_concepts"] = cursor.fetchone()[0]

            # Count source concepts
            cursor.execute("SELECT COUNT(*) FROM source_concepts")
            stats["source_concepts"] = cursor.fetchone()[0]

            # Count mappings
            cursor.execute("SELECT COUNT(*) FROM source_standard_map")
            stats["mappings"] = cursor.fetchone()[0]

            # Count embedded concepts
            cursor.execute("SELECT COUNT(*) FROM embedded_concepts")
            stats["embedded_concepts"] = cursor.fetchone()[0]

            # Count ATC7 codes
            cursor.execute("SELECT COUNT(*) FROM concept_atc7")
            stats["atc7_concepts"] = cursor.fetchone()[0]

            return stats
