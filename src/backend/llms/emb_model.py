import time
from abc import ABC, abstractmethod
from typing import TypeVar, Generic
from openai import OpenAI
from src.backend.llms.client import LLMClient
from src.backend.utils.logging import logger

T = TypeVar("T")


class EmbeddingModel(ABC, Generic[T]):
    """Base class for embedding models."""

    def __init__(self, model: str, client: LLMClient[T], dims: int | None = None):
        self.model: str = model
        self.client: T = client.get_client()
        self.dims: int | None = dims

    @abstractmethod
    def embed(self, text: str | list[str], num_retries: int = 3):
        pass

    def get_model_name(self) -> str:
        """Get the name of the embedding model."""
        return self.model


class OpenAIEmbeddingModel(EmbeddingModel[OpenAI]):
    def __init__(self, model: str, client: LLMClient[OpenAI], dims: int | None = None):
        super().__init__(model, client, dims)

    def _create_embeddings(self, text: str | list[str]):
        """Create embeddings using OpenAI's API."""

        logger.info("🔗 Creating embeddings with OpenAI API")
        response = self.client.embeddings.create(
            model=self.model, input=text, dimensions=self.dims
        )

        if not response.data:
            logger.error("❌ No embeddings returned from OpenAI API", exc_info=True)
            raise RuntimeError("No embeddings returned from OpenAI API")

        logger.info("✅ Embeddings created successfully for input")
        return [emb.embedding for emb in response.data]

    def embed(self, text: str | list[str], num_retries: int = 3):
        for attempt in range(1, num_retries + 1):
            try:
                return self._create_embeddings(text)
            except Exception as e:
                logger.error(
                    f"Error creating embeddings (attempt {attempt}/{num_retries})",
                    exc_info=True,
                )
                if attempt < num_retries:
                    time.sleep(3)
                else:
                    raise RuntimeError(
                        f"Failed to create embeddings after {num_retries} retries."
                    ) from e
