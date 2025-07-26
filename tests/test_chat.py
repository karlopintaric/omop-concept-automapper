#!/usr/bin/env python3
"""
Tests for chat model functionality
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))


class TestChatModel(unittest.TestCase):
    """Test chat model functionality"""

    @patch("streamlit.cache_data")
    @patch("streamlit.cache_resource")
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("src.backend.llms.client.OpenAI")
    def setUp(self, mock_openai, mock_cache_resource, mock_cache_data):
        """Set up test fixtures"""
        from src.backend.llms.chat_model import ChatModelWithStructuredOutput
        from src.backend.llms.client import OpenAIClient
        from src.backend.llms.output_models import RerankerResponse

        self.mock_openai_client = MagicMock()
        mock_openai.return_value = self.mock_openai_client

        # Mock chat response
        mock_message = MagicMock()
        mock_message.parsed = RerankerResponse(
            most_similar_item_id=1, confidence_score=9
        )
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        self.mock_openai_client.chat.completions.parse.return_value = mock_response

        client = OpenAIClient()
        self.chat_model = ChatModelWithStructuredOutput(
            model="gpt-4o-mini", client=client
        )

    def test_chat_with_structured_output(self):
        """Test chat with structured output"""
        from src.backend.llms.output_models import RerankerResponse

        response = self.chat_model.chat(
            input_text="Which is most similar?",
            system_prompt="You are a mapper.",
            output_schema=RerankerResponse,
        )

        self.assertIsInstance(response, RerankerResponse)
        self.assertEqual(response.most_similar_item_id, 1)
        self.assertEqual(response.confidence_score, 9)
        self.mock_openai_client.chat.completions.parse.assert_called_once()

    def test_chat_model_name(self):
        """Test chat model name"""
        self.assertEqual(self.chat_model.model, "gpt-4o-mini")


if __name__ == "__main__":
    unittest.main()
