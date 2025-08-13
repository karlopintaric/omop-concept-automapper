import streamlit as st
from src.backend.db.methods.mapping import (
    get_mapped_concepts,
    get_unmapped_source_concepts,
)
from src.backend.db.methods.utils import get_source_vocabulary_ids, get_total_pages
from src.backend.utils.logging import logger

DOMAINS = [
    "Condition",
    "Device",
    "Drug",
    "Measurement",
    "Observation",
    "Procedure",
]


def display_vocabulary_selector():
    source_vocabularies = get_source_vocabulary_ids()
    if not source_vocabularies:
        st.warning("No source vocabularies found. Please import source concepts first.")
        return None, False

    selected_vocabulary = st.selectbox(
        "Source Vocabulary ID",
        options=source_vocabularies,
        format_func=lambda x: f"Vocabulary {x}",
    )
    is_drug_vocabulary = st.checkbox("Drug vocabulary", value=False)

    return selected_vocabulary, is_drug_vocabulary


def clear_mapping_cache():
    """Clear the cache for mapping-related functions"""
    # Clear specific cache functions
    get_source_vocabulary_ids()
    get_unmapped_source_concepts.clear()
    get_mapped_concepts.clear()
    get_total_pages.clear()
    logger.info("✅ Mapping cache cleared")
