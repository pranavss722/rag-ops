"""Tests for the generation module."""

from unittest.mock import MagicMock, patch

from app.retrieval import RetrievalResult


def test_build_prompt_includes_context_and_query():
    from app.generation import build_prompt

    chunks = [
        RetrievalResult(
            content="FAISS is a vector search library.",
            score=0.9,
            metadata={"source": "doc_0.txt"},
        ),
        RetrievalResult(
            content="Embeddings map text to vectors.", score=0.8, metadata={"source": "doc_1.txt"}
        ),
    ]

    prompt = build_prompt("What is FAISS?", chunks)

    assert "What is FAISS?" in prompt
    assert "FAISS is a vector search library." in prompt
    assert "Embeddings map text to vectors." in prompt
    assert "doc_0.txt" in prompt


def test_generate_answer_returns_response():
    from app.generation import GenerationResult, generate_answer

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "FAISS is a library for similarity search."
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 20
    mock_response.usage.total_tokens = 120
    mock_response.model = "gpt-4o"

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("app.generation._get_client", return_value=mock_client):
        result = generate_answer("test prompt")

    assert isinstance(result, GenerationResult)
    assert result.answer == "FAISS is a library for similarity search."
    assert result.usage["prompt_tokens"] == 100
    assert result.usage["completion_tokens"] == 20
    assert result.usage["total_tokens"] == 120
    assert result.model == "gpt-4o"


def test_generation_result_schema():
    from app.generation import GenerationResult

    r = GenerationResult(
        answer="Test answer",
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        model="gpt-4o",
    )
    assert r.answer == "Test answer"
    assert r.usage["total_tokens"] == 15
    assert r.model == "gpt-4o"
