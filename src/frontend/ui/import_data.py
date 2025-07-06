import streamlit as st
import pandas as pd
import os
from src.backend.db.core import init_connection
from src.backend.db.methods import (
    import_source_concepts,
    process_drug_atc7_codes,
    get_embedding_status,
    import_all_vocabulary_tables,
    get_vocabulary_import_status,
    get_vocabulary_table_counts,
    check_vocabulary_files_exist,
    get_atc7_statistics,
    get_source_vocabulary_ids,
    get_concept_atc7_count,
)
from src.backend.auto_mapper import init_automapper
from src.backend.config_manager import get_config_manager


conn = init_connection()


def clear_vocab_cache():
    get_vocabulary_import_status.clear()
    get_vocabulary_table_counts.clear()


def clear_embedding_caches():
    get_embedding_status.clear()


def clear_atc7_caches():
    get_atc7_statistics.clear()
    get_concept_atc7_count.clear()


def clear_source_concepts_cache():
    get_source_vocabulary_ids.clear()
    get_embedding_status.clear()


def render_vocabulary_import_tab():
    st.subheader("Import OMOP Vocabulary Tables")
    st.markdown("""
    Import OMOP vocabulary tables.
    
    **Instructions:**
    1. Place your OMOP vocabulary CSV files in the `vocabulary/` directory
    2. Required files: `CONCEPT.csv`, `CONCEPT_RELATIONSHIP.csv`, `CONCEPT_ANCESTOR.csv`
    3. Click "Import OMOP Vocabulary" to import all tables
    """)

    # Show current import status
    st.write("### Current Import Status")

    try:
        import_status = get_vocabulary_import_status()
        table_counts = get_vocabulary_table_counts()

        if import_status:
            col1, col2, col3 = st.columns(3)

            for i, record in enumerate(import_status):
                table_name = record["table_name"]
                last_import = record["last_import"]
                total_records = record["total_records"]
                current_count = table_counts.get(table_name, 0)

                with [col1, col2, col3][i % 3]:
                    st.metric(
                        f"{table_name.title().replace('_', ' ')}",
                        f"{current_count:,}",
                        help=f"Last import: {last_import.strftime('%Y-%m-%d %H:%M') if last_import else 'Never'}",
                    )
        else:
            st.info("No vocabulary tables have been imported yet.")

    except Exception as e:
        st.error(f"Error getting import status: {str(e)}")

    # Check file availability
    st.write("### File Status")

    try:
        file_status = check_vocabulary_files_exist()

        for table, info in file_status.items():
            col1, col2, col3 = st.columns([3, 1, 2])

            with col1:
                status_icon = "✅" if info["exists"] else "❌"
                st.write(f"{status_icon} **{info['filename']}**")

            with col2:
                if info["exists"]:
                    size_mb = info["size"] / (1024 * 1024)
                    st.write(f"{size_mb:.1f} MB")
                else:
                    st.write("Not found")

            with col3:
                if info["exists"]:
                    st.write("✅ Ready to import")
                else:
                    st.write("❌ File missing")

    except Exception as e:
        st.error(f"Error checking files: {str(e)}")

    st.divider()

    # Import button
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🚀 Import OMOP Vocabulary", type="primary", key="import_vocab"):
            try:
                with st.spinner(
                    "Importing vocabulary tables... This may take several minutes."
                ):
                    results = import_all_vocabulary_tables()

                # Clear caches after import
                clear_vocab_cache()

                # Show results
                success_count = sum(
                    1 for r in results.values() if r["status"] == "success"
                )
                total_records = sum(r["records_imported"] for r in results.values())

                if success_count > 0:
                    st.success(
                        f"✅ Successfully imported {success_count} tables with {total_records:,} total records!"
                    )

                # Show detailed results
                for table, result in results.items():
                    if result["status"] == "success":
                        st.success(
                            f"✅ {table}: {result['records_imported']:,} records imported"
                        )
                    elif result["status"] == "failed":
                        st.error(f"❌ {table}: {result['error']}")
                    else:
                        st.warning(f"⚠️ {table}: {result['error']}")

                # Refresh the page to show updated counts
                st.rerun()

            except Exception as e:
                st.error(f"❌ Error importing vocabulary: {str(e)}")

    with col2:
        st.info("""
        **Note:** Files must be placed in the `vocabulary/` directory before importing.
        """)


