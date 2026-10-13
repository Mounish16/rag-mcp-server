"""Embedding backends.

`SentenceTransformerEmbedder` is the real one. `HashEmbedder` is a small,
deterministic, dependency-free stand-in so the server can be demoed and tested
without downloading a model.
"""
import hashlib
import math
import re
from typing import Protocol, Sequence


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class SentenceTransformerEmbedder:
    """Loads the model lazily on first use (keeps server start-up fast)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._load().encode(
            list(texts), normalize_embeddings=True, show_progress_bar=False
        )
        return vectors.tolist()


class HashEmbedder:
    """Bag-of-words hashing embedder: texts sharing words get similar vectors."""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in re.findall(r"\w+", text.lower()):
            bucket = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % self.dim
            vec[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def make_embedder(kind: str, model_name: str) -> Embedder:
    if kind == "hash":
        return HashEmbedder()
    if kind in ("sentence-transformers", "st"):
        return SentenceTransformerEmbedder(model_name)
    raise ValueError(f"Unknown embedder '{kind}'. Use 'sentence-transformers' or 'hash'.")
