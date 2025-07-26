#!/usr/bin/env python3
"""
Tests for vector store functionality
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

# Patch the database connection before any imports
with patch("src.backend.db.core.init_connection"):
    from src.backend.llms.vector_store import VectorDatabase


class TestVectorStore(unittest.TestCase):
    """Test vector database functionality"""

    @patch("src.backend.db.core.init_connection")
    @patch("streamlit.cache_data")
    @patch("streamlit.cache_resource")
    @patch("src.backend.llms.vector_store.QdrantClient")
    def setUp(
        self, mock_qdrant, mock_cache_resource, mock_cache_data, mock_init_connection
    ):
        """Set up test fixtures"""
        # Mock the database connection
        mock_init_connection.return_value = MagicMock()

        # Set up mocks
        self.mock_client = MagicMock()
        mock_qdrant.return_value = self.mock_client

        # Mock embedding model
        self.mock_emb_model = MagicMock()
        self.mock_emb_model.embed.return_value = [[0.1] * 384]
        self.mock_emb_model.get_model_name.return_value = "test-model"

        # Create vector database instance
        self.vector_db = VectorDatabase(
            name="test_collection",
            embedding_model=self.mock_emb_model,
            url="http://localhost:6333",
        )
        self.vector_db.client = self.mock_client

    def test_search_basic(self):
        """Test basic vector search"""
        # Mock search results
        mock_result = MagicMock()
        mock_result.points = [
            MagicMock(
                score=0.95,
                payload={
                    "text": "Aspirin",
                    "metadata": {"concept_id": 1191, "concept_name": "Aspirin"},
                },
            )
        ]
        self.mock_client.query_points.return_value = mock_result

        results = self.vector_db.search("aspirin", k=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["concept_name"], "Aspirin")
        self.assertEqual(results[0]["score"], 0.95)
        self.mock_client.query_points.assert_called_once()

    def test_create_collection(self):
        """Test collection creation"""
        self.mock_client.collection_exists.return_value = False
        self.vector_db.create_new_collection("new_collection", 384)
        self.mock_client.create_collection.assert_called_once()


if __name__ == "__main__":
    unittest.main()
