import streamlit as st
import pandas as pd
import re
from src.backend.db.methods.utils import (
    get_total_pages,
    get_concept_from_id,
    get_auto_mapping_statistics,
    get_recent_auto_mappings,
    extract_atc7_codes_from_source,
)
from src.backend.db.methods.mapping import (
    get_unmapped_source_concepts,
    map_concepts,
    get_mapped_concepts,
    save_mapping_audit,
)
from src.backend.auto_mapper import init_automapper, AutoMapper
from src.frontend.ui.common import (
    display_vocabulary_selector,
    DOMAINS,
)
from src.backend.utils.logging import log_and_show_error, logger
from src.frontend.ui.common import clear_mapping_cache

# Constants
ATC7_PATTERN = r"^[A-Z]\d{2}[A-Z]{2}\d{2}$"
DEFAULT_SEARCH_LIMIT = 100

# Column configurations for dataframes
UNMAPPED_CONCEPTS_COLUMNS = {
    "source_value": st.column_config.TextColumn(
        "Source Code", help="Original code from your source system"
    ),
    "source_concept_name": st.column_config.TextColumn(
        "Source Concept Name", help="Description/name of the concept"
    ),
    "mapped_concepts": st.column_config.NumberColumn(
        "# Mapped", help="Number of OMOP concepts already mapped to this source concept"
    ),
    "freq": st.column_config.NumberColumn(
        "Frequency", help="How often this concept appears in your data"
    ),
}

SEARCH_RESULTS_COLUMNS = {
    "similarity": st.column_config.NumberColumn(
        "Similarity", format="%.3f", help="Higher values indicate better matches"
    )
}


def initialize_page_controls(vocabulary_id: int, is_drug_vocabulary: bool = False):
    cols = st.columns((1, 1, 2, 3), vertical_alignment="bottom")

    # Page size selection
    batch_size = cols[1].selectbox(
        "Concepts per page",
        options=[25, 50, 100],
        index=1,
        help="Number of concepts to display per page",
    )

    # Calculate pagination
    total_pages = get_total_pages(vocabulary_id, per_page=batch_size)
    current_page = cols[0].number_input(
        "Page",
        min_value=1,
        max_value=total_pages,
        step=1,
        help=f"Navigate through {total_pages} pages",
    )

    # Auto map all button and settings
    with cols[2].popover("⚙️ Auto Map Settings"):
        st.markdown("**Auto-Mapping Configuration**")

        # Domain selector - always visible in settings
        st.markdown("**Target Domains**")
        target_domains = st.multiselect(
            "Select domains for auto-mapping:",
            options=DOMAINS,
            default=st.session_state.get("auto_map_domains", []),
            help="Choose which OMOP domains to map concepts to",
            key="auto_map_domains",
        )

        confidence_threshold = st.slider(
            "Confidence Threshold",
            min_value=1,
            max_value=10,
            value=8,
            help="Minimum confidence score (1-10) required to auto-map a concept",
        )

        drug_specific = st.checkbox(
            "Drug-specific mapping",
            value=is_drug_vocabulary,
            help="Use specialized drug mapping logic with ATC7 filtering when possible",
        )

        if drug_specific:
            st.info(
                "💡 **ATC7 Enhanced Mapping**: When enabled, the system will automatically extract ATC7 codes from source values (e.g., 'A10BA02' from medication codes) and use them to limit the search space."
            )

        if st.button("🤖 Start Auto Mapping", type="primary", use_container_width=True):
            if target_domains:
                auto_mapper = init_automapper()
                with st.spinner("Auto-mapping all concepts... This may take a while."):
                    logger.info("Started auto-mapping all concepts...")
                    try:
                        result = auto_mapper.automap_all(
                            vocabulary_id,
                            target_domains,
                            drug_specific=drug_specific,
                            confidence_threshold=confidence_threshold,
                        )
                        _display_auto_mapping_result(result)
                        clear_mapping_cache()
                        st.rerun()
                    except Exception as e:
                        log_and_show_error("Error during auto-mapping", e)
            else:
                st.warning("Please select at least one target domain for auto-mapping.")

    # Page info
    cols[-1].markdown(f"Page **{current_page}** of **{total_pages}**")

    return current_page, batch_size


def display_data_table(vocabulary_id: int, current_page: int, batch_size: int):
    """Display the data table with unmapped concepts"""

    data_section = st.container()
    data = get_unmapped_source_concepts(
        vocabulary_id, page=current_page, per_page=batch_size
    )

    if not data:
        st.info(
            "🎉 No unmapped concepts found for this vocabulary. All concepts have been mapped!"
        )
        return [], []

    with data_section:
        st.markdown(f"**Unmapped Concepts** (showing {len(data)} concepts)")
        st.caption("💡 Click on a row to start mapping that concept")

        event = st.dataframe(
            data,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            column_order=[
                "source_value",
                "source_concept_name",
                "mapped_concepts",
                "freq",
            ],
            column_config=UNMAPPED_CONCEPTS_COLUMNS,
        )

    return event.selection.rows, data


