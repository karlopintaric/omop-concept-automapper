from pydantic import BaseModel, Field


class RerankerResponse(BaseModel):
    """
    Represents the response from a reranker model, containing the most similar item ID
    and a confidence score indicating the quality of the match.
    """

    most_similar_item_id: int
    confidence_score: int = Field(..., ge=1, le=10)
