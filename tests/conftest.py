import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).parents[1] / "services" / "mcp-server"
sys.path.insert(0, str(SERVICE_ROOT))

from app.models import Filing  # noqa: E402
from app.parser import filing_content_hash  # noqa: E402


@pytest.fixture
def filing_html() -> bytes:
    return (Path(__file__).parent / "fixtures" / "filing.html").read_bytes()


@pytest.fixture
def filing(filing_html: bytes) -> Filing:
    return Filing(
        ticker="ACME",
        cik="0000000001",
        accession="0000000001-24-000001",
        form="10-Q",
        report_date=date(2024, 3, 31),
        filed_at=datetime(2024, 5, 1, 20, 30, tzinfo=UTC),
        source_url="https://www.sec.gov/Archives/example.htm",
        content_hash=filing_content_hash(filing_html),
    )
