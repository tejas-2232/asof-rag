from datetime import UTC, datetime

from app.sec import SecEdgarClient


def test_acceptance_timestamp_supports_iso_and_legacy_formats():
    iso = {"acceptanceDateTime": ["2026-07-29T20:04:17.000Z"]}
    legacy = {"acceptanceDateTime": ["20240730160500"]}

    assert SecEdgarClient._filed_at(iso, 0) == datetime(
        2026, 7, 29, 20, 4, 17, tzinfo=UTC
    )
    assert SecEdgarClient._filed_at(legacy, 0) == datetime(
        2024, 7, 30, 20, 5, tzinfo=UTC
    )
