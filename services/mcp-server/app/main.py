from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP

from .config import get_settings
from .models import (
    BuildCandidateRequest,
    IndexVersion,
    PromoteRequest,
    Promotion,
    QueryRequest,
    QueryResponse,
)
from .sec import SecEdgarClient
from .service import AsOfRagService
from .state import StateRepository
from .store import QdrantStore

settings = get_settings()
sec_client = (
    SecEdgarClient(
        settings.sec_user_agent,
        settings.data_dir / "sec-cache",
        settings.sec_cache_ttl_seconds,
        settings.sec_request_interval_seconds,
        settings.sec_max_retries,
    )
    if settings.sec_user_agent
    else None
)
service = AsOfRagService(
    StateRepository(settings.data_dir),
    QdrantStore(settings.qdrant_url, settings.embedding_model),
    sec_client,
)

mcp = FastMCP("AsOfRAG")


@mcp.tool(annotations={"readOnlyHint": True})
def list_filings(
    ticker: str, forms: list[str] | None = None, limit: int = 10
) -> list[dict[str, Any]]:
    """List live SEC 10-K/10-Q filing metadata for a ticker."""
    rows = service.list_filings(ticker, tuple(forms or ["10-K", "10-Q"]), limit)
    return [row.model_dump(mode="json") for row in rows]


@mcp.tool(annotations={"readOnlyHint": True})
def get_filing_source(accession: str) -> str:
    """Return cached or live primary SEC filing HTML."""
    return service.filing_source(accession)


@mcp.tool(annotations={"readOnlyHint": True})
def query_production(
    query: str, as_of: datetime, limit: int = 5, ticker: str | None = None
) -> dict[str, Any]:
    """Query production with the mandatory point-in-time filter."""
    return service.query(query, as_of, limit, ticker).model_dump(mode="json")


@mcp.tool(annotations={"readOnlyHint": True})
def compare_retrieval(
    query: str, as_of: datetime, limit: int = 5, ticker: str | None = None
) -> dict[str, Any]:
    """Compare naive, hard as-of, production, and candidate retrieval."""
    comparison: dict[str, Any] = {
        "as_of": as_of.isoformat(),
        "production": None,
        "candidate": None,
    }
    state = service.status()
    for index_name, index_id in (
        ("production", state.production_id),
        ("candidate", state.candidate_id),
    ):
        if not index_id:
            continue
        safe = service.query(
            query, as_of, limit, ticker, index_name, temporal_filter=True
        )
        naive = service.query(
            query, as_of, limit, ticker, index_name, temporal_filter=False
        )
        comparison[index_name] = {
            "safe": safe.model_dump(mode="json"),
            "naive": naive.model_dump(mode="json"),
            "temporal_leakage_count": sum(
                hit.chunk.filed_at > as_of for hit in naive.hits
            ),
        }
    return comparison


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False})
def build_candidate(
    ticker: str,
    forms: list[str] | None = None,
    limit: int = 4,
    accession: str | None = None,
) -> dict[str, Any]:
    """Download SEC filings and build an isolated candidate index."""
    result = service.build_candidate(
        ticker, tuple(forms or ["10-K", "10-Q"]), limit, accession
    )
    return result.model_dump(mode="json")


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def promote_candidate(candidate_id: str | None = None) -> dict[str, Any]:
    """Promote a candidate by changing the production pointer; prior data is retained."""
    return service.promote(candidate_id).model_dump(mode="json")


mcp_http = mcp.http_app(path="/mcp")
app = FastAPI(
    title="AsOfRAG",
    version="0.1.0",
    lifespan=mcp_http.lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    try:
        service.store.ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Qdrant is unavailable") from exc
    return {"status": "ok"}


@app.get("/api/status")
def status() -> dict[str, Any]:
    state = service.status()
    return {
        **state.model_dump(mode="json"),
        "sec_configured": service.sec is not None,
        "embedding_model": settings.embedding_model,
    }


@app.get("/api/filings")
def filings(
    ticker: str = Query(min_length=1),
    forms: list[str] = Query(default=["10-K", "10-Q"]),
    limit: int = Query(default=10, ge=1, le=40),
) -> list[dict[str, Any]]:
    try:
        return [
            row.model_dump(mode="json")
            for row in service.list_filings(ticker, tuple(forms), limit)
        ]
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/candidates/build", response_model=IndexVersion)
def candidate_build(request: BuildCandidateRequest) -> IndexVersion:
    try:
        return service.build_candidate(
            request.ticker,
            tuple(request.forms),
            request.limit,
            request.accession,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    try:
        return service.query(
            request.query,
            request.as_of,
            request.limit,
            request.ticker,
            request.index,
            request.temporal_filter,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/promote", response_model=Promotion)
def promote(request: PromoteRequest) -> Promotion:
    try:
        return service.promote(request.candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


app.mount("/", mcp_http)
