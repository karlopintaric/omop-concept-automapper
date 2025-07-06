import streamlit as st
from src.backend.db.methods import get_source_vocabulary_ids, get_standard_domains

DOMAINS = ["Device", "Drug", "Measurement", "Observation", "Procedure", "Condition"]


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


def display_domain_selector():
    """Display standard domain selector"""
    domains = get_standard_domains()
    if not domains:
        st.warning("No standard domains found. Please import OMOP vocabulary first.")
        return []

    selected_domains = st.multiselect(
        "Target Domains",
        options=domains,
        default=domains[:3] if len(domains) >= 3 else domains,
    )

    return selected_domains


def display_file_uploader(label: str, file_type: str = "csv"):
    """Generic file uploader component"""
    uploaded_file = st.file_uploader(
        label, type=[file_type], help=f"Upload a {file_type.upper()} file"
    )
    return uploaded_file
