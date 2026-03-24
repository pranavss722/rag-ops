"""Retrieval module — vector search and re-ranking."""

from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel


class RetrievalResult(BaseModel):
    """A single retrieval result with content, score, and metadata."""

    content: str
    score: float
    metadata: dict


def embed_query(query: str, embeddings: Embeddings) -> list[float]:
    """Embed a query string into a vector."""
    return embeddings.embed_query(query)


def search(
    query: str,
    store: FAISS,
    embeddings: Embeddings,
    k: int = 5,
) -> list[RetrievalResult]:
    """Search the FAISS index and return top-k results with scores."""
    results_with_scores = store.similarity_search_with_score(query, k=k)
    return [
        RetrievalResult(
            content=doc.page_content,
            score=float(score),
            metadata=doc.metadata,
        )
        for doc, score in results_with_scores
    ]
