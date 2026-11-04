import re
import threading
import uuid
from datetime import date, datetime

from .models import (
    Evaluation,
    Filing,
    FilingReference,
    IndexVersion,
    PersistentState,
    Promotion,
    QueryResponse,
)
from .parser import filing_content_hash, parse_filing
from .sec import SecEdgarClient, SecFilingRef
from .state import StateRepository
from .store import QdrantStore


class AsOfRagService:
    def __init__(
        self,
        state: StateRepository,
        store: QdrantStore,
        sec: SecEdgarClient | None,
    ):
        self.state = state
        self.store = store
        self.sec = sec
        self._build_lock = threading.Lock()

    def status(self) -> PersistentState:
        return self.state.load()

    def list_filings(
        self, ticker: str, forms: tuple[str, ...] = ("10-K", "10-Q"), limit: int = 10
    ) -> list[SecFilingRef]:
        if self.sec is None:
            raise RuntimeError("SEC client is unavailable; configure SEC_USER_AGENT")
        rows = self.sec.list_filings(ticker, forms, limit)
        state = self.state.load()
        for row in rows:
            state.filing_references[row.accession] = FilingReference(
                **row.model_dump()
            )
        self.state.save(state)
        return rows

    def filing_source(self, accession: str) -> str:
        if self.sec is None:
            raise RuntimeError("SEC client is unavailable; configure SEC_USER_AGENT")
        cached = self.sec.cached_source(accession)
        if cached is not None:
            return cached
        state = self.state.load()
        reference = state.filing_references.get(accession)
        if reference is None:
            filing = state.filings.get(accession)
            if filing is not None:
                reference = FilingReference(
                    ticker=filing.ticker,
                    cik=filing.cik,
                    accession=filing.accession,
                    form=filing.form,
                    report_date=filing.report_date,
                    filed_at=filing.filed_at,
                    primary_document=str(filing.source_url).rsplit("/", 1)[-1],
                    source_url=filing.source_url,
                )
        if reference is None:
            raise ValueError(f"Unknown filing accession: {accession}")
        sec_reference = SecFilingRef(
            ticker=reference.ticker,
            cik=reference.cik,
            accession=reference.accession,
            form=reference.form,
            report_date=reference.report_date.isoformat(),
            filed_at=reference.filed_at,
            primary_document=reference.primary_document,
            source_url=reference.source_url,
        )
        return self.sec.download_filing(sec_reference).decode("utf-8", errors="replace")

    @staticmethod
    def _lineage(
        state: PersistentState, reference: SecFilingRef, content_hash: str
    ) -> tuple[int, str | None]:
        related = [
            filing
            for filing in state.filings.values()
            if filing.ticker == reference.ticker
            and filing.form == reference.form
            and filing.report_date == date.fromisoformat(reference.report_date)
        ]
        if not related:
            return 1, None
        latest = max(related, key=lambda filing: filing.version)
        if latest.content_hash == content_hash:
            return latest.version, latest.parent_content_hash
        return latest.version + 1, latest.content_hash

    def build_candidate(
        self,
        ticker: str,
        forms: tuple[str, ...] = ("10-K", "10-Q"),
        limit: int = 4,
        accession: str | None = None,
    ) -> IndexVersion:
        if self.sec is None:
            raise RuntimeError("SEC client is unavailable; configure SEC_USER_AGENT")
        with self._build_lock:
            discovery_limit = max(limit, 40) if accession else limit
            references = self.sec.list_filings(ticker, forms, discovery_limit)
            if accession:
                references = [
                    reference
                    for reference in references
                    if reference.accession == accession
                ]
            else:
                references = references[:limit]
            if not references:
                suffix = f" and accession {accession}" if accession else ""
                raise ValueError(f"No matching SEC filings found for {ticker}{suffix}")
            state = self.state.load()
            chunks = []
            accessions: list[str] = []
            filings: dict[str, Filing] = {}
            for reference in references:
                html = self.sec.download_filing(reference)
                digest = filing_content_hash(html)
                version, parent_hash = self._lineage(state, reference, digest)
                filing = Filing(
                    ticker=reference.ticker,
                    cik=reference.cik,
                    accession=reference.accession,
                    form=reference.form,
                    report_date=date.fromisoformat(reference.report_date),
                    filed_at=reference.filed_at,
                    source_url=reference.source_url,
                    content_hash=digest,
                    version=version,
                    parent_content_hash=parent_hash,
                )
                parsed = parse_filing(html, filing)
                if not parsed:
                    raise ValueError(f"No readable content in filing {reference.accession}")
                chunks.extend(parsed)
                accessions.append(reference.accession)
                filings[reference.accession] = filing

            index_id = str(uuid.uuid4())
            safe_ticker = re.sub(r"[^A-Z0-9]+", "_", ticker.strip().upper())
            collection = f"asof_candidate_{safe_ticker}_{index_id.replace('-', '')}"
            self.store.create_collection(collection, chunks)
            index = IndexVersion(
                id=index_id,
                collection_name=collection,
                ticker=safe_ticker,
                filing_accessions=accessions,
                chunk_count=len(chunks),
                parent_index_id=state.production_id,
                evaluation=Evaluation(
                    notes=[
                        "Required provenance validated for every chunk.",
                        "Temporal eligibility is enforced by Qdrant before ranking.",
                    ]
                ),
            )
            state.indexes[index.id] = index
            state.candidate_id = index.id
            state.filings.update(filings)
            self.state.save(state)
            return index

    def query(
        self,
        text: str,
        as_of: datetime,
        limit: int = 5,
        ticker: str | None = None,
        index: str = "production",
        temporal_filter: bool = True,
    ) -> QueryResponse:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must include a timezone")
        state = self.state.load()
        index_id = state.production_id if index == "production" else state.candidate_id
        if not index_id or index_id not in state.indexes:
            raise ValueError(f"No {index} index is available")
        version = state.indexes[index_id]
        hits = self.store.query(
            version.collection_name,
            text,
            as_of,
            limit,
            ticker,
            temporal_filter=temporal_filter,
        )
        return QueryResponse(
            index_id=index_id,
            collection_name=version.collection_name,
            temporal_filter_applied=temporal_filter,
            hits=hits,
        )

    def promote(self, candidate_id: str | None = None) -> Promotion:
        return self.state.promote(candidate_id)
