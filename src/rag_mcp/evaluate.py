"""Measure retrieval quality against a labelled question set.

Each question lists the source file(s) that contain its answer. A question is a
hit at rank k when at least one of its expected sources appears among the first
k retrieved chunks. Reports recall@k and mean reciprocal rank (MRR).

Run as a CLI:  python -m rag_mcp.evaluate
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Optional, Sequence

from rag_mcp.config import PROJECT_ROOT, Settings
from rag_mcp.embedding import make_embedder
from rag_mcp.ingest import build_index
from rag_mcp.store import VectorStore

DEFAULT_QUESTIONS = PROJECT_ROOT / "eval" / "questions.json"
DEFAULT_KS = (1, 3, 5)


def load_questions(path: Path) -> list[dict]:
    questions = json.loads(Path(path).read_text(encoding="utf-8"))
    for q in questions:
        if not q.get("question") or not q.get("expected_sources"):
            raise ValueError(f"Question {q.get('id')!r} needs 'question' and 'expected_sources'")
    return questions


def first_hit_rank(retrieved_sources: Sequence[str], expected: Iterable[str]) -> Optional[int]:
    """1-based rank of the first retrieved chunk from an expected source, else None."""
    wanted = set(expected)
    for rank, source in enumerate(retrieved_sources, start=1):
        if source in wanted:
            return rank
    return None


def summarise(ranks: Sequence[Optional[int]], ks: Sequence[int] = DEFAULT_KS) -> dict:
    """Aggregate per-question first-hit ranks into recall@k and MRR."""
    n = len(ranks)
    if n == 0:
        raise ValueError("No questions to evaluate")
    summary = {f"recall@{k}": sum(1 for r in ranks if r is not None and r <= k) / n for k in ks}
    summary["mrr"] = sum(1 / r for r in ranks if r is not None) / n
    summary["questions"] = n
    return summary


def evaluate(store: VectorStore, questions: Sequence[dict], ks: Sequence[int] = DEFAULT_KS):
    depth = max(ks)
    ranks, rows = [], []
    for q in questions:
        hits = store.search(q["question"], top_k=depth)
        rank = first_hit_rank([h["source"] for h in hits], q["expected_sources"])
        ranks.append(rank)
        rows.append({"id": q.get("id"), "question": q["question"], "rank": rank,
                     "top_source": hits[0]["source"] if hits else None})
    return summarise(ranks, ks), rows


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate retrieval quality.")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--embedder", choices=["sentence-transformers", "hash"], default=None,
                        help="Defaults to RAG_EMBEDDER, else sentence-transformers.")
    parser.add_argument("--json", type=Path, default=None, help="Also write results to this JSON file.")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    kind = args.embedder or settings.embedder
    questions = load_questions(args.questions)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        store = VectorStore(Path(tmp) / "index", settings.collection,
                            make_embedder(kind, settings.embed_model))
        stats = build_index(store, settings.data_dir, settings.chunk_words, settings.overlap_words)
        summary, rows = evaluate(store, questions)

    print(f"Embedder: {kind}   Chunks indexed: {stats["chunks"]}   Questions: {summary['questions']}")
    for k in DEFAULT_KS:
        print(f"  recall@{k}: {summary[f'recall@{k}']:.3f}")
    print(f"  MRR:      {summary['mrr']:.3f}")
    misses = [r for r in rows if r["rank"] is None or r["rank"] > DEFAULT_KS[-1]]
    if misses:
        print(f"\nNot found in top {DEFAULT_KS[-1]}:")
        for r in misses:
            print(f"  {r['id']}: {r['question']}  (top hit: {r['top_source']})")
    if args.json:
        args.json.write_text(json.dumps({"embedder": kind, **summary, "details": rows}, indent=2),
                             encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