def render_atc7_processing_tab():
    st.subheader("ATC7 Code Processing")
    st.markdown("""
    After importing the OMOP vocabulary tables, process ATC7 codes for drug concepts.
    This will find all ATC7 codes that drug concepts belong to through relationships and hierarchies.
    """)

    st.info("""
    **Prerequisites:**
    1. Import CONCEPT table
    2. Import CONCEPT_RELATIONSHIP table  
    3. Import CONCEPT_ANCESTOR table
    """)

    col1, col2 = st.columns(2)

    if col1.button("🔍 Process ATC7 Codes", type="primary"):
        try:
            with st.spinner("Processing ATC7 codes for drug concepts..."):
                count = process_drug_atc7_codes()

            # Clear ATC7 caches after processing
            clear_atc7_caches()

            if count > 0:
                st.success(
                    f"✅ Successfully processed ATC7 codes for {count:,} drug concepts!"
                )
            else:
                st.warning(
                    "⚠️ No ATC7 codes found. Ensure all vocabulary tables are imported."
                )

        except Exception as e:
            st.error(f"❌ Error processing ATC7 codes: {str(e)}")

    if col2.button("📊 View ATC7 Statistics"):
        try:
            result = get_atc7_statistics()

            if result and result[0] > 0:
                st.metric("Drugs with ATC7 codes", f"{result[0]:,}")
                st.metric("Average ATC7 codes per drug", f"{result[1]:.1f}")
            else:
                st.info("No ATC7 data found. Process ATC7 codes first.")

        except Exception as e:
            st.error(f"Error getting ATC7 statistics: {str(e)}")


def render_source_concepts_tab():
    st.subheader("Import Source Concepts")
    st.markdown("""
    Upload a CSV file containing your source concepts that need to be mapped to OMOP. The file should be comma delimited, not tab (like OMOP vocabularies).
    Required columns:
    - `source_value`: Source concept code/value
    - `source_concept_name`: Name or description of the source concept
    - `freq` (optional): Frequency/count of usage
    """)

    st.info("""
    💡 **Drug-Specific Mapping Enhancement**: 
    For drug vocabularies, if your `source_value` starts with an ATC7 code (e.g., 'A10BA02XYZ'), 
    the system will use this code to limit search space during drug-specific mapping.
    """)

    source_file = st.file_uploader(
        "Upload Source Concepts CSV",
        type=["csv"],
        help="CSV file with your source concepts",
    )

    vocabulary_id = st.number_input(
        "Source Vocabulary ID",
        min_value=1,
        value=1,
        help="Unique identifier for this source vocabulary",
    )

    if source_file is not None:
        # Show preview
        if st.checkbox("Preview source data"):
            df = pd.read_csv(source_file)
            st.dataframe(df.head(), use_container_width=True)
            source_file.seek(0)  # Reset file pointer

        col1, col2 = st.columns(2)

        if col1.button("Import Source Concepts", type="primary"):
            try:
                # Save uploaded file temporarily
                temp_path = "temp_source.csv"
                with open(temp_path, "wb") as f:
                    f.write(source_file.getbuffer())

                with st.spinner("Importing source concepts..."):
                    count = import_source_concepts(temp_path, vocabulary_id)

                # Clear source-related caches after import
                clear_source_concepts_cache()

                st.success(f"✅ Successfully imported {count:,} source concepts!")

                # Remove temp file
                os.remove(temp_path)

            except Exception as e:
                st.error(f"❌ Error importing source concepts: {str(e)}")

        if col2.button("Embed After Import (Source)"):
            st.info(
                "After importing, go to the 'Embedding Management' tab to embed the concepts."
            )


