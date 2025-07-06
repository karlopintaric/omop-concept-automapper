import streamlit as st
from typing import Dict, Any
from contextlib import closing
from src.backend.db.core import init_connection


class ConfigManager:
    """Manage application configuration with database persistence"""

    def __init__(self):
        self.conn = init_connection()
        self._ensure_config_table()
        self._set_defaults()

    def _ensure_config_table(self):
        """Create config table if it doesn't exist"""
        with closing(self.conn.cursor()) as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.conn.commit()

    def _set_defaults(self):
        """Set default configuration values if they don't exist"""
        defaults = {
            "vector_store.name": "omop_vocab",
            "vector_store.embeddings": "text-embedding-3-large",
            "vector_store.dims": "1024",
            "vector_store.url": "http://qdrant:6333",
            "reranker.model": "gpt-4.1",
        }

        with closing(self.conn.cursor()) as cursor:
            for key, value in defaults.items():
                cursor.execute(
                    """
                    INSERT INTO app_config (key, value, updated_at) 
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (key) DO NOTHING
                """,
                    (key, value),
                )
            self.conn.commit()

    @st.cache_data(ttl=30)
    def get_config(_self) -> Dict[str, Any]:
        """Get current configuration from database"""
        config = {"vector_store": {}, "reranker": {}}

        with closing(_self.conn.cursor()) as cursor:
            cursor.execute("SELECT key, value FROM app_config")
            db_config = cursor.fetchall()

            for key, value in db_config:
                if key == "vector_store.embeddings":
                    config["vector_store"]["embeddings"] = value
                elif key == "vector_store.dims":
                    config["vector_store"]["dims"] = int(value)
                elif key == "vector_store.name":
                    config["vector_store"]["name"] = value
                elif key == "vector_store.url":
                    config["vector_store"]["url"] = value
                elif key == "reranker.model":
                    config["reranker"]["model"] = value

        return config

    def update_config(self, updates: Dict[str, Any]):
        with closing(self.conn.cursor()) as cursor:
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
            self.conn.commit()

    def get_embedding_models(self):
        return {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072}

    def get_llm_models(self):
        return ["gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o", "gpt-4o-mini"]

    def create_new_collection_name(self, embedding_model: str, dims: int) -> str:
        """Generate a new collection name based on model and dimensions"""
        model_short = embedding_model.replace("text-embedding-", "").replace("-", "")
        return f"omop_vocab_{model_short}_{dims}"

    def get_vector_collections(self) -> list:
        try:
            config = self.get_config()
            return [config["vector_store"]["name"]]
        except Exception as e:
            print(f"Error getting collections: {e}")
            return ["omop_vocab"]

    def validate_dimensions(self, model: str, dims: int) -> bool:
        """Validate if the dimensions are supported for the given model"""
        model_info = self.get_embedding_models()
        if model in model_info:
            return dims <= model_info[model]
        return False

    def clear_config_info_cache(self):
        self.get_config.clear()


# Global config manager instance
@st.cache_resource
def get_config_manager():
    return ConfigManager()
