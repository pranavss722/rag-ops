"""Tests for the FastAPI endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def test_query_request_schema_validation():
    from app.main import QueryRequest, QueryResponse

    req = QueryRequest(question="What is FAISS?")
    assert req.question == "What is FAISS?"
    assert req.top_k == 5  # default

    req2 = QueryRequest(question="Test", top_k=10)
    assert req2.top_k == 10

    resp = QueryResponse(
        answer="FAISS is a library.",
        sources=[{"source": "doc.txt", "score": 0.9}],
        trace_id="trace-123",
        latency_ms=100.5,
        cost_usd=0.003,
    )
    assert resp.answer == "FAISS is a library."
    assert resp.trace_id == "trace-123"


@pytest.mark.anyio
async def test_query_endpoint_returns_answer():
    from app.generation import GenerationResult
    from app.retrieval import RetrievalResult

    mock_results = [
        RetrievalResult(content="FAISS content", score=0.9, metadata={"source": "doc_0.txt"}),
    ]
    mock_gen = GenerationResult(
        answer="FAISS is great.",
        usage={"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
        model="gpt-4o",
    )

    with (
        patch("app.main._get_index") as mock_get_index,
        patch("app.main.OpenAIEmbeddings"),
        patch("app.main.search", return_value=mock_results),
        patch("app.main.build_prompt", return_value="test prompt"),
        patch("app.main.generate_answer", return_value=mock_gen),
        patch("app.main._trace_query") as mock_trace,
    ):
        mock_get_index.return_value = MagicMock()
        mock_trace.return_value = "trace-abc"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/query", json={"question": "What is FAISS?"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "FAISS is great."
        assert "trace_id" in data
        assert "latency_ms" in data
        assert "cost_usd" in data
        assert len(data["sources"]) == 1


@pytest.mark.anyio
async def test_query_endpoint_handles_empty_index():
    with patch("app.main._get_index", return_value=None):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/query", json={"question": "test"})

        assert resp.status_code == 503
        assert "index" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_stats_endpoint_returns_aggregates():
    from app.main import query_stats

    # Simulate some recorded queries
    query_stats.clear()
    query_stats.extend(
        [
            {"latency_ms": 100.0, "cost_usd": 0.003},
            {"latency_ms": 200.0, "cost_usd": 0.005},
        ]
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/stats")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_queries"] == 2
    assert data["avg_latency_ms"] == 150.0
    assert data["avg_cost_usd"] == 0.004
    assert data["total_cost_usd"] == 0.008
