import streamlit as st
from src.backend.llms.reranker import Reranker
from src.backend.db.vector_store import VectorDatabase
from src.backend.db.methods import (
    get_unmapped_concepts,
    map_concepts,
    save_auto_mapping_audit,
)

from src.backend.config_manager import get_config_manager
from src.backend.utils.logging import logger


class AutoMapper:
    def __init__(self, vector_store_config, reranker_config):
        self.vector_store = VectorDatabase(
            vector_store_config["name"],
            embeddings=vector_store_config["embeddings"],
            emb_dims=vector_store_config["dims"],
            url=vector_store_config["url"],
        )

        self.rerankers = {
            "drug": Reranker(reranker_config["model"], drug_specific=True),
            "concept": Reranker(reranker_config["model"], drug_specific=False),
        }

    @st.cache_data(max_entries=5)
    def get_similar_concepts(
        _self,
        source_concept_name: str,
        k: int = 5,
        domains: str | list = [],
        vocabulary_id: str = "",
        atc7_codes: list | None = None,
    ):
        logger.info(f"🔍 Vector search for: '{source_concept_name}' (k={k})")

        filters = {}
        if domains:
            filters["domain_id"] = domains

        if vocabulary_id:
            filters["vocabulary_id"] = vocabulary_id

        if atc7_codes:
            filters["atc7_codes"] = atc7_codes

        logger.info(f"🔍 Filters: {filters}")

        results = _self.vector_store.search(source_concept_name, k, filters)

        logger.info(f"🔍 Found {len(results)} similar concepts")
        if results:
            logger.info(f"🔍 Top result: {results[0].get('concept_name', 'Unknown')}")

        return results

    @st.cache_data(max_entries=5, show_spinner="Finding best match...")
    def auto_map(
        _self,
        source_concept_name: str,
        domains: list | str = [],
    ):
        matched_concepts = _self.get_similar_concepts(
            source_concept_name, domains=domains, k=10
        )

        if len(matched_concepts) == 0:
            return

        return _self.rerankers["concept"].select_similar(
            source_concept_name, matched_concepts
        )

    @st.cache_data(
        max_entries=5, show_spinner="Finding best match with ATC filtering..."
    )
    def auto_map_with_atc_filter(
        _self,
        source_concept_name: str,
        atc7_codes: list = None,
        domains: list | str = [],
    ):
        """Auto-map with ATC7 code filtering"""
        matched_concepts = _self.get_similar_concepts_with_atc_filter(
            source_concept_name,
            atc7_codes=atc7_codes,
            k=25,
            domains=domains,
        )

        if len(matched_concepts) == 0:
            return

        return _self.rerankers["drug"].select_similar(
            source_concept_name, matched_concepts
        )

    def automap_all(
        self,
        vocabulary_id: int,
        target_domains: str | list,
        drug_specific: bool = False,
        confidence_threshold: int = 8,
    ):
        """Auto-map all unmapped concepts and save results to database"""
        unmapped_concepts = get_unmapped_concepts(vocabulary_id)

        # Ensure target_domains is a list for processing
        if isinstance(target_domains, str):
            target_domains = [target_domains]

        mapped_count = 0
        total_concepts = len(unmapped_concepts)

        # Debug logging
        print(
            f"Found {total_concepts} unmapped concepts for vocabulary {vocabulary_id}"
        )
        if total_concepts == 0:
            print("No unmapped concepts found - auto mapping completed")
            return {
                "mapped_count": 0,
                "total_concepts": 0,
                "mapping_method": "auto_drug" if drug_specific else "auto_standard",
                "confidence_threshold": confidence_threshold,
            }

        # Determine mapping method for audit trail
        mapping_method = "auto_drug" if drug_specific else "auto_standard"

        # Check if we're in Streamlit context for progress bar
        try:
            import streamlit as st

            progress_bar = st.progress(0)
            status_text = st.empty()
            in_streamlit = True
        except Exception:
            progress_bar = None
            status_text = None
            in_streamlit = False

        print(f"Starting auto-mapping for {total_concepts} concepts...")
        print(f"Mapping method: {mapping_method}")
        print(f"Target domains: {target_domains}")
        print(f"Confidence threshold: {confidence_threshold}")

        for i, source_concept in enumerate(unmapped_concepts):
            source_concept_name = source_concept["source_concept_name"]
            source_id = source_concept["source_id"]

            # Update progress
            if in_streamlit and progress_bar:
                progress = (i + 1) / total_concepts
                progress_bar.progress(progress)
                status_text.text(
                    f"Processing concept {i + 1}/{total_concepts}: {source_concept_name[:50]}..."
                )

            try:
                print(
                    f"Processing concept {i + 1}/{total_concepts}: '{source_concept_name}'"
                )

                # For drug-specific mapping, try ATC7 filtering first
                if drug_specific:
                    from src.backend.db.methods import extract_atc7_codes_from_source

                    # Extract ATC7 codes from source value and name
                    source_value = source_concept.get("source_value", "")
                    atc7_codes = extract_atc7_codes_from_source(source_value)

                    if atc7_codes:
                        print(
                            f"Found ATC7 codes: {atc7_codes} for '{source_concept_name}'"
                        )
                        mapped_result = self.auto_map_with_atc_filter(
                            source_concept_name,
                            atc7_codes=atc7_codes,
                            domains=target_domains,
                        )
                    else:
                        print(
                            f"No ATC7 codes found for '{source_concept_name}', using standard drug mapping"
                        )
                        mapped_result = self.auto_map(
                            source_concept_name,
                            drug_specific=drug_specific,
                            domains=target_domains,
                        )
                else:
                    mapped_result = self.auto_map(
                        source_concept_name,
                        drug_specific=drug_specific,
                        domains=target_domains,
                    )

                print(f"Auto map result: {mapped_result}")

                if (
                    mapped_result
                    and mapped_result.get("confidence_score", 0) >= confidence_threshold
                ):
                    # Extract the selected concept
                    selected_concept = mapped_result["selected"]
                    confidence_score = mapped_result["confidence_score"]

                    # Prepare mapping data for database
                    mapping_data = [
                        {
                            "source_id": source_id,
                            "concept_id": selected_concept["concept_id"],
                            "confidence_score": confidence_score,
                        }
                    ]

                    # Save mapping to database
                    map_concepts(mapping_data, is_manual=False)

                    # Save audit trail
                    save_auto_mapping_audit(
                        mapping_data, mapping_method, target_domains
                    )

                    mapped_count += 1

                    print(
                        f"✓ Mapped '{source_concept_name}' → '{selected_concept['concept_name']}' (confidence: {confidence_score})"
                    )

                else:
                    if mapped_result:
                        confidence = mapped_result.get("confidence_score", 0)
                        print(
                            f"✗ Skipped '{source_concept_name}' (confidence: {confidence} < {confidence_threshold})"
                        )
                    else:
                        print(f"✗ No mapping found for '{source_concept_name}'")

            except Exception as e:
                print(f"✗ Error mapping concept '{source_concept_name}': {str(e)}")
                continue

        # Clear progress indicators
        if in_streamlit and progress_bar:
            progress_bar.empty()
            status_text.empty()

        print(
            f"Auto-mapping completed: {mapped_count}/{total_concepts} concepts mapped successfully"
        )

        return {
            "mapped_count": mapped_count,
            "total_concepts": total_concepts,
            "mapping_method": mapping_method,
            "target_domains": target_domains,
            "confidence_threshold": confidence_threshold,
        }

    def embed_all_concepts(self, domain_filter: str = None, batch_size: int = 100):
        logger.info("Starting to embed standard concepts...")

        # Check status before embedding
        status = self.vector_store.get_embedding_status()
        pending_count = status["standard_concepts"]["pending"]

        if pending_count == 0:
            logger.info("All standard concepts are already embedded!")
            return

        logger.info(f"Found {pending_count} standard concepts to embed...")
        self.vector_store.embed_standard_concepts(domain_filter, batch_size)
        logger.info("Standard concepts embedding completed!")

    def embed_source_concepts(self, vocabulary_id: int = None, batch_size: int = 100):
        """Embed source concepts in the vector database"""
        logger.info("Starting to embed source concepts...")

        # Check status before embedding
        status = self.vector_store.get_embedding_status()
        pending_count = status["source_concepts"]["pending"]

        if pending_count == 0:
            logger.info("All source concepts are already embedded!")
            return

        logger.info(f"Found {pending_count} source concepts to embed...")
        self.vector_store.embed_source_concepts(vocabulary_id, batch_size)
        logger.info("Source concepts embedding completed!")

    def get_embedding_status(self):
        """Get the current embedding status"""
        return self.vector_store.get_embedding_status()


@st.cache_resource
def init_automapper():
    config_manager = get_config_manager()
    config = config_manager.get_config()

    return AutoMapper(config["vector_store"], config["reranker"])
