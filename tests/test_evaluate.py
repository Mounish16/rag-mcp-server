import pytest

from rag_mcp.evaluate import (
    DEFAULT_QUESTIONS,
    evaluate,
    first_hit_rank,
    load_questions,
    summarise,
)
from rag_mcp.ingest import load_documents


def test_first_hit_rank_returns_first_matching_position():
    assert first_hit_rank(["a", "b", "c"], ["c", "b"]) == 2
    assert first_hit_rank(["a", "b"], ["z"]) is None
    assert first_hit_rank([], ["a"]) is None


def test_summarise_computes_recall_and_mrr():
    summary = summarise([1, 3, None, 2], ks=(1, 3))
    assert summary["recall@1"] == pytest.approx(0.25)
    assert summary["recall@3"] == pytest.approx(0.75)
    assert summary["mrr"] == pytest.approx((1 + 1 / 3 + 0 + 1 / 2) / 4)
    assert summary["questions"] == 4


def test_summarise_rejects_empty_input():
    with pytest.raises(ValueError):
        summarise([])


def test_question_set_is_well_formed(settings):
    questions = load_questions(DEFAULT_QUESTIONS)
    ids = [q["id"] for q in questions]
    assert len(ids) == len(set(ids)), "question ids must be unique"
    available = {source for source, _ in load_documents(settings.data_dir)}
    for q in questions:
        missing = set(q["expected_sources"]) - available
        assert not missing, f"{q['id']} expects sources that do not exist: {missing}"


def test_hash_baseline_stays_above_floor(indexed_store):
    summary, rows = evaluate(indexed_store, load_questions(DEFAULT_QUESTIONS))
    assert summary["recall@5"] >= 0.6
    assert summary["recall@1"] <= summary["recall@3"] <= summary["recall@5"]
    assert len(rows) == summary["questions"]
