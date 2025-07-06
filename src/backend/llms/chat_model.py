from openai import OpenAI
from pydantic import BaseModel


class ChatModelWithStructuredOutput:
    def __init__(
        self,
        model: str,
        system_prompt: str,
        output_schema: BaseModel,
    ):
        self.model = model
        self.client = self._init_client()
        self.system_prompt = system_prompt
        self.output_schema = output_schema

    def _init_client(
        self,
    ):
        import os

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("⚠️ WARNING: OPENAI_API_KEY environment variable not set!")
            print("⚠️ LLM calls will fail without this API key")
        else:
            print("✅ OpenAI API key found")

        client = OpenAI()
        return client

    def chat(self, input_text):
        print(f"🔗 Making API call to {self.model}")
        print(f"🔗 Input text length: {len(input_text)} characters")

        try:
            response = self.client.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": input_text},
                ],
                response_format=self.output_schema,
            )

            print("🔗 API call successful, response received")
            parsed_response = response.choices[0].message.parsed
            print(f"🔗 Parsed response: {parsed_response}")

            return parsed_response

        except Exception as e:
            print(f"❌ API call failed: {str(e)}")
            print(f"❌ Error type: {type(e).__name__}")
            raise e
