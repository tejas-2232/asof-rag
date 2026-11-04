from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class Filing(BaseModel):
    ticker: str
    cik: str
    accession: str
    form: Literal["10-K", "10-Q"]
    report_date: date
    filed_at: datetime
    source_url: HttpUrl
    content_hash: str
    version: int = 1
    parent_content_hash: str | None = None


class FilingReference(BaseModel):
    ticker: str
    cik: str
    accession: str
    form: Literal["10-K", "10-Q"]
    report_date: date
    filed_at: datetime
    primary_document: str
    source_url: HttpUrl


class Chunk(BaseModel):
    id: str
    filing_id: str
    ticker: str
    cik: str
    accession: str
    form: str
    report_date: date
    filed_at: datetime
    filed_at_epoch: int
    source_url: HttpUrl
    content_hash: str
    filing_content_hash: str
    version: int
    parent_content_hash: str | None = None
    section: str
    ordinal: int
    text: str


class Evaluation(BaseModel):
    checked_at: datetime = Field(default_factory=utc_now)
    temporal_violations: int = 0
    notes: list[str] = Field(default_factory=list)


class IndexVersion(BaseModel):
    id: str
    collection_name: str
    stage: Literal["candidate", "production", "retired"] = "candidate"
    created_at: datetime = Field(default_factory=utc_now)
    ticker: str
    filing_accessions: list[str]
    chunk_count: int
    parent_index_id: str | None = None
    evaluation: Evaluation = Field(default_factory=Evaluation)


class Promotion(BaseModel):
    candidate_id: str
    previous_production_id: str | None = None
    promoted_at: datetime = Field(default_factory=utc_now)


class PersistentState(BaseModel):
    candidate_id: str | None = None
    production_id: str | None = None
    indexes: dict[str, IndexVersion] = Field(default_factory=dict)
    filings: dict[str, Filing] = Field(default_factory=dict)
    filing_references: dict[str, FilingReference] = Field(default_factory=dict)
    promotions: list[Promotion] = Field(default_factory=list)


class BuildCandidateRequest(BaseModel):
    ticker: str
    forms: list[Literal["10-K", "10-Q"]] = Field(
        default_factory=lambda: ["10-K", "10-Q"]
    )
    limit: int = Field(default=4, ge=1, le=40)
    accession: str | None = None


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    as_of: datetime
    limit: int = Field(default=5, ge=1, le=25)
    ticker: str | None = None
    index: Literal["production", "candidate"] = "production"
    temporal_filter: bool = True

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must include a timezone")
        return value


class QueryHit(BaseModel):
    score: float
    chunk: Chunk


class QueryResponse(BaseModel):
    index_id: str
    collection_name: str
    temporal_filter_applied: bool
    hits: list[QueryHit]


class PromoteRequest(BaseModel):
    candidate_id: str | None = None
