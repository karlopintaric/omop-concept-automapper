#!/usr/bin/env python3
"""
Tests for embedding model functionality
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))


class TestEmbeddingModel(unittest.TestCase):
    """Test embedding model functionality"""

    @patch("streamlit.cache_data")
    @patch("streamlit.cache_resource")
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("src.backend.llms.client.OpenAI")
    def setUp(self, mock_openai, mock_cache_resource, mock_cache_data):
        """Set up test fixtures"""
        from src.backend.llms.emb_model import OpenAIEmbeddingModel
        from src.backend.llms.client import OpenAIClient

        self.mock_openai_client = MagicMock()
        mock_openai.return_value = self.mock_openai_client

        # Mock embedding response
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1] * 384
        mock_response = MagicMock()
        mock_response.data = [mock_embedding]
        self.mock_openai_client.embeddings.create.return_value = mock_response

        client = OpenAIClient()
        self.embedding_model = OpenAIEmbeddingModel(
            model="text-embedding-3-small", client=client, dims=384
        )

    def test_embed_single_text(self):
        """Test embedding single text"""
        embeddings = self.embedding_model.embed("aspirin tablet")

        self.assertIsInstance(embeddings, list)
        self.assertEqual(len(embeddings), 1)
        self.assertEqual(len(embeddings[0]), 384)
        self.mock_openai_client.embeddings.create.assert_called_once()

    def test_embed_multiple_texts(self):
        """Test embedding multiple texts"""
        texts = ["aspirin tablet", "ibuprofen capsule", "acetaminophen pill"]

        # Mock multiple embeddings response
        mock_embeddings = [MagicMock() for _ in texts]
        for mock_emb in mock_embeddings:
            mock_emb.embedding = [0.1] * 384
        mock_response = MagicMock()
        mock_response.data = mock_embeddings
        self.mock_openai_client.embeddings.create.return_value = mock_response

        embeddings = self.embedding_model.embed(texts)

        self.assertIsInstance(embeddings, list)
        self.assertEqual(len(embeddings), 3)
        for embedding in embeddings:
            self.assertEqual(len(embedding), 384)
        self.mock_openai_client.embeddings.create.assert_called_once()

    def test_get_model_name(self):
        """Test model name retrieval"""
        self.assertEqual(
            self.embedding_model.get_model_name(), "text-embedding-3-small"
        )

    def test_get_dimensions(self):
        """Test dimension retrieval"""
        self.assertEqual(self.embedding_model.dims, 384)


if __name__ == "__main__":
    unittest.main()
