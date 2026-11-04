import pytest

from app.models import Evaluation, IndexVersion
from app.state import StateRepository


def make_index(identifier: str, collection: str) -> IndexVersion:
    return IndexVersion(
        id=identifier,
        collection_name=collection,
        ticker="ACME",
        filing_accessions=[f"{identifier}-accession"],
        chunk_count=3,
    )


def test_candidate_is_isolated_and_promotion_retains_prior_index(tmp_path):
    repository = StateRepository(tmp_path)
    first = make_index("v1", "asof_candidate_acme_v1")
    repository.register_candidate(first)
    repository.promote("v1")

    second = make_index("v2", "asof_candidate_acme_v2")
    repository.register_candidate(second)
    before = repository.load()

    assert before.production_id == "v1"
    assert before.candidate_id == "v2"
    assert before.indexes["v1"].collection_name != before.indexes["v2"].collection_name

    promotion = repository.promote("v2")
    after = repository.load()

    assert promotion.previous_production_id == "v1"
    assert after.production_id == "v2"
    assert after.candidate_id is None
    assert after.indexes["v1"].stage == "retired"
    assert after.indexes["v1"].collection_name == "asof_candidate_acme_v1"


def test_promotion_rejects_failed_or_retired_index(tmp_path):
    repository = StateRepository(tmp_path)
    failed = make_index("failed", "asof_candidate_acme_failed").model_copy(
        update={"evaluation": Evaluation(temporal_violations=1)}
    )
    repository.register_candidate(failed)

    with pytest.raises(ValueError, match="temporal violations"):
        repository.promote("failed")

    valid = make_index("valid", "asof_candidate_acme_valid")
    repository.register_candidate(valid)
    repository.promote("valid")

    with pytest.raises(ValueError, match="already in production"):
        repository.promote("valid")
