import streamlit as st
from typing import Dict, Any
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
            "reranker.model": "gpt-5-mini",
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

    @st.cache_data(ttl=3600)
    def _fetch_models_from_api(_self) -> list:
        """Fetch all available models from OpenAI API"""
        import os
        from openai import OpenAI
        
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.warning("No OPENAI_API_KEY set, using default models")
                return []
                
            client = OpenAI(api_key=api_key)
            models = client.models.list()
            return [m.id for m in models.data]
        except Exception as e:
            logger.warning(f"Failed to fetch models from API: {e}")
            return []

    def get_embedding_models(self):
        """Get available embedding models and their dimensions"""
        
        # Known embedding models and their max supported dimensions
        known_models = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        
        fetched_models = self._fetch_models_from_api()
        
        if fetched_models:
            # Filter known models that are available in API
            available = {
                m: known_models[m] 
                for m in known_models 
                if m in fetched_models
            }
            # If we found matches, return those
            if available:
                return available
        
        # Fallback to defaults
        return {
            "text-embedding-3-small": 1536, 
            "text-embedding-3-large": 3072
        }

    def get_llm_models(self):
        """Get available LLM models (starting with gpt)"""
        fetched_models = self._fetch_models_from_api()
        
        # Priority/Custom models that should always be available
        priority_models = [
            "gpt-5-mini",
            "gpt-4o",
            "gpt-4-turbo",
        ]
        
        if fetched_models:
            # Filter for text generation models (gpt-*)
            fetched_gpt = [m for m in fetched_models if m.startswith("gpt")]
            fetched_gpt.sort(reverse=True)
            
            # Filter out models already in priority list to avoid duplication
            others = [m for m in fetched_gpt if m not in priority_models]
            
            return priority_models + others
        
        # Fallback list if API fails
        return [
            "gpt-5-mini",
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-4.1",
            "gpt-3.5-turbo",
        ]

    def create_new_collection_name(self, embedding_model: str, dims: int) -> str:
        """Generate a new collection name based on model and dimensions"""
        # Defaul emb model
        if embedding_model == "text-embedding-3-large":
            return "omop_vocab"

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
        self._fetch_models_from_api.clear()


# Global config manager instance
@st.cache_resource
def get_config_manager():
    return ConfigManager()
