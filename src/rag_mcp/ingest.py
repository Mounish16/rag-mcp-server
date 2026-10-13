"""Load documents from a data directory, chunk them and index them.

Run as a CLI:  python -m rag_mcp.ingest
"""
import argparse
import json
import logging
import sys
from pathlib import Path

import yaml
from pypdf import PdfReader

from rag_mcp.config import Settings
from rag_mcp.embedding import make_embedder
from rag_mcp.store import Chunk, VectorStore

logger = logging.getLogger("rag-mcp.ingest")
logging.getLogger("pypdf").setLevel(logging.ERROR)  # quiet noisy PDF-structure warnings

SUPPORTED_SUFFIXES = {".txt", ".md", ".json", ".jsonl", ".yaml", ".yml", ".pdf"}
MAX_FILE_BYTES = 20 * 1024 * 1024  # skip anything larger than 20 MB


def read_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".json":
        return json.dumps(json.loads(raw), indent=2, ensure_ascii=False)
    if suffix in (".yaml", ".yml"):
        return yaml.safe_dump(yaml.safe_load(raw), sort_keys=False, allow_unicode=True)
    return raw


def chunk_words(text: str, size: int, overlap: int) -> list[str]:
    """Split text into windows of `size` words that overlap by `overlap` words."""
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("Need size > 0 and 0 <= overlap < size")
    words = text.split()
    chunks, start = [], 0
    while start < len(words):
        end = min(start + size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return chunks


def load_documents(data_dir: Path) -> list[tuple[str, str]]:
    """Return (relative_posix_path, text) for every readable supported file.

    Files that resolve outside `data_dir` (for example via symlinks) are skipped.
    """
    root = data_dir.resolve()
    docs: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            logger.warning("Skipping %s: resolves outside the data directory", path)
            continue
        if resolved.stat().st_size > MAX_FILE_BYTES:
            logger.warning("Skipping %s: larger than %d bytes", path, MAX_FILE_BYTES)
            continue
        try:
            text = read_file(resolved).strip()
        except Exception as exc:  # one bad file should not stop indexing
            logger.warning("Skipping %s: %s", path, exc)
            continue
        if text:
            docs.append((resolved.relative_to(root).as_posix(), text))
    return docs


def build_chunks(docs: list[tuple[str, str]], size: int, overlap: int) -> list[Chunk]:
    return [
        Chunk(source=source, index=i, text=piece)
        for source, text in docs
        for i, piece in enumerate(chunk_words(text, size, overlap))
    ]


def build_index(store: VectorStore, data_dir: Path, size: int = 200, overlap: int = 40) -> dict:
    docs = load_documents(data_dir)
    if not docs:
        raise RuntimeError(f"No supported documents found in {data_dir}")
    chunks = build_chunks(docs, size, overlap)
    store.reset()
    store.add_chunks(chunks)
    return {"documents": len(docs), "chunks": len(chunks)}


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(message)s")
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(description="Build the RAG vector index.")
    parser.add_argument("--data-dir", type=Path, default=settings.data_dir)
    parser.add_argument("--index-dir", type=Path, default=settings.index_dir)
    args = parser.parse_args()

    store = VectorStore(
        args.index_dir, settings.collection, make_embedder(settings.embedder, settings.embed_model)
    )
    summary = build_index(store, args.data_dir, settings.chunk_words, settings.overlap_words)
    print(f"Indexed {summary['chunks']} chunks from {summary['documents']} documents into {args.index_dir}")


if __name__ == "__main__":
    main()
