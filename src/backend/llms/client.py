import os
from typing import Protocol, TypeVar
from openai import OpenAI
from src.backend.utils.logging import logger

T = TypeVar("T")


class LLMClient(Protocol[T]):
    def get_client(self) -> T: ...


class OpenAIClient(LLMClient[OpenAI]):
    """A client for interacting with OpenAI's API."""

    def __init__(self):
        self._client: OpenAI = self._init_client()

    def _init_client(self) -> OpenAI:
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            logger.warning("⚠️ WARNING: OPENAI_API_KEY environment variable not set!")
        else:
            logger.info("✅ OpenAI API key found")

        try:
            client = OpenAI(api_key=api_key)
            logger.info("OpenAI client initialized successfully")
            return client
        except Exception as e:
            logger.error("❌ Error initializing OpenAI client", exc_info=True)
            raise RuntimeError("Failed to initialize OpenAI client") from e

    def get_client(self) -> OpenAI:
        return self._client
