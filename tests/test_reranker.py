#!/usr/bin/env python3
"""
Tests for reranker functionality
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))


class TestReranker(unittest.TestCase):
    """Test reranker functionality"""

    @patch("streamlit.cache_data")
    @patch("streamlit.cache_resource")
    def setUp(self, mock_cache_resource, mock_cache_data):
        """Set up test fixtures"""
        from src.backend.llms.reranker import Reranker
        from src.backend.llms.output_models import RerankerResponse

        self.mock_chat_model = MagicMock()
        self.mock_chat_model.chat.return_value = RerankerResponse(
            most_similar_item_id=0, confidence_score=8
        )
        self.reranker = Reranker(chat_model=self.mock_chat_model, drug_specific=False)

        self.sample_candidates = [
            {"concept_id": 1191, "concept_name": "Aspirin"},
            {"concept_id": 1124300, "concept_name": "Ibuprofen"},
        ]

    def test_select_similar(self):
        """Test concept selection"""
        result = self.reranker.select_similar("aspirin tablet", self.sample_candidates)

        self.assertIn("selected", result)
        self.assertIn("confidence_score", result)
        self.assertEqual(result["selected"]["concept_name"], "Aspirin")
        self.assertEqual(result["confidence_score"], 8)
        self.mock_chat_model.chat.assert_called_once()

    def test_empty_candidates(self):
        """Test with empty candidate list"""
        result = self.reranker.select_similar("test", [])
        self.assertIsNone(result)

    def test_drug_specific_reranker(self):
        """Test drug-specific reranker configuration"""
        from src.backend.llms.reranker import Reranker

        drug_reranker = Reranker(chat_model=self.mock_chat_model, drug_specific=True)
        # Test that drug_specific parameter is accepted during initialization
        # The actual behavior would depend on the implementation
        self.assertIsInstance(drug_reranker, Reranker)

    def test_single_candidate(self):
        """Test reranking with single candidate"""
        single_candidate = [{"concept_id": 1191, "concept_name": "Aspirin"}]
        result = self.reranker.select_similar("aspirin", single_candidate)

        self.assertIsNotNone(result)
        self.assertEqual(result["selected"]["concept_name"], "Aspirin")


if __name__ == "__main__":
    unittest.main()
