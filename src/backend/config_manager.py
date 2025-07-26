import streamlit as st
from typing import Dict, Any
from src.backend.db.core import init_connection
from src.backend.db.methods.config import (
    create_config_table,
    set_default_config,
    get_config,
    update_config,
)
from src.backend.utils.logging import logger


class ConfigManager:
    """Manage application configuration with database persistence"""

    def __init__(self):
        self._ensure_config_table()
        self._set_defaults()

    def _ensure_config_table(self):
        """Create config table if it doesn't exist"""
        create_config_table()
        logger.info("✅ Config table ensured in database")

    def _set_defaults(self):
        """Set default configuration values if they don't exist"""
        defaults = {
            "vector_store.name": "omop_vocab",
            "vector_store.embeddings": "text-embedding-3-large",
            "vector_store.dims": "1024",
            "vector_store.url": "http://qdrant:6333",
            "reranker.model": "gpt-4.1",
        }

        set_default_config(defaults)

    @st.cache_data(ttl=60)
    def get_config(_self) -> Dict[str, Any]:
        """Get current configuration from database"""
        config = {"vector_store": {}, "reranker": {}}

        db_config = get_config()
        if not db_config:
            logger.warning("No configuration found in the database. Using defaults.")
            return config

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
        """Update configuration in the database"""
        update_config(updates)
        logger.info("✅ Configuration updated in database")

        self.clear_config_info_cache()

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
            logger.error(f"Error getting collections: {e}")
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
