from pathlib import Path

import pytest

from rag_mcp.config import Settings
from rag_mcp.embedding import HashEmbedder
from rag_mcp.ingest import build_index
from rag_mcp.store import VectorStore

SAMPLE_DATA = Path(__file__).resolve().parents[1] / "sample_data"


@pytest.fixture
def settings(tmp_path):
    return Settings(index_dir=tmp_path / "index", data_dir=SAMPLE_DATA, embedder="hash")


@pytest.fixture
def empty_store(settings):
    return VectorStore(settings.index_dir, settings.collection, HashEmbedder())


@pytest.fixture
def indexed_store(empty_store, settings):
    build_index(empty_store, settings.data_dir)
    return empty_store
