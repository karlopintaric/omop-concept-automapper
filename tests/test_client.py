#!/usr/bin/env python3
"""
Tests for OpenAI client functionality
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))


class TestOpenAIClient(unittest.TestCase):
    """Test OpenAI client functionality"""

    @patch("streamlit.cache_data")
    @patch("streamlit.cache_resource")
    def setUp(self, mock_cache_resource, mock_cache_data):
        """Set up test fixtures"""
        pass

    def test_client_with_api_key(self):
        """Test client initialization with API key"""
        from src.backend.llms.client import OpenAIClient

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("src.backend.llms.client.OpenAI") as mock_openai:
                mock_client_instance = MagicMock()
                mock_openai.return_value = mock_client_instance

                client = OpenAIClient()
                self.assertEqual(client.get_client(), mock_client_instance)
                mock_openai.assert_called_once_with(api_key="test-key")

    def test_client_without_api_key(self):
        """Test client initialization without API key"""
        from src.backend.llms.client import OpenAIClient

        with patch.dict(os.environ, {}, clear=True):
            with patch("src.backend.llms.client.OpenAI") as mock_openai:
                mock_openai.return_value = MagicMock()

                OpenAIClient()
                mock_openai.assert_called_once_with(api_key=None)

    def test_client_singleton_behavior(self):
        """Test that client behaves correctly across multiple instantiations"""
        from src.backend.llms.client import OpenAIClient

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("src.backend.llms.client.OpenAI") as mock_openai:
                mock_client_instance = MagicMock()
                mock_openai.return_value = mock_client_instance

                client1 = OpenAIClient()
                client2 = OpenAIClient()

                # Both should have the same underlying client
                self.assertEqual(client1.get_client(), client2.get_client())


if __name__ == "__main__":
    unittest.main()
