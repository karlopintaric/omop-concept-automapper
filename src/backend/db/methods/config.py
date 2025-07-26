from typing import Any
from src.backend.db.core import init_connection

conn = init_connection()


def create_config_table():
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def set_default_config(defaults: dict[str, str]):
    with conn.cursor() as cursor:
        for key, value in defaults.items():
            cursor.execute(
                """
                    INSERT INTO app_config (key, value, updated_at) 
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (key) DO NOTHING
                """,
                (key, value),
            )
            conn.commit()


def get_config() -> dict[str, str]:
    """Get current configuration from database"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT key, value FROM app_config")
        db_config = cursor.fetchall()

    return db_config


def update_config(updates: dict[str, Any]):
    with conn.cursor() as cursor:
        for key, value in updates.items():
            cursor.execute(
                """
                        INSERT INTO app_config (key, value, updated_at) 
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (key) DO UPDATE SET 
                        value = EXCLUDED.value, 
                        updated_at = EXCLUDED.updated_at
                    """,
                (key, str(value)),
            )
        conn.commit()
