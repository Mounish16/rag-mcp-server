"""Runtime settings, read from environment variables."""
import os
from dataclasses import dataclass
from pathlib import Path

# Repo root when running from a source checkout (src/rag_mcp/config.py -> repo).
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    index_dir: Path
    data_dir: Path
    collection: str = "rag_collection"
    embedder: str = "sentence-transformers"  # or "hash" (offline demo / tests)
    embed_model: str = "all-MiniLM-L6-v2"
    chunk_words: int = 200
    overlap_words: int = 40

    @classmethod
    def from_env(cls) -> "Settings":
        def path(var: str, default: Path) -> Path:
            return Path(os.getenv(var, str(default))).expanduser().resolve()

        return cls(
            index_dir=path("RAG_INDEX_DIR", PROJECT_ROOT / "index" / "chroma"),
            data_dir=path("RAG_DATA_DIR", PROJECT_ROOT / "sample_data"),
            collection=os.getenv("RAG_COLLECTION", "rag_collection"),
            embedder=os.getenv("RAG_EMBEDDER", "sentence-transformers"),
            embed_model=os.getenv("RAG_EMBED_MODEL", "all-MiniLM-L6-v2"),
            chunk_words=int(os.getenv("RAG_CHUNK_WORDS", "200")),
            overlap_words=int(os.getenv("RAG_OVERLAP_WORDS", "40")),
        )
