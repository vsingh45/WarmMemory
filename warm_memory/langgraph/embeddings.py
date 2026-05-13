from __future__ import annotations

import math
from typing import Any, Mapping

from langchain_core.embeddings import Embeddings

from ..scoring import ImportanceScorer


class EmbeddingsImportanceScorer(ImportanceScorer):
    """
    Importance scorer that ranks rows by cosine similarity in a
    LangChain `Embeddings` space.

    Bring your own embedding model: any object implementing
    `embed_query` / `embed_documents` works (OpenAI, HuggingFace, Anthropic,
    Voyage, or `DeterministicFakeEmbedding` for tests).

    Example:
        from langchain_openai import OpenAIEmbeddings
        scorer = EmbeddingsImportanceScorer(OpenAIEmbeddings())
        store = WarmStore(scorer=scorer)
    """

    __slots__ = ("embeddings", "role_weights", "_cache")

    def __init__(
        self,
        embeddings: Embeddings,
        *,
        role_weights: Mapping[str, float] | None = None,
    ) -> None:
        self.embeddings = embeddings
        self.role_weights = dict(role_weights or {})
        self._cache: dict[str, list[float]] = {}

    def _embed(self, text: str) -> list[float]:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        vector = self.embeddings.embed_query(text)
        self._cache[text] = vector
        return vector

    def score(self, query: str, row: Mapping[str, Any]) -> float:
        content = str(row.get("content", ""))
        if not content.strip() or not query.strip():
            return 0.0

        query_vec = self._embed(query)
        doc_vec = self._embed(content)
        if not query_vec or not doc_vec or len(query_vec) != len(doc_vec):
            return 0.0

        dot = sum(a * b for a, b in zip(query_vec, doc_vec))
        query_norm = math.sqrt(sum(a * a for a in query_vec))
        doc_norm = math.sqrt(sum(b * b for b in doc_vec))
        if query_norm == 0 or doc_norm == 0:
            return 0.0

        similarity = dot / (query_norm * doc_norm)
        role = str(row.get("role", "user"))
        weight = self.role_weights.get(role, 1.0)
        return similarity * weight
