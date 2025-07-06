import streamlit as st
from src.backend.auto_mapper import init_automapper
from src.frontend.ui.common import DOMAINS


def render_search_page():
    auto_mapper = init_automapper()

    st.title("🔍 Search OMOP Concepts")

    cols = st.columns((4, 2, 1, 2), vertical_alignment="bottom")
    query = cols[0].text_input(
        label="Concept Name", placeholder="Enter concept name to search..."
    )
    domain_filter = cols[1].multiselect("Domains", options=DOMAINS)

    with cols[-1].popover("Advanced filters"):
        vocabulary_filter = st.text_input(
            label="Vocabulary", help="Filter by specific vocabulary"
        )
        atc7_filter = st.text_input(
            label="ATC7 Code",
            help="Filter drugs by ATC7 code (e.g., A02BC01)",
            max_chars=7,
        )

    k_value = cols[-2].number_input(
        "Number of results", min_value=1, max_value=100, value=50
    )

    if query:
        with st.spinner("Searching for similar concepts..."):
            # Build filters
            filters = {}
            if vocabulary_filter:
                filters["vocabulary_id"] = vocabulary_filter
            if atc7_filter and len(atc7_filter.strip()) > 0:
                results = auto_mapper.get_similar_concepts_with_atc_filter(
                    query,
                    atc7_codes=[atc7_filter.strip()],
                    k=k_value,
                    domains=domain_filter,
                    vocabulary_id=vocabulary_filter,
                )
            else:
                results = auto_mapper.get_similar_concepts(
                    query,
                    k=k_value,
                    domains=domain_filter,
                    vocabulary_id=vocabulary_filter,
                )

        if results:
            st.success(f"Found {len(results)} similar concepts")

            # Display results in a more user-friendly format
            for i, result in enumerate(results):
                with st.expander(
                    f"Rank {i + 1}: {result.get('concept_name', 'N/A')} (Score: {result.get('score', 0):.3f})"
                ):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write("**Concept Details:**")
                        st.write(f"- **ID:** {result.get('concept_id', 'N/A')}")
                        st.write(f"- **Name:** {result.get('concept_name', 'N/A')}")
                        st.write(f"- **Domain:** {result.get('domain_id', 'N/A')}")

                    with col2:
                        st.write("**Classification:**")
                        st.write(
                            f"- **Class:** {result.get('concept_class_id', 'N/A')}"
                        )
                        st.write(
                            f"- **Vocabulary:** {result.get('vocabulary_id', 'N/A')}"
                        )
                        st.write(f"- **Code:** {result.get('concept_code', 'N/A')}")

                        # Display ATC7 codes if available
                        if result.get("atc7_codes"):
                            st.write("**ATC7 Codes:**")
                            atc7_codes = result["atc7_codes"]
                            if isinstance(atc7_codes, list):
                                for atc7 in atc7_codes[:5]:  # Show first 5 ATC7 codes
                                    st.write(f"- {atc7}")
                                if len(atc7_codes) > 5:
                                    st.write(f"- ... and {len(atc7_codes) - 5} more")
        else:
            st.warning(
                "No similar concepts found. Try adjusting your search terms or filters."
            )
    else:
        st.info("Enter a concept name above to search for similar OMOP concepts.")

        # Show some helpful information
        st.markdown("""
        ### Search Tips
        - Filter by domain to narrow down results
        - Use ATC7 codes to find drugs in specific therapeutic classes
        - Try filtering by vocabularies (e.g., 'RxNorm' for drugs)
        """)


render_search_page()
