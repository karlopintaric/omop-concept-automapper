from src.backend.db.methods.embeddings import (
    fetch_standard_concepts,
    update_embedded_concepts_table,
)
from src.backend.llms.emb_model import EmbeddingModel
from qdrant_client import QdrantClient, models
from src.backend.utils.logging import logger


class VectorDatabase:
    def __init__(
        self,
        name: str,
        embedding_model: EmbeddingModel,
        url: str | None = None,
    ):
        self.emb_model = embedding_model
        self.name = name
        self.client = self._init_client(url=url)
        self.vector_store = self._init_db()

    def search(self, query: str, k: int = 5, filters: dict = {}):
        embedded_query = self.emb_model.embed(query)[0]
        filters = self._create_filters(filters)

        results = self.client.query_points(
            collection_name=self.name,
            query=embedded_query,
            with_payload=True,
            query_filter=filters,
            limit=k,
        )

        formatted_results = self._format_results(results)

        return formatted_results

    def embed_standard_concepts(self, domain_filter: str = None, batch_size: int = 100):
        logger.info("Disabling indexing for better embedding performance...")
        self._toggle_indexing(enable=False)

        try:
            for batch in fetch_standard_concepts(self.name, domain_filter, batch_size):
                self._embed_batch_standard_concepts(batch)
                self._update_embedded_concepts_table(batch, "standard_concepts")

        finally:
            print("Re-enabling indexing...")
            self._toggle_indexing(enable=True)

    def _embed_batch_standard_concepts(self, batch):
        """Embed a batch of standard concepts"""
        texts = [row[1] for row in batch]  # concept_name is at index 1
        embeddings = self.emb_model.embed(texts)

        points = []
        for i, row in enumerate(batch):
            (
                concept_id,
                concept_name,
                domain_id,
                vocabulary_id,
                concept_class_id,
                concept_code,
                atc7_codes,
            ) = row

            # Prepare metadata
            metadata = {
                "concept_id": concept_id,
                "concept_name": concept_name,
                "domain_id": domain_id,
                "vocabulary_id": vocabulary_id,
                "concept_class_id": concept_class_id,
                "concept_code": concept_code,
                "type": "standard",
                "atc7_codes": atc7_codes,
            }

            point = models.PointStruct(
                id=concept_id,
                vector=embeddings[i],
                payload={"text": concept_name, "metadata": metadata},
            )
            points.append(point)

        self.client.upsert(collection_name=self.name, points=points)

    def _update_embedded_concepts_table(self, batch, table_type):
        update_embedded_concepts_table(
            batch=batch,
            table_type=table_type,
            collection_name=self.name,
            embedding_model_name=self.emb_model.get_model_name(),
        )

    def _format_results(self, results: models.ScrollResult) -> list[dict]:
        """Format search results for display"""
        formatted = []
        for result in results.points:
            formatted.append(
                {
                    "score": result.score,
                    "text": result.payload["text"],
                    **result.payload["metadata"],
                }
            )
        return formatted

    def _init_client(self, url: str) -> QdrantClient:
        try:
            return QdrantClient(url=url, timeout=500)
        except Exception as e:
            logger.error("Error initializing Qdrant client", exc_info=True)
            raise

    def _init_db(self):
        emb_size = len(self.emb_model.embed("test")[0])

        if not self.client.collection_exists(self.name):
            logger.info(f"Creating new collection: {self.name}")
            self.create_new_collection(self.name, emb_size)
        else:
            logger.info(f"Using existing collection: {self.name}")

    def _create_filters(self, filter_dict: dict) -> models.Filter | None:
        if not filter_dict:
            return None

        filters = []
        for k, v in filter_dict.items():
            if isinstance(v, list):
                match_condition = models.MatchAny(any=v)
            else:
                match_condition = models.MatchValue(value=v)

            filters.append(
                models.FieldCondition(key=f"metadata.{k}", match=match_condition)
            )

        return models.Filter(must=filters)

    def _toggle_indexing(self, enable: bool):
        if enable:
            m = 16
        else:
            m = 0

        self.client.update_collection(
            collection_name=self.name,
            hnsw_config=models.HnswConfigDiff(m=m),
        )

    def create_new_collection(self, collection_name: str, vector_size: int) -> bool:
        """Create a new vector collection"""
        if self.client.collection_exists(collection_name):
            logger.warning(f"Collection '{collection_name}' already exists.")
            return False  # Collection already exists

        logger.info(
            f"Creating new collection: {collection_name} with vector size {vector_size}"
        )
        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size, distance=models.Distance.COSINE, on_disk=True
            ),
            hnsw_config=models.HnswConfigDiff(m=0),
        )

        logger.info(f"Collection '{collection_name}' created successfully.")

        return True

    def get_collections(self):
        try:
            collections = self.client.get_collections()
            return [collection.name for collection in collections.collections]
        except Exception:
            logger.error("Error fetching collections", exc_info=True)
            return []

    def switch_collection(self, new_collection_name: str):
        self.name = new_collection_name
        # Re-initialize to ensure collection exists
        self._init_db()
        self._toggle_indexing(enable=True)

    def get_collection_info(self, collection_name: str = None):
        if collection_name is None:
            collection_name = self.name

        try:
            info = self.client.get_collection(collection_name)
            return {
                "name": collection_name,
                "points_count": info.points_count,
                "vectors_config": info.config.params.vectors,
                "status": info.status,
            }
        except Exception:
            logger.error(
                f"Error getting collection info for {collection_name}", exc_info=True
            )
            return None

    def delete_collection(self, collection_name: str | None = None):
        """Delete a collection"""

        if collection_name is None:
            collection_name = self.name

        try:
            return self.client.delete_collection(collection_name)
        except Exception:
            logger.error(f"Error deleting collection {collection_name}", exc_info=True)
            return False