def display_concept_details(
    concept_data: dict, auto_mapper: AutoMapper, is_drug_vocabulary: bool
):
    st.subheader(f"📝 Mapping: {concept_data['source_concept_name']}")

    # Concept information row
    cols = st.columns((3, 1, 1, 2, 2), vertical_alignment="bottom", gap="large")

    concept_name_input = cols[0].text_input(
        value=concept_data["source_concept_name"],
        label="Source concept name",
        help="Edit the name to search for better matches",
    )

    cols[1].markdown(f"**Source ID:** {concept_data['source_id']}")
    cols[2].markdown(f"**Frequency:** {concept_data['freq']}")

    # Search filters
    with cols[3].popover("🔍 Search Filters"):
        search_params = _render_search_filters(
            is_drug_vocabulary, concept_data.get("source_value", "")
        )

    results = []
    # Search for similar concepts
    if cols[4].button("🔍 Search Similar Concepts", type="primary"):
        with st.spinner("Searching for similar concepts..."):
            results, search_method = _perform_concept_search(
                auto_mapper, concept_name_input, search_params
            )
            st.session_state.search_method = search_method

    if not results:
        # Auto-search on first load with default filters
        with st.spinner("Searching for similar concepts..."):
            auto_search_params = {
                "domains": st.session_state.get("domains", []),
                "vocabulary_filter": "",
                "limit": DEFAULT_SEARCH_LIMIT,
                "use_atc7_filter": is_drug_vocabulary,
                "atc7_codes": extract_atc7_codes_from_source(
                    concept_data.get("source_value")
                ),
            }
            results, search_method = _perform_concept_search(
                auto_mapper, concept_name_input, auto_search_params
            )
            st.session_state.search_method = f"Auto {search_method}"

    if not results:
        st.warning(
            "No similar concepts found. Try adjusting your search term or filters."
        )
        return

    # Display results
    st.divider()

    # Show search method used
    search_method = st.session_state.get("search_method", "Standard similarity")
    st.caption(f"🔍 Search method: {search_method}")

    cols = st.columns((3, 1), vertical_alignment="top", gap="large")

    with cols[0]:
        st.markdown(f"**Found {len(results)} similar concepts:**")
        concept_selection_event = st.dataframe(
            results,
            use_container_width=True,
            on_select="rerun",
            selection_mode="multi-row",
            column_config=SEARCH_RESULTS_COLUMNS,
        )

    # Manual concept ID entry option
    manual_concept_ids = ""
    with cols[0]:
        if st.checkbox(
            "💡 Enter concept IDs manually", help="If you know specific concept IDs"
        ):
            manual_concept_ids = st.text_input(
                "Concept ID(s)",
                placeholder="123456 or 123456;789012;345678",
                help="Enter one or more concept IDs separated by semicolons",
            )

    # Handle concept selection and mapping
    selected_concepts = _handle_concept_selection(
        results, concept_selection_event, manual_concept_ids
    )

    if selected_concepts:
        _display_selected_concepts_and_map(selected_concepts, concept_data, cols)
    else:
        with cols[1]:
            st.info(
                "👆 Select concepts from the table to map them to this source concept."
            )


