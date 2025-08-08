from abc import ABC, abstractmethod
from typing import TypeVar, Generic
from pydantic import BaseModel

from src.backend.llms.client import LLMClient
from openai import OpenAI
from src.backend.utils.logging import logger


T = TypeVar("T")


class ChatModel(ABC, Generic[T]):
    def __init__(self, model: str, client: LLMClient[T]):
        self.model = model
        self.client: T = client.get_client()

    @abstractmethod
    def chat(
        self,
        input_text: str,
        system_prompt: str,
        output_schema: type[BaseModel] | None = None,
    ) -> BaseModel | str:
        pass


class ChatModelWithStructuredOutput(ChatModel[OpenAI]):
    def chat(
        self,
        input_text: str,
        system_prompt: str | None = None,
        output_schema: BaseModel | None = None,
    ):
        logger.info(f"🔗 Sending chat request to OpenAI model: {self.model}")

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": input_text},
            ]

            response = self.client.chat.completions.parse(
                model=self.model,
                messages=messages,
                response_format=output_schema,
                temperature=0
            )

            logger.info("🔗 API call successful, response received")
            parsed_response = response.choices[0].message.parsed

            return parsed_response

        except Exception as e:
            logger.error("❌ API call failed", exc_info=True)
            raise
