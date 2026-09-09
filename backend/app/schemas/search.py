from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchInspectRequest(BaseModel):
    """`access_roles` / `document_ids` in the body are ignored (extra=ignore)."""

    model_config = ConfigDict(extra="ignore")

    query: str = Field(..., min_length=1, max_length=4000)
    limit: int = Field(default=15, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be empty")
        return stripped


class InspectHit(BaseModel):
    chunk_id: str
    document_id: UUID
    page: int
    score: float
    snippet: str


class SearchInspectResponse(BaseModel):
    dense: list[InspectHit] = Field(default_factory=list)
    sparse: list[InspectHit] = Field(default_factory=list)
    rrf: list[InspectHit] = Field(default_factory=list)
    reranked: list[InspectHit] = Field(default_factory=list)
