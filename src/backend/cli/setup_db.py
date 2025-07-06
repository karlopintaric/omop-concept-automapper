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


def wait_for_database(max_attempts=30, delay=2):
    """Wait for database to be ready"""
    print("Waiting for database to be ready...")

    for attempt in range(max_attempts):
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    print("✅ Database connection established")
                    return True
        except Exception as e:
            print(f"Attempt {attempt + 1}/{max_attempts}: Database not ready yet ({e})")
            if attempt < max_attempts - 1:
                time.sleep(delay)

    print("❌ Database failed to become ready after maximum attempts")
    return False


def setup_database():
    """Initialize and seed the database"""
    print("🗄️ Setting up Auto OMOP Mapper database...")

    # Display connection info (without password)
    try:
        conn_str = create_connection_string()
        # Parse connection string to show info without password
        parts = conn_str.split("@")
        if len(parts) > 1:
            host_db = parts[1]
            print(f"📡 Connecting to: {host_db}")
    except Exception as e:
        print(f"❌ Error reading connection info: {e}")
        sys.exit(1)

    # Wait for database to be ready
    if not wait_for_database():
        sys.exit(1)

    # Set up database schema
    try:
        seed_database_cli()
        print("✅ Database schema created successfully")

        # Show database stats
        stats = get_database_stats()
        print(f"📊 Database initialized with {stats['total_concepts']} concepts")

        print("\n🎉 Database setup completed successfully!")
        print("\nNext steps:")
        print("1. Open http://localhost:8501 in your browser")
        print("2. Go to the 'Import Data' page to upload your vocabularies")
        print("3. Embed the concepts for similarity search")
        print("4. Start mapping your concepts!")

    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    setup_database()
