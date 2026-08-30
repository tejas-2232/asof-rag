import json
import threading
import time
from datetime import UTC, datetime
from datetime import time as day_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, HttpUrl


class SecFilingRef(BaseModel):
    ticker: str
    cik: str
    accession: str
    form: str
    report_date: str
    filed_at: datetime
    primary_document: str
    source_url: HttpUrl


class SecEdgarClient:
    data_base = "https://data.sec.gov"
    archive_base = "https://www.sec.gov/Archives/edgar/data"
    ticker_url = "https://www.sec.gov/files/company_tickers.json"

    def __init__(
        self,
        user_agent: str,
        cache_dir: Path,
        cache_ttl_seconds: int = 86_400,
        request_interval_seconds: float = 0.12,
        max_retries: int = 4,
        client: httpx.Client | None = None,
    ):
        if not user_agent.strip():
            raise ValueError("SEC_USER_AGENT is required for SEC EDGAR requests")
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = cache_ttl_seconds
        self.interval = request_interval_seconds
        self.max_retries = max_retries
        self.client = client or httpx.Client(
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
            timeout=30,
            follow_redirects=True,
        )
        self._request_lock = threading.Lock()
        self._last_request = 0.0

    def _cache_path(self, key: str) -> Path:
        safe = "".join(character if character.isalnum() else "_" for character in key)
        return self.cache_dir / safe

    def _get(self, url: str, cache_key: str, *, immutable: bool = False) -> bytes:
        path = self._cache_path(cache_key)
        if path.exists() and (
            immutable or time.time() - path.stat().st_mtime <= self.cache_ttl
        ):
            return path.read_bytes()

        error: Exception | None = None
        for attempt in range(self.max_retries):
            with self._request_lock:
                delay = self.interval - (time.monotonic() - self._last_request)
                if delay > 0:
                    time.sleep(delay)
                try:
                    response = self.client.get(url)
                    self._last_request = time.monotonic()
                    response.raise_for_status()
                    path.write_bytes(response.content)
                    return response.content
                except (httpx.HTTPError, OSError) as exc:
                    self._last_request = time.monotonic()
                    error = exc
            if attempt + 1 < self.max_retries:
                time.sleep(min(2**attempt, 8))
        raise RuntimeError(
            f"SEC request failed after {self.max_retries} attempts: {url}"
        ) from error

    def _json(self, url: str, cache_key: str) -> dict[str, Any]:
        try:
            return json.loads(self._get(url, cache_key))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"SEC returned invalid JSON for {url}") from exc

    def resolve_cik(self, ticker: str) -> str:
        normalized = ticker.strip().upper()
        rows = self._json(
            self.ticker_url,
            "company_tickers.json",
        )
        for row in rows.values():
            if str(row["ticker"]).upper() == normalized:
                return str(row["cik_str"]).zfill(10)
        raise ValueError(f"Unknown SEC ticker: {normalized}")

    @staticmethod
    def _filed_at(recent: dict[str, list[Any]], position: int) -> datetime:
        accepted = recent.get("acceptanceDateTime", [])
        if position < len(accepted) and accepted[position]:
            value = str(accepted[position])
            if "-" in value or "T" in value:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            else:
                parsed = datetime.strptime(value[:14], "%Y%m%d%H%M%S")
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=ZoneInfo("America/New_York"))
            return parsed.astimezone(UTC)
        filed_date = datetime.fromisoformat(str(recent["filingDate"][position])).date()
        return datetime.combine(filed_date, day_time.max, tzinfo=UTC)

    def list_filings(
        self,
        ticker: str,
        forms: tuple[str, ...] = ("10-K", "10-Q"),
        limit: int = 10,
    ) -> list[SecFilingRef]:
        ticker = ticker.strip().upper()
        cik = self.resolve_cik(ticker)
        submission = self._json(
            f"{self.data_base}/submissions/CIK{cik}.json",
            f"submissions_{cik}.json",
        )
        recent = submission["filings"]["recent"]
        filings: list[SecFilingRef] = []
        for position, form in enumerate(recent["form"]):
            if form not in forms:
                continue
            accession = recent["accessionNumber"][position]
            primary_document = recent["primaryDocument"][position]
            compact_accession = accession.replace("-", "")
            source_url = (
                f"{self.archive_base}/{int(cik)}/{compact_accession}/{primary_document}"
            )
            filings.append(
                SecFilingRef(
                    ticker=ticker,
                    cik=cik,
                    accession=accession,
                    form=form,
                    report_date=recent["reportDate"][position],
                    filed_at=self._filed_at(recent, position),
                    primary_document=primary_document,
                    source_url=source_url,
                )
            )
            if len(filings) >= limit:
                break
        return filings

    def download_filing(self, filing: SecFilingRef) -> bytes:
        return self._get(
            str(filing.source_url),
            f"filing_{filing.accession}.html",
            immutable=True,
        )

    def cached_source(self, accession: str) -> str | None:
        path = self._cache_path(f"filing_{accession}.html")
        return path.read_text("utf-8", errors="replace") if path.exists() else None
