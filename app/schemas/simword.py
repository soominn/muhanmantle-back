from typing import Union

from pydantic import BaseModel


class TotalCountResponse(BaseModel):
    total_count: int


class SimilarityItem(BaseModel):
    word: str
    similarity_percentage: float
    rank: int


class AnswerWordDetailResponse(BaseModel):
    id: int
    answer_word: str
    top_500_similarities: list[SimilarityItem]


class SimilarityResponse(BaseModel):
    id: int
    input_word: str
    similarity_percentage: float
    # int (1-500), "순위 밖", "?", or "정답!"
    rank: Union[int, str]


class HealthResponse(BaseModel):
    status: str
