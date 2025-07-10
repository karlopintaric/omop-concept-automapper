from src.backend.db.emb_model import EmbeddingModel
from qdrant_client import QdrantClient, models
import pandas as pd
from tqdm import tqdm
from contextlib import closing
from src.backend.db.core import init_connection
from datetime import datetime


class VectorDatabase:
    def __init__(
        self,
        name: str,
        embeddings: str,
        emb_dims: int,
        url: str | None = None,
    ):
        self.emb_model = self._init_emb_model(embeddings, emb_dims)
        self.name = name
        self.client = self._init_client(url=url)
        self.vector_store = self._init_db()
        self.conn = init_connection()

        # Ensure database schema is up to date
        self._ensure_schema_compatibility()

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

    def search_with_atc7_filter(
        self, query: str, atc7_codes: list = None, k: int = 5, filters: dict = {}
    ):
        # Add ATC7 filtering using array matching
        if atc7_codes:
            # Convert ATC codes to 7-character format
            normalized_atc_codes = []
            for atc7 in atc7_codes:
                if len(atc7) >= 7:
                    normalized_atc_codes.append(atc7[:7])
                else:
                    normalized_atc_codes.append(atc7)

            # Add ATC7 array filter
            filters["atc7_codes"] = normalized_atc_codes

        results = self.search(
            query=query,
            k=k,
            filters=filters,
        )

        return results

    def add_docs_from_csv(
        self,
        csv_path: str,
        content_col: str,
        metadata_cols: list,
        batch_size: int = 1000,
    ):
        """Add documents from CSV file to vector store in batches"""
        print("Disabling indexing for better embedding performance...")
        self._toggle_indexing(enable=False)

        try:
            df = pd.read_csv(csv_path)
            total_rows = len(df)

            for i in tqdm(range(0, total_rows, batch_size), desc="Embedding batches"):
                batch_df = df.iloc[i : i + batch_size]
                self._embed_batch_from_dataframe(batch_df, content_col, metadata_cols)

        finally:
            print("Re-enabling indexing...")
            self._toggle_indexing(enable=True)

    def embed_standard_concepts(self, domain_filter: str = None, batch_size: int = 100):
        print("Disabling indexing for better embedding performance...")
        self._toggle_indexing(enable=False)

        try:
            query = """
                SELECT c.concept_id, c.concept_name, c.domain_id, c.vocabulary_id, 
                    c.concept_class_id, c.concept_code, ca.atc7_codes
                FROM concept c
                LEFT JOIN concept_atc7 ca ON c.concept_id = ca.concept_id
                LEFT JOIN embedded_concepts ec ON c.concept_id = ec.concept_id 
                    AND ec.collection_name = %s
                    AND ec.concept_type = 'standard'
                WHERE c.standard_concept = 'S'
                AND ec.concept_id IS NULL
                AND LOWER(c.concept_class_id) NOT LIKE %s
            """

            params = [self.name, '%brand%']

            if domain_filter:
                query += " AND c.domain_id = %s"
                params.append(domain_filter)

            with closing(self.conn.cursor()) as cursor:
                cursor.execute(query, params)

                while True:
                    batch = cursor.fetchmany(batch_size)
                    if not batch:
                        break

                    self._embed_batch_standard_concepts(batch)
                    self._update_embedded_concepts_table(batch, "standard_concepts")

        finally:
            print("Re-enabling indexing...")
            self._toggle_indexing(enable=True)

    def embed_source_concepts(self, vocabulary_id: int = None, batch_size: int = 100):
        """Embed source concepts from database in batches"""
        print("Disabling indexing for better embedding performance...")
        self._toggle_indexing(enable=False)

        try:
            query = """
                SELECT sc.source_id, sc.source_value, sc.source_concept_name, sc.source_vocabulary_id
                FROM source_concepts sc
                LEFT JOIN embedded_concepts ec ON sc.source_id = ec.concept_id 
                    AND ec.collection_name = %s
                    AND ec.concept_type = 'source'
                WHERE sc.mapped = FALSE
                AND ec.concept_id IS NULL
            """

            if vocabulary_id:
                query += f" AND sc.source_vocabulary_id = {vocabulary_id}"

            with closing(self.conn.cursor()) as cursor:
                cursor.execute(query, (self.name,))

                while True:
                    batch = cursor.fetchmany(batch_size)
                    if not batch:
                        break

                    self._embed_batch_source_concepts(batch)
                    self._update_embedded_concepts_table(batch, "source_concepts")

        finally:
            print("Re-enabling indexing...")
            self._toggle_indexing(enable=True)

    def _embed_batch_from_dataframe(
        self, batch_df, content_col: str, metadata_cols: list
    ):
        """Embed a batch of documents from dataframe"""
        texts = batch_df[content_col].tolist()
        embeddings = self.emb_model.embed(texts)

        points = []
        for idx, row in batch_df.iterrows():
            metadata = {col: row[col] for col in metadata_cols}

            point = models.PointStruct(
                id=int(
                    row.get("concept_id", idx)
                ),  # Use concept_id if available, otherwise index
                vector=embeddings[idx - batch_df.index[0]],
                payload={"text": row[content_col], "metadata": metadata},
            )
            points.append(point)

        self.client.upsert(collection_name=self.name, points=points)

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
            }

            # Add ATC7 codes if available
            if atc7_codes:
                # Store ATC7 codes as an array for filtering
                normalized_atc_codes = []
                for atc7 in atc7_codes:
                    if len(atc7) >= 7:
                        normalized_atc_codes.append(atc7[:7])
                    else:
                        normalized_atc_codes.append(atc7)

                metadata["atc7_codes"] = normalized_atc_codes
                # Keep the original array for reference
                metadata["atc7_codes_original"] = atc7_codes

            point = models.PointStruct(
                id=concept_id,
                vector=embeddings[i],
                payload={"text": concept_name, "metadata": metadata},
            )
            points.append(point)

        self.client.upsert(collection_name=self.name, points=points)

    def _embed_batch_source_concepts(self, batch):
        """Embed a batch of source concepts"""
        texts = [row[2] for row in batch]  # source_concept_name is at index 2
        embeddings = self.emb_model.embed(texts)

        points = []
        for i, row in enumerate(batch):
            source_id, source_value, source_concept_name, source_vocabulary_id = row

            point = models.PointStruct(
                id=self._source_id_to_vector_id(source_id),
                vector=embeddings[i],
                payload={
                    "text": source_concept_name,
                    "metadata": {
                        "source_id": source_id,
                        "source_value": source_value,
                        "source_concept_name": source_concept_name,
                        "source_vocabulary_id": source_vocabulary_id,
                        "type": "source",
                    },
                },
            )
            points.append(point)

        self.client.upsert(collection_name=self.name, points=points)

    def _update_embedded_concepts_table(self, batch, table_type):
        """Update the embedded_concepts table to track what has been embedded"""

        values = []
        if table_type == "standard_concepts":
            for row in batch:
                concept_id = row[0]
                values.append(
                    (
                        concept_id,
                        self.name,
                        self.emb_model.model_name,
                        datetime.now(),
                        "standard",
                        None,
                    )
                )
        else:  # source_concepts
            for row in batch:
                source_id = row[0]
                source_vocabulary_id = row[3]  # source_vocabulary_id is at index 3
                values.append(
                    (
                        source_id,
                        self.name,
                        self.emb_model.model_name,
                        datetime.now(),
                        "source",
                        source_vocabulary_id,
                    )
                )

        with closing(self.conn.cursor()) as cursor:
            cursor.executemany(
                """
                INSERT INTO embedded_concepts (concept_id, collection_name, embedding_model, embedded_at, concept_type, source_vocabulary_id) 
                VALUES (%s, %s, %s, %s, %s, %s) 
                ON CONFLICT (concept_id, collection_name, concept_type) DO UPDATE SET 
                    embedding_model = EXCLUDED.embedding_model, 
                    embedded_at = EXCLUDED.embedded_at,
                    source_vocabulary_id = EXCLUDED.source_vocabulary_id
                """,
                values,
            )
            self.conn.commit()

    def _format_results(self, results):
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

    def _init_emb_model(self, emb_model_str: str, emb_dims: int):
        emb_model = EmbeddingModel(emb_model_str, emb_dims)
        return emb_model

    def _init_client(self, url: str):
        client = QdrantClient(url=url, timeout=500)
        return client

    def _init_db(self):
        emb_size = len(self.emb_model.embed("test")[0])

        if not self.client.collection_exists(self.name):
            self.client.create_collection(
                collection_name=self.name,
                vectors_config=models.VectorParams(
                    size=emb_size, distance=models.Distance.COSINE, on_disk=True
                ),
                hnsw_config=models.HnswConfigDiff(m=0),
            )

            print("Vector store created")

    def _create_filters(self, filter_dict: dict):
        if not filter_dict:
            return

        filters = []
        for k, v in filter_dict.items():
            if k == "atc7_codes":
                # Special handling for ATC7 codes array filtering
                # Check if any of the provided ATC codes are in the document's ATC codes array
                if isinstance(v, list):
                    # Use MatchAny to check if any of the provided ATC codes
                    # are present in the document's ATC codes array
                    filters.append(
                        models.FieldCondition(
                            key=f"metadata.{k}", match=models.MatchAny(any=v)
                        )
                    )
                else:
                    # Single ATC code
                    filters.append(
                        models.FieldCondition(
                            key=f"metadata.{k}", match=models.MatchValue(value=v)
                        )
                    )
            else:
                # Regular filtering
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

    def create_new_collection(self, collection_name: str, vector_size: int):
        """Create a new vector collection"""
        if self.client.collection_exists(collection_name):
            return False  # Collection already exists

        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size, distance=models.Distance.COSINE, on_disk=True
            ),
            hnsw_config=models.HnswConfigDiff(m=0),
        )
        return True

    def get_collections(self):
        try:
            collections = self.client.get_collections()
            return [collection.name for collection in collections.collections]
        except Exception:
            return []

    def switch_collection(self, new_collection_name: str):
        self.name = new_collection_name
        # Re-initialize to ensure collection exists
        self._init_db()

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
            return None

    def delete_collection(self, collection_name: str):
        """Delete a collection"""
        try:
            return self.client.delete_collection(collection_name)
        except Exception:
            return False

    def search_by_atc_codes(self, atc7_codes: list, k: int = 100):
        """Search for concepts that have any of the specified ATC7 codes"""
        if not atc7_codes:
            return []

        # Normalize ATC codes to 7 characters
        normalized_atc_codes = []
        for atc7 in atc7_codes:
            if len(atc7) >= 7:
                normalized_atc_codes.append(atc7[:7])
            else:
                normalized_atc_codes.append(atc7)

        # Create filter for ATC codes using MatchAny for array membership
        filters = models.Filter(
            must=[
                models.FieldCondition(
                    key="metadata.atc7_codes",
                    match=models.MatchAny(any=normalized_atc_codes),
                )
            ]
        )

        # Search without query vector (scroll through all matching documents)
        results = self.client.scroll(
            collection_name=self.name, scroll_filter=filters, limit=k, with_payload=True
        )

        return results[0]  # Return the points, not the next_page_offset

    def get_embedding_status(self):
        """Get the status of embeddings for the current collection"""
        with closing(self.conn.cursor()) as cursor:
            # Count total standard concepts
            cursor.execute("SELECT COUNT(*) FROM concept WHERE standard_concept = 'S'")
            total_standard = cursor.fetchone()[0]

            # Count embedded standard concepts
            cursor.execute(
                """
                SELECT COUNT(*) FROM embedded_concepts 
                WHERE collection_name = %s 
                AND concept_type = 'standard'
                AND concept_id IN (SELECT concept_id FROM concept WHERE standard_concept = 'S')
            """,
                (self.name,),
            )
            embedded_standard = cursor.fetchone()[0]

            # Count total source concepts
            cursor.execute("SELECT COUNT(*) FROM source_concepts WHERE mapped = FALSE")
            total_source = cursor.fetchone()[0]

            # Count embedded source concepts
            cursor.execute(
                """
                SELECT COUNT(*) FROM embedded_concepts 
                WHERE collection_name = %s 
                AND concept_type = 'source'
                AND concept_id IN (SELECT source_id FROM source_concepts WHERE mapped = FALSE)
            """,
                (self.name,),
            )
            embedded_source = cursor.fetchone()[0]

            return {
                "standard_concepts": {
                    "total": total_standard,
                    "embedded": embedded_standard,
                    "pending": total_standard - embedded_standard,
                },
                "source_concepts": {
                    "total": total_source,
                    "embedded": embedded_source,
                    "pending": total_source - embedded_source,
                },
            }

    def check_concept_already_embedded(self, concept_id: int):
        """Check if a specific concept is already embedded in the current collection"""
        with closing(self.conn.cursor()) as cursor:
            cursor.execute(
                """
                SELECT embedded_at FROM embedded_concepts 
                WHERE concept_id = %s AND collection_name = %s
            """,
                (concept_id, self.name),
            )
            result = cursor.fetchone()
            return result is not None

    def _toggle_indexing(self, enable: bool):
        if enable:
            m = 16
        else:
            m = 0

        self.client.update_collection(
            collection_name=self.name,
            hnsw_config=models.HnswConfigDiff(m=m),
        )

    def _ensure_schema_compatibility(self):
        """Ensure database schema is compatible with current version"""
        pass  # Schema compatibility is now handled by seed.sql

    @staticmethod
    def _source_id_to_vector_id(source_id: int) -> int:
        """Convert source concept ID to vector database ID"""
        return 1000000000 + source_id

    @staticmethod
    def _vector_id_to_source_id(vector_id: int) -> int:
        """Convert vector database ID back to source concept ID"""
        if vector_id >= 1000000000:
            return vector_id - 1000000000
        return vector_id  # Standard concept ID

    @staticmethod
    def _is_source_concept_id(vector_id: int) -> bool:
        """Check if vector ID represents a source concept"""
        return vector_id >= 1000000000
