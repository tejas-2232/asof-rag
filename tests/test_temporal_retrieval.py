import uuid
from datetime import UTC, datetime

from qdrant_client import QdrantClient

from app.parser import parse_filing, sha256
from app.store import QdrantStore


class KeywordEmbedder:
    def embed(self, documents):
        for document in documents:
            yield [1.0, 0.0] if "future" in document.lower() else [0.0, 1.0]


def test_temporal_filter_excludes_future_before_ranking(filing_html, filing):
    base = parse_filing(filing_html, filing)[0]
    old_text = "Historical revenue information."
    future_text = "Future restatement with highly relevant future facts."
    old = base.model_copy(
        update={
            "id": str(uuid.uuid4()),
            "text": old_text,
            "content_hash": sha256(old_text),
        }
    )
    future_date = datetime(2025, 5, 1, tzinfo=UTC)
    future = base.model_copy(
        update={
            "id": str(uuid.uuid4()),
            "accession": "0000000001-25-000001",
            "filing_id": "0000000001-25-000001",
            "filed_at": future_date,
            "filed_at_epoch": int(future_date.timestamp()),
            "text": future_text,
            "content_hash": sha256(future_text),
        }
    )
    store = QdrantStore(
        client=QdrantClient(location=":memory:"),
        embedder=KeywordEmbedder(),
    )
    store.create_collection("temporal_test", [old, future])
    cutoff = datetime(2024, 12, 31, tzinfo=UTC)

    safe = store.query("temporal_test", "future", cutoff, 5, temporal_filter=True)
    naive = store.query("temporal_test", "future", cutoff, 5, temporal_filter=False)

    assert [hit.chunk.id for hit in safe] == [old.id]
    assert naive[0].chunk.id == future.id
