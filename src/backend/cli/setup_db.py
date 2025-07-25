#!/usr/bin/env python3
"""
Database setup script for Auto OMOP Mapper
"""

import os
import sys
import time

# Add the project root to the Python path
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, project_root)

# Import after path setup
from src.backend.db.cli_utils import seed_database_cli, get_database_stats  # noqa: E402
from src.backend.db.core import get_db_connection, create_connection_string  # noqa: E402
from src.backend.utils.logging import logger  # noqa: E402


def wait_for_database(max_attempts=30, delay=2):
    """Wait for database to be ready"""
    logger.info("Waiting for database to be ready...")

    for attempt in range(max_attempts):
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    logger.info("✅ Database connection established")
                    return True
        except Exception as e:
            logger.warning(
                f"Attempt {attempt + 1}/{max_attempts}: Database not ready yet ({e})"
            )
            if attempt < max_attempts - 1:
                time.sleep(delay)

    logger.error("❌ Database failed to become ready after maximum attempts")
    return False


def setup_database():
    """Initialize and seed the database"""
    logger.info("🗄️ Setting up Auto OMOP Mapper database...")

    # Display connection info (without password)
    try:
        conn_str = create_connection_string()
        # Parse connection string to show info without password
        parts = conn_str.split("@")
        if len(parts) > 1:
            host_db = parts[1]
            logger.info(f"📡 Connecting to: {host_db}")
    except Exception as e:
        logger.error("❌ Error reading connection info", exc_info=True)
        sys.exit(1)

    # Wait for database to be ready
    if not wait_for_database():
        sys.exit(1)

    # Set up database schema
    try:
        seed_database_cli()
        logger.info("✅ Database schema created successfully")

        # Show database stats
        stats = get_database_stats()
        logger.info(f"📊 Database initialized with {stats['total_concepts']} concepts")

        logger.info("🎉 Database setup completed successfully!")
        logger.info("Next steps:")
        logger.info("1. Open http://localhost:8501 in your browser")
        logger.info("2. Go to the 'Import Data' page to upload your vocabularies")
        logger.info("3. Embed the concepts for similarity search")
        logger.info("4. Start mapping your concepts!")

    except Exception as e:
        logger.error("❌ Error setting up database", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    setup_database()