def display_mapping_statistics(vocabulary_id: int):
    """Display mapping statistics for the selected vocabulary"""
    try:
        unmapped_count = len(get_unmapped_source_concepts(vocabulary_id))
        mapped_count = len(get_mapped_concepts(vocabulary_id))
        total_count = unmapped_count + mapped_count

        if total_count > 0:
            progress_percentage = (mapped_count / total_count) * 100
        else:
            progress_percentage = 0

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Concepts", total_count)
        with col2:
            st.metric("Mapped", mapped_count)
        with col3:
            st.metric("Unmapped", unmapped_count)
        with col4:
            st.metric("Progress", f"{progress_percentage:.1f}%")

        # Progress bar
        if total_count > 0:
            st.progress(progress_percentage / 100)

        # Auto-mapping statistics
        with st.expander("📊 Auto-Mapping Audit Trail", expanded=False):
            try:
                auto_stats = get_auto_mapping_statistics(vocabulary_id)
                if auto_stats:
                    st.markdown("**Mapping Method Statistics:**")
                    for stat in auto_stats:
                        method = stat["mapping_method"]
                        count = stat["mapping_count"]
                        avg_conf = stat["avg_confidence"]

                        cols = st.columns([2, 1, 1])
                        cols[0].metric(f"{method.title()} Mappings", count)
                        if avg_conf:
                            cols[1].metric("Avg Confidence", f"{avg_conf:.2f}")

                    # Show recent mappings
                    st.markdown("**Recent Auto-Mappings:**")
                    recent_mappings = get_recent_auto_mappings(vocabulary_id, limit=10)
                    if recent_mappings:
                        df_recent = pd.DataFrame(recent_mappings)
                        st.dataframe(
                            df_recent[
                                [
                                    "source_concept_name",
                                    "mapped_concept_name",
                                    "confidence_score",
                                    "mapping_method",
                                    "created_at",
                                ]
                            ],
                            use_container_width=True,
                            height=200,
                        )
                    else:
                        st.info("No auto-mapping history found for this vocabulary.")
                else:
                    st.info("No auto-mapping statistics available for this vocabulary.")
            except Exception as e:
                st.error(f"Error loading auto-mapping statistics: {str(e)}")

        return unmapped_count
    except Exception as e:
        st.error(f"Error loading statistics: {str(e)}")
        return 0


def render_mapping_page():
    st.title("🗺️ Map Concepts")

    st.markdown("""
    This page allows you to:
    1. **Auto Map All**: Automatically map all unmapped concepts using AI similarity search
    2. **Manual Mapping**: Review and manually map individual concepts with search and filtering
    
    💡 **Tip**: Use the Import Data page to import vocabulary and embed concepts before mapping.
    """)

    # Main mapping interface
    vocabulary_id, is_drug_vocabulary = display_vocabulary_selector()

    if vocabulary_id is None:
        st.info("Please select a vocabulary to start mapping concepts.")
        return

    # Display mapping statistics
    st.subheader("📊 Mapping Progress")
    unmapped_count = display_mapping_statistics(vocabulary_id)

    if unmapped_count == 0:
        st.success("🎉 All concepts in this vocabulary have been mapped!")
        st.info(
            "Switch to a different vocabulary or check the Import Data page to add more concepts."
        )
        return

    st.divider()

    current_page, batch_size = initialize_page_controls(
        vocabulary_id, is_drug_vocabulary
    )
    selected_row_indices, data = display_data_table(
        vocabulary_id, current_page, batch_size
    )

    if selected_row_indices and data:
        selected_concept = data[selected_row_indices[0]]
        auto_mapper = init_automapper()

        st.divider()
        display_concept_details(selected_concept, auto_mapper, is_drug_vocabulary)
    elif data:  # Has data but no selection
        st.info("👆 Select a concept from the table above to start mapping.")


def _validate_atc7_code(code: str) -> bool:
    """Validate ATC7 code format"""
    return bool(re.match(ATC7_PATTERN, code))


def _get_atc7_codes(source_value: str, manual_atc7: str = None) -> list:
    """Extract or validate ATC7 codes from source value or manual input"""

    # Try automatic extraction first
    auto_codes = extract_atc7_codes_from_source(source_value)
    if auto_codes:
        return auto_codes

    # Try manual input if provided
    if manual_atc7:
        manual_code = manual_atc7.strip().upper()
        if _validate_atc7_code(manual_code):
            return [manual_code]
        else:
            st.error(
                "Invalid ATC7 code format. Expected: Letter-Digit-Digit-Letter-Letter-Digit-Digit (e.g., A10BA02)"
            )

    return []


def _perform_concept_search(
    auto_mapper: AutoMapper, concept_name: str, search_params: dict
) -> tuple:
    """Perform concept search with ATC7 filtering if applicable"""
    use_atc7 = search_params.get("use_atc7_filter", False)
    atc7_codes = search_params.get("atc7_codes", [])

    if use_atc7 and atc7_codes:
        search_method = f"ATC7 filtered ({atc7_codes[0]})"
    else:
        search_method = "Standard similarity"

    results = auto_mapper.get_similar_concepts(
        concept_name,
        k=search_params.get("limit", DEFAULT_SEARCH_LIMIT),
        domains=search_params.get("domains", []),
        vocabulary_id=search_params.get("vocabulary_filter", ""),
        atc7_codes=atc7_codes if use_atc7 else None,
    )

    return results, search_method


