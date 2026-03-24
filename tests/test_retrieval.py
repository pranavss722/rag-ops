"""Tests for the retrieval module."""

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.ingestion import build_index


class FakeEmbeddings(Embeddings):
    """Deterministic fake embeddings for testing."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(i % 10) * 0.1] * 128 for i in range(len(texts))]

    def embed_query(self, text: str) -> list[float]:
        return [0.5] * 128


def test_embed_query_returns_vector():
    from app.retrieval import embed_query

    emb = FakeEmbeddings()
    vector = embed_query("What is an API?", embeddings=emb)

    assert isinstance(vector, list)
    assert len(vector) == 128
    assert all(isinstance(v, float) for v in vector)


def _build_test_index(emb):
    chunks = [
        Document(
            page_content=f"Document about topic {i} with technical content",
            metadata={"source": f"doc_{i}.txt", "chunk_index": 0},
        )
        for i in range(20)
    ]
    return build_index(chunks, embeddings=emb)


def test_search_returns_top_k_with_scores():
    from app.retrieval import search

    emb = FakeEmbeddings()
    store = _build_test_index(emb)

    results = search("technical topic", store=store, embeddings=emb, k=5)

    assert len(results) == 5
    for r in results:
        assert hasattr(r, "content")
        assert hasattr(r, "score")
        assert hasattr(r, "metadata")
        assert isinstance(r.score, float)
        assert "source" in r.metadata


def test_retrieval_result_schema():
    from app.retrieval import RetrievalResult

    r = RetrievalResult(content="test content", score=0.95, metadata={"source": "doc.txt"})
    assert r.content == "test content"
    assert r.score == 0.95
    assert r.metadata == {"source": "doc.txt"}
