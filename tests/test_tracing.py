"""Tests for the tracing module."""

from unittest.mock import MagicMock, patch


def test_get_langfuse_client_returns_instance():
    from app.tracing import get_langfuse

    with patch("app.tracing.Langfuse") as MockLangfuse:
        MockLangfuse.return_value = MagicMock()
        client = get_langfuse()
        assert client is not None
        MockLangfuse.assert_called_once()


def test_trace_context_creates_trace():
    from app.tracing import create_trace

    mock_langfuse = MagicMock()
    mock_trace = MagicMock()
    mock_langfuse.trace.return_value = mock_trace

    trace = create_trace(mock_langfuse, name="test-query", metadata={"key": "value"})

    mock_langfuse.trace.assert_called_once_with(name="test-query", metadata={"key": "value"})
    assert trace is mock_trace


def test_span_helpers_record_correct_metrics():
    from app.tracing import span_cost, span_embed, span_generate, span_retrieve

    mock_trace = MagicMock()
    mock_span = MagicMock()
    mock_trace.span.return_value = mock_span

    # Test embed span
    span_embed(mock_trace, latency_ms=15.2, model="text-embedding-3-small")
    mock_trace.span.assert_called_with(
        name="embed_query",
        input={"model": "text-embedding-3-small"},
        output={"latency_ms": 15.2},
    )

    mock_trace.span.reset_mock()

    # Test retrieve span
    span_retrieve(mock_trace, latency_ms=5.1, top_k_scores=[0.9, 0.8, 0.7], k=3)
    mock_trace.span.assert_called_with(
        name="faiss_retrieval",
        input={"k": 3},
        output={"latency_ms": 5.1, "top_k_scores": [0.9, 0.8, 0.7]},
    )

    mock_trace.span.reset_mock()

    # Test generate span
    span_generate(
        mock_trace,
        latency_ms=450.0,
        model="gpt-4o",
        prompt_tokens=200,
        completion_tokens=50,
        total_tokens=250,
    )
    mock_trace.span.assert_called_with(
        name="llm_generation",
        input={"model": "gpt-4o"},
        output={
            "latency_ms": 450.0,
            "prompt_tokens": 200,
            "completion_tokens": 50,
            "total_tokens": 250,
        },
    )

    mock_trace.span.reset_mock()

    # Test cost span
    span_cost(mock_trace, cost_usd=0.0035, breakdown={"embedding": 0.0001, "generation": 0.0034})
    mock_trace.span.assert_called_with(
        name="cost_calculation",
        input={"breakdown": {"embedding": 0.0001, "generation": 0.0034}},
        output={"cost_usd": 0.0035},
    )


def test_calculate_cost_for_known_model():
    from app.tracing import calculate_cost

    cost = calculate_cost(model="gpt-4o", prompt_tokens=1000, completion_tokens=500)
    assert isinstance(cost, float)
    assert cost > 0

    # gpt-4o: $2.50/1M prompt, $10.00/1M completion
    expected = (1000 * 2.50 / 1_000_000) + (500 * 10.00 / 1_000_000)
    assert abs(cost - expected) < 1e-8

    cost_mini = calculate_cost(model="gpt-4o-mini", prompt_tokens=1000, completion_tokens=500)
    assert cost_mini < cost  # mini should be cheaper

    cost_embed = calculate_cost(
        model="text-embedding-3-small", prompt_tokens=1000, completion_tokens=0
    )
    assert cost_embed > 0


def test_cost_metadata_attached_to_trace():
    from app.tracing import build_cost_metadata

    metadata = build_cost_metadata(
        model="gpt-4o",
        prompt_tokens=200,
        completion_tokens=50,
        embedding_tokens=100,
    )

    assert "cost_usd" in metadata
    assert metadata["cost_usd"] > 0
    assert metadata["prompt_tokens"] == 200
    assert metadata["completion_tokens"] == 50
    assert metadata["embedding_tokens"] == 100