def _display_auto_mapping_result(result: dict):
    """Display auto-mapping results in a consistent format"""
    if result:
        mapped_count = result.get("mapped_count", 0)
        total_concepts = result.get("total_concepts", 0)
        mapping_method = result.get("mapping_method", "auto")
        confidence_threshold = result.get("confidence_threshold", 8)

        st.success(
            f"Auto-mapping completed! Successfully mapped {mapped_count} out of {total_concepts} concepts "
            f"using {mapping_method} method (confidence ≥ {confidence_threshold})."
        )

        if mapped_count > 0:
            st.info(
                "✅ All mappings have been saved to the database and can be reviewed in the mapping table."
            )
    else:
        st.success("Auto-mapping completed!")


def _render_search_filters(is_drug_vocabulary: bool, source_value: str) -> dict:
    """Render search filters and return search parameters"""
    search_params = {}

    st.markdown("**Target Domains**")
    search_params["domains"] = st.multiselect(
        "Select domains to search in:",
        options=DOMAINS,
        default=st.session_state.get("domains", []),
        help="Narrow search to specific OMOP domains",
    )
    st.session_state.domains = search_params["domains"]

    st.markdown("**Vocabulary Filter**")
    search_params["vocabulary_filter"] = st.text_input(
        "Vocabulary ID",
        value="",
        help="Filter by specific vocabulary (e.g., 'SNOMED', 'ICD10CM')",
    )

    # Drug-specific ATC7 filtering
    search_params["use_atc7_filter"] = False
    search_params["atc7_codes"] = []

    if is_drug_vocabulary:
        st.markdown("**🧬 Drug-Specific ATC7 Filtering**")
        auto_atc7_codes = extract_atc7_codes_from_source(source_value)

        search_params["use_atc7_filter"] = st.checkbox(
            "Enable ATC7 filtering",
            value=bool(auto_atc7_codes),
            help="Filter search results to drugs with the specific ATC7 code from source value",
        )

        if search_params["use_atc7_filter"]:
            if auto_atc7_codes:
                atc7_code = auto_atc7_codes[0]
                st.info(f"🔍 Using ATC7 code from source value: **{atc7_code}**")
                search_params["atc7_codes"] = [atc7_code]
            else:
                st.warning("No ATC7 code detected at the beginning of source value")
                manual_atc7 = st.text_input(
                    "Manual ATC7 code",
                    placeholder="A10BA02",
                    help="Enter ATC7 code manually (7 characters: Letter-Digit-Digit-Letter-Letter-Digit-Digit)",
                    max_chars=7,
                )
                search_params["atc7_codes"] = _get_atc7_codes("", manual_atc7)

    st.markdown("**Search Limit**")
    search_params["limit"] = st.slider(
        "Max results", min_value=10, max_value=200, value=DEFAULT_SEARCH_LIMIT, step=10
    )

    return search_params


def _handle_concept_selection(
    results: list, concept_selection_event, manual_concept_ids: str = ""
) -> list:
    """Handle concept selection from dataframe or manual input"""
    selected_concepts = None

    if concept_selection_event.selection.rows:
        selected_concepts = [results[i] for i in concept_selection_event.selection.rows]
    elif manual_concept_ids:
        try:
            concept_ids = [
                int(id.strip())
                for id in manual_concept_ids.replace(",", ";").split(";")
            ]
            selected_concepts = []
            for concept_id in concept_ids:
                concept_data_result = get_concept_from_id(concept_id)
                if concept_data_result:
                    selected_concepts.append(concept_data_result[0])
                else:
                    st.error(f"Concept ID {concept_id} not found")
        except ValueError:
            st.error("Please enter valid concept IDs separated by semicolons")

    return selected_concepts or []


def _display_selected_concepts_and_map(
    selected_concepts: list, source_concept_data: dict, cols
):
    """Display selected concepts and handle mapping confirmation"""

    with cols[1]:
        st.markdown("**Selected concepts for mapping:**")
        for i, concept in enumerate(selected_concepts, 1):
            with st.container(border=True):
                st.markdown(f"**{i}. {concept['concept_name']}**")
                st.caption(
                    f"ID: {concept['concept_id']} | Domain: {concept['domain_id']}"
                )
                st.caption(f"Vocabulary: {concept['vocabulary_id']}")

        st.divider()

        if st.button("✅ Confirm Mapping", type="primary", use_container_width=True):
            try:
                mappings = [
                    {
                        "source_id": source_concept_data["source_id"],
                        "concept_id": concept["concept_id"],
                    }
                    for concept in selected_concepts
                ]
                map_concepts(mappings)
                st.success(
                    f"Successfully mapped to {len(selected_concepts)} concept(s)!"
                )

                # Save mapping audit
                save_mapping_audit(mappings, mapping_method="manual")

                clear_mapping_cache()
                st.rerun()
            except Exception as e:
                st.error("Error mapping concepts", exc_info=True)


render_mapping_page()
