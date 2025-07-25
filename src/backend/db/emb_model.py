from openai import OpenAI
import time
from src.backend.utils.logging import logger


class EmbeddingModel:
    def __init__(self, model: str, dims: int | None = None, num_retries: int = 3):
        self.model = model
        self.model_name = model
        self.client = self._init_client()
        self.dims = dims
        self.num_retries = num_retries

    def _init_client(
        self,
    ):
        try:
            client = OpenAI()
        except Exception as e:
            logger.error("Error initializing OpenAI client", exc_info=True)
            raise

        return client

    def _create_embeddings(self, text):
        response = self.client.embeddings.create(
            model=self.model, input=text, dimensions=self.dims
        )

        embeddings = [emb.embedding for emb in response.data]

        return embeddings

    def embed(self, text):
        for attempt in range(1, self.num_retries + 1):
            try:
                return self._create_embeddings(text)
            except Exception as e:
                logger.error(
                    f"Error creating embeddings (attempt {attempt}/{self.num_retries})",
                    exc_info=True,
                )
                if attempt < self.num_retries:
                    time.sleep(3)
                else:
                    raise RuntimeError(
                        f"Failed to create embeddings after {self.num_retries} retries."
                    ) from e
