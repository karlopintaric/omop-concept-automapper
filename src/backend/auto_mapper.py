import streamlit as st
from src.backend.llms.reranker import Reranker
from src.backend.llms.vector_store import VectorDatabase
from src.backend.llms.emb_model import OpenAIEmbeddingModel
from src.backend.llms.client import OpenAIClient
from src.backend.llms.chat_model import ChatModelWithStructuredOutput

from src.backend.db.methods.utils import (
    extract_atc7_codes_from_source,
)
from src.backend.db.methods.mapping import (
    get_unmapped_source_concepts,
    map_concepts,
    save_mapping_audit,
)

from src.backend.db.methods.embeddings import get_embedding_status
from src.backend.config_manager import get_config_manager
from src.backend.utils.logging import logger, log_and_show_success
from src.backend.utils.progress import StreamlitProgressTracker


class AutoMapper:
    def __init__(self, vector_store: VectorDatabase, rerankers: dict[str, Reranker]):
        self.vector_store = vector_store
        self.rerankers = rerankers

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

        filters["type"] = "standard"

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
        drug_specific: bool = False,
        atc7_codes: list | None = None,
    ):
        k = 30 if drug_specific else 15
        reranker_type = "drug" if drug_specific else "concept"

        matched_concepts = _self.get_similar_concepts(
            source_concept_name, domains=domains, k=k, atc7_codes=atc7_codes
        )

        if len(matched_concepts) == 0:
            return

        return _self.rerankers[reranker_type].select_similar(
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
        unmapped_concepts = get_unmapped_source_concepts(
            vocabulary_id,
        )

        # Ensure target_domains is a list for processing
        if isinstance(target_domains, str):
            target_domains = [target_domains]

        mapped_count = 0
        total_concepts = len(unmapped_concepts)

        # Debug logging
        logger.info(
            f"Found {total_concepts} unmapped concepts for vocabulary {vocabulary_id}"
        )
        if total_concepts == 0:
            logger.info("No unmapped concepts found - auto mapping completed")
            return {
                "mapped_count": 0,
                "total_concepts": 0,
                "mapping_method": "auto_drug" if drug_specific else "auto_standard",
                "confidence_threshold": confidence_threshold,
            }

        # Determine mapping method for audit trail
        mapping_method = "auto_drug" if drug_specific else "auto_standard"

        # Streamlit progress bar
        progress_tracker = StreamlitProgressTracker(
            total_count=total_concepts,
            message_template="Processing {current}/{total} concepts...",
        )

        logger.info(f"Starting auto-mapping for {total_concepts} concepts...")
        logger.info(f"Mapping method: {mapping_method}")
        logger.info(f"Target domains: {target_domains}")
        logger.info(f"Confidence threshold: {confidence_threshold}")

        for i, source_concept in enumerate(unmapped_concepts):
            source_concept_name = source_concept["source_concept_name"]
            source_id = source_concept["source_id"]

            # Update progress
            progress_tracker.update(1)

            try:
                logger.info(
                    f"Processing concept {i + 1}/{total_concepts}: '{source_concept_name}'"
                )

                source_value = source_concept.get("source_value", "")
                atc7_codes = None
                if drug_specific:
                    atc7_codes = extract_atc7_codes_from_source(source_value)

                    if atc7_codes:
                        logger.info(
                            f"Found ATC7 codes: {atc7_codes} for '{source_concept_name}'"
                        )

                    else:
                        logger.info(
                            f"No ATC7 codes found for '{source_concept_name}', falling back to standard mapping"
                        )

                mapped_result = self.auto_map(
                    source_concept_name,
                    domains=target_domains,
                    drug_specific=drug_specific,
                    atc7_codes=atc7_codes,
                )

                logger.info(f"Auto map result: {mapped_result}")

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
                    map_concepts(mapping_data)

                    # Save audit trail
                    save_mapping_audit(
                        mapping_data,
                        mapping_method,
                        target_domains=target_domains,
                    )

                    mapped_count += 1

                    logger.info(
                        f"✓ Mapped '{source_concept_name}' → '{selected_concept['concept_name']}' (confidence: {confidence_score})"
                    )

                else:
                    if mapped_result:
                        confidence = mapped_result.get("confidence_score", 0)
                        logger.info(
                            f"✗ Skipped '{source_concept_name}' (confidence: {confidence} < {confidence_threshold})"
                        )
                    else:
                        logger.info(f"✗ No mapping found for '{source_concept_name}'")

            except Exception as e:
                logger.error(
                    f"✗ Error mapping concept '{source_concept_name}", exc_info=True
                )
                continue

        progress_tracker.complete("Auto-mapping completed!")

        logger.info(
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
        status = get_embedding_status(self.vector_store.name, domain_filter)
        pending_count = status["pending"]

        if pending_count == 0:
            log_and_show_success("All concepts are already embedded!")

            return

        logger.info(f"Found {pending_count}  concepts to embed...")
        self.vector_store.embed_standard_concepts(
            pending_count, domain_filter, batch_size
        )
        logger.info("Standard concepts embedding completed!")


@st.cache_resource
def init_automapper():
    config_manager = get_config_manager()
    config = config_manager.get_config()

    vector_store_config = config["vector_store"]
    reranker_config = config["reranker"]

    client = OpenAIClient()

    emb_model = OpenAIEmbeddingModel(
        vector_store_config["embeddings"],
        client,
        dims=vector_store_config["dims"],
    )

    vector_store = VectorDatabase(
        vector_store_config["name"],
        embedding_model=emb_model,
        url=vector_store_config["url"],
    )

    chat_model = ChatModelWithStructuredOutput(
        reranker_config["model"],
        client,
    )

    rerankers = {
        "concept": Reranker(
            chat_model,
            drug_specific=False,
        ),
        "drug": Reranker(
            chat_model,
            drug_specific=True,
        ),
    }

    return AutoMapper(
        vector_store,
        rerankers=rerankers,
    )
