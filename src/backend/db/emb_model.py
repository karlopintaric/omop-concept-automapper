from openai import OpenAI
import time


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
        client = OpenAI()
        return client

    def _create_embeddings(self, text):
        response = self.client.embeddings.create(
            model=self.model, input=text, dimensions=self.dims
        )

        embeddings = [emb.embedding for emb in response.data]

        return embeddings

    def embed(self, text):
        for i in range(self.num_retries):
            try:
                return self._create_embeddings(text)
            except Exception:
                print(
                    "Error creating embeddings. Retrying...",
                )
                time.sleep(3)

        raise Exception(
            f"Failed to create embeddings after {self.num_retries} retries."
        )