def render_embedding_management_tab():
    st.subheader("Embedding Management")
    st.markdown("""
    Embed concepts into the vector database to enable similarity search and auto-mapping.
    """)

    # Show current configuration
    try:
        config_manager = get_config_manager()
        current_config = config_manager.get_config()

        st.info(f"""
        **Current Configuration:**
        - Collection: `{current_config["vector_store"]["name"]}`
        - Embedding Model: `{current_config["vector_store"]["embeddings"]}`
        - Dimensions: `{current_config["vector_store"]["dims"]}`
        - LLM Model: `{current_config["reranker"]["model"]}`
        """)

        # Show collection information
        auto_mapper = init_automapper()
        collection_info = auto_mapper.vector_store.get_collection_info()
        if collection_info:
            st.metric("Points in Collection", f"{collection_info['points_count']:,}")

    except Exception as e:
        st.warning(f"Could not load configuration: {str(e)}")

    col1, col2 = st.columns(2)

    with col1:
        st.write("### Standard Concepts")

        try:
            standard_status = get_embedding_status("standard_concepts")

            st.metric("Total Standard Concepts", f"{standard_status['total']:,}")
            st.metric("Embedded", f"{standard_status['embedded']:,}")
            progress = standard_status["percentage"] / 100
            st.progress(progress, text=f"{standard_status['percentage']:.1f}% embedded")

            # Domain filter
            domain_filter = st.selectbox(
                "Filter by Domain (optional)",
                options=[
                    "All",
                    "Drug",
                    "Device",
                    "Condition",
                    "Procedure",
                    "Measurement",
                    "Observation",
                ],
                index=0,
            )
            domain_value = None if domain_filter == "All" else domain_filter

            if st.button("🚀 Embed Standard Concepts", type="primary"):
                auto_mapper = init_automapper()

                with st.spinner(
                    "Embedding standard concepts... This may take a while."
                ):
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    try:
                        auto_mapper.embed_all_concepts(domain_filter=domain_value)

                        # Clear embedding caches after successful embedding
                        clear_embedding_caches()

                        progress_bar.progress(1.0)
                        status_text.success("Standard concepts embedded successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error embedding standard concepts: {str(e)}")

        except Exception as e:
            st.error(f"Error getting embedding status: {str(e)}")

    with col2:
        st.write("### Source Concepts")

        try:
            source_status = get_embedding_status("source_concepts")

            st.metric("Total Source Concepts", f"{source_status['total']:,}")
            st.metric("Embedded", f"{source_status['embedded']:,}")
            progress = (
                source_status["percentage"] / 100 if source_status["total"] > 0 else 0
            )
            st.progress(progress, text=f"{source_status['percentage']:.1f}% embedded")

            # Vocabulary filter
            vocab_ids = get_source_vocabulary_ids()

            vocab_options = ["All"] + [f"Vocabulary {vid}" for vid in vocab_ids]
            vocab_filter = st.selectbox(
                "Filter by Vocabulary (optional)",
                options=vocab_options,
                index=0,
                key="source_vocab_filter",
            )

            vocab_id_value = None
            if vocab_filter != "All":
                vocab_id_value = int(vocab_filter.split()[-1])

            if st.button(
                "🚀 Embed Source Concepts", type="primary", key="embed_source"
            ):
                auto_mapper = init_automapper()

                with st.spinner("Embedding source concepts... This may take a while."):
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    try:
                        auto_mapper.embed_source_concepts(
                            vocabulary_id=vocab_id_value,
                            batch_size=st.session_state.get("batch_size_setting", 1000),
                        )

                        # Clear embedding caches after successful embedding
                        clear_embedding_caches()

                        progress_bar.progress(1.0)
                        status_text.success("Source concepts embedded successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error embedding source concepts: {str(e)}")

        except Exception as e:
            st.error(f"Error getting source embedding status: {str(e)}")

    # Batch embedding settings
    st.divider()
    st.subheader("⚙️ Embedding Settings")

    col1, col2 = st.columns(2)
    col1.slider(
        "Batch Size",
        min_value=100,
        max_value=2000,
        value=1000,
        step=10,
        key="batch_size_setting",
    )

    # Clear embeddings
    st.divider()
    st.subheader("🗑️ Clear Embeddings")
    st.warning("This will remove all embeddings from the vector database.")

    if st.button("Clear All Embeddings", type="secondary", key="clear_embeddings"):
        st.info(
            "Delete in the Qdrant dashboard at http://localhost:6333/dashboard#/collections"
        )


def render_import_page():
    """Main render function for the import page"""

    st.title("📥 Data Import & Embedding")

    st.markdown("""
    This page allows you to:
    1. Import OMOP standard vocabulary concepts
    2. Import your source concepts that need to be mapped
    3. Embed concepts into the vector database for similarity search
    """)

    tabs = st.tabs(
        [
            "OMOP Vocabulary Tables",
            "Source Concepts",
            "ATC7 Processing",
            "Embedding Management",
        ]
    )

    with tabs[0]:
        render_vocabulary_import_tab()

    with tabs[2]:
        render_atc7_processing_tab()

    with tabs[1]:
        render_source_concepts_tab()

    with tabs[3]:
        render_embedding_management_tab()


render_import_page()
