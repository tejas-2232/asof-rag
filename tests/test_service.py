from datetime import UTC, datetime

from app.sec import SecFilingRef
from app.service import AsOfRagService
from app.state import StateRepository


class FakeSecClient:
    def __init__(self):
        self.reference = SecFilingRef(
            ticker="ACME",
            cik="0000000001",
            accession="0000000001-24-000001",
            form="10-Q",
            report_date="2024-03-31",
            filed_at=datetime(2024, 5, 1, 20, 30, tzinfo=UTC),
            primary_document="filing.htm",
            source_url="https://www.sec.gov/Archives/filing.htm",
        )

    def list_filings(self, ticker, forms, limit):
        return [self.reference]

    def cached_source(self, accession):
        return None

    def download_filing(self, reference):
        assert reference.accession == self.reference.accession
        return b"<html><body>live filing</body></html>"


def test_discovery_persists_reference_for_later_download(tmp_path):
    service = AsOfRagService(
        StateRepository(tmp_path),
        store=object(),
        sec=FakeSecClient(),
    )

    discovered = service.list_filings("ACME")
    source = service.filing_source(discovered[0].accession)

    assert source == "<html><body>live filing</body></html>"
    assert service.status().filing_references[discovered[0].accession].ticker == "ACME"
