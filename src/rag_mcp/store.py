"""Thin wrapper around a persistent ChromaDB collection."""
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import chromadb

from rag_mcp.embedding import Embedder


@dataclass(frozen=True)
class Chunk:
    source: str  # path relative to the data directory, POSIX style
    index: int
    text: str

    @property
    def id(self) -> str:
        return f"{self.source}::{self.index}"


class VectorStore:
    def __init__(self, index_dir: Path, collection: str, embedder: Embedder):
        self._client = chromadb.PersistentClient(path=str(index_dir))
        self._name = collection
        self._embedder = embedder

    @property
    def _col(self):
        return self._client.get_or_create_collection(self._name)

    def reset(self) -> None:
        try:
            self._client.delete_collection(self._name)
        except Exception:
            pass

    def add_chunks(self, chunks: list[Chunk], batch_size: int = 64) -> int:
        col = self._col
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            col.add(
                ids=[c.id for c in batch],
                documents=[c.text for c in batch],
                metadatas=[{"source": c.source, "chunk": c.index} for c in batch],
                embeddings=self._embedder.embed([c.text for c in batch]),
            )
        return len(chunks)

    def count(self) -> int:
        return self._col.count()

    def search(self, query: str, top_k: int = 5, source: Optional[str] = None) -> list[dict[str, Any]]:
        col = self._col
        if col.count() == 0:
            return []
        result = col.query(
            query_embeddings=self._embedder.embed([query]),
            n_results=top_k,
            where={"source": source} if source else None,
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        for i, text in enumerate(result["documents"][0]):
            meta = result["metadatas"][0][i]
            hits.append({
                "citation": f"[{i + 1}]",
                "source": meta["source"],
                "chunk": meta["chunk"],
                "distance": round(float(result["distances"][0][i]), 4),
                "text": text,
            })
        return hits

    def get_chunk(self, source: str, chunk: int) -> Optional[dict[str, Any]]:
        got = self._col.get(ids=[f"{source}::{chunk}"], include=["documents", "metadatas"])
        if not got["ids"]:
            return None
        return {
            "source": got["metadatas"][0]["source"],
            "chunk": got["metadatas"][0]["chunk"],
            "text": got["documents"][0],
        }

    def list_sources(self) -> list[dict[str, Any]]:
        metas = self._col.get(include=["metadatas"])["metadatas"] or []
        counts = Counter(m["source"] for m in metas)
        return [{"source": s, "chunks": n} for s, n in sorted(counts.items())]

    def stats(self) -> dict[str, Any]:
        sources = self.list_sources()
        return {
            "collection": self._name,
            "chunks": sum(s["chunks"] for s in sources),
            "sources": len(sources),
        }
