from src.backend.llms.chat_model import ChatModel
from src.backend.llms.output_models import RerankerResponse
from src.backend.llms.prompt import (
    DRUG_SYSTEM_PROMPT,
    CONCEPT_SYSTEM_PROMPT,
    INPUT_PROMPT,
)
from src.backend.utils.logging import logger


class Reranker:
    def __init__(
        self,
        chat_model: ChatModel,
        drug_specific: bool = False,
    ):
        self.system_prompt = (
            DRUG_SYSTEM_PROMPT if drug_specific else CONCEPT_SYSTEM_PROMPT
        )
        self.llm = chat_model
        self.input_prompt = INPUT_PROMPT

    def select_similar(self, input_term: str, candidate_list: list[dict]) -> dict:
        logger.info(f"🤖 Reranker called with input: '{input_term}'")

        candidate_list_str = self._format_item_list_for_prompt(candidate_list)
        input_text = self.input_prompt.format(
            input_term=input_term, candidate_list=candidate_list_str
        )

        try:
            response = self.llm.chat(
                input_text=input_text,
                system_prompt=self.system_prompt,
                output_schema=RerankerResponse,  # Pass your structured output model here
            )
            logger.info(f"🤖 LLM response: {response}")

            result = self._select_similar_with_confidence(response, candidate_list)

            return result
        except Exception as e:
            print(f"❌ Error in reranker: {str(e)}")
            # Return first candidate with low confidence as fallback
            return (
                {"selected": candidate_list[0], "confidence_score": 1}
                if candidate_list
                else None
            )

    def _select_similar_with_confidence(
        self, response: RerankerResponse, candidate_list: list
    ) -> dict:
        selected_id = int(response.most_similar_item_id)
        confidence = response.confidence_score

        return {
            "selected": candidate_list[selected_id],
            "confidence_score": confidence,
        }

    def _format_item_list_for_prompt(self, item_list: list[dict]):
        items = []

        for i, item in enumerate(item_list):
            item_str = f"{i}: {item['concept_name']}"
            items.append(item_str)

        return "\n".join(items)
