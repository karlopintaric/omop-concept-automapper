import streamlit as st
import pandas as pd
from src.backend.db.methods.mapping import get_mapped_concepts, unmap_concepts
from src.frontend.ui.common import display_vocabulary_selector, clear_mapping_cache
from src.backend.utils.logging import logger, log_and_show_error


def render_commit_page():
    st.title("✅ Check & Commit Mappings")

    vocabulary_id, _ = display_vocabulary_selector()

    if vocabulary_id:
        # Load and display mapped concepts
        mapped_data = get_mapped_concepts(vocabulary_id)

        if not mapped_data:
            st.info("No mapped concepts found for this vocabulary.")
            return

        data = pd.DataFrame.from_dict(mapped_data)

        st.subheader(f"Mapped Concepts for Vocabulary {vocabulary_id}")

        event = st.dataframe(
            data,
            height=600,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="multi-row",
            column_order=[
                "source_value",
                "source_concept_name",
                "concept_name",
                "concept_id",
                "domain_id",
                "freq",
            ],
        )

        selected = event.selection.rows
        cols = st.columns((1, 2, 1, 1, 1), vertical_alignment="top")

        # Actions for selected rows
        if selected:
            selected_source_ids = [data.iloc[row]["source_id"] for row in selected]

            if cols[0].button(label="Unmap Selected", type="secondary"):
                try:
                    unmap_concepts(selected_source_ids)
                    st.success(f"Unmapped {len(selected_source_ids)} concepts")
                    clear_mapping_cache()
                    st.rerun()
                except Exception as e:
                    log_and_show_error("Error unmapping concepts", e)

        # Statistics
        cols[1].metric("Total Mappings", len(data))
        unique_concepts = data["concept_id"].nunique()
        cols[2].metric("Unique OMOP Concepts", unique_concepts)

        # Download button
        csv_data = data.to_csv(index=False).encode("utf-8")
        cols[3].download_button(
            "📥 Download CSV",
            csv_data,
            f"vocabulary_{vocabulary_id}_mappings.csv",
            "text/csv",
            key="download-csv",
            type="secondary",
        )

        # Export to final format button
        if cols[4].button(label="🚀 Export Final", type="primary", disabled=True):
            st.success("Mappings exported successfully to something (not implemented)!")

        # Display mapping quality metrics
        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📊 Mapping Statistics")
            domain_counts = data.groupby("domain_id").size()
            st.bar_chart(domain_counts)

        with col2:
            st.subheader("🎯 Mapping Coverage")
            total_freq = data["freq"].sum()
            st.metric("Total Frequency Coverage", f"{total_freq:,}")


render_commit_page()
