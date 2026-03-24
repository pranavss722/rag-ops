"""Tests for the RAGAS evaluation pipeline."""

from unittest.mock import MagicMock, patch


def test_eval_set_has_required_columns():
    from scripts.generate_eval_set import generate_eval_set

    eval_set = generate_eval_set(num_pairs=50, seed=42)

    assert len(eval_set) == 50
    required_keys = {"question", "ground_truth", "context_source"}
    for entry in eval_set:
        assert required_keys.issubset(entry.keys()), f"Missing keys in {entry}"
        assert len(entry["question"]) > 0
        assert len(entry["ground_truth"]) > 0
        assert len(entry["context_source"]) > 0


def test_eval_set_is_deterministic():
    from scripts.generate_eval_set import generate_eval_set

    a = generate_eval_set(num_pairs=10, seed=42)
    b = generate_eval_set(num_pairs=10, seed=42)

    for i in range(10):
        assert a[i]["question"] == b[i]["question"]
        assert a[i]["ground_truth"] == b[i]["ground_truth"]


def test_ragas_runner_returns_scores():
    from scripts.evaluate import run_evaluation

    mock_pipeline = MagicMock()
    mock_pipeline.return_value = {
        "answer": "Test answer",
        "contexts": ["context chunk 1"],
    }

    eval_set = [
        {
            "question": "What is FAISS?",
            "ground_truth": "FAISS is a vector search library.",
            "context_source": "doc_0.txt",
        }
    ]

    with patch("scripts.evaluate._evaluate_with_ragas") as mock_ragas:
        mock_ragas.return_value = {
            "faithfulness": 0.85,
            "answer_relevancy": 0.90,
            "context_precision": 0.80,
        }
        scores = run_evaluation(eval_set, mock_pipeline)

    assert "faithfulness" in scores
    assert "answer_relevancy" in scores
    assert "context_precision" in scores
    assert all(0 <= v <= 1 for v in scores.values())


def test_scores_pushed_to_langfuse():
    from scripts.evaluate import push_scores_to_langfuse

    mock_client = MagicMock()
    scores = {
        "faithfulness": 0.85,
        "answer_relevancy": 0.90,
        "context_precision": 0.80,
    }

    push_scores_to_langfuse(mock_client, trace_id="trace-123", scores=scores)

    assert mock_client.score.call_count == 3
    call_names = [c.kwargs["name"] for c in mock_client.score.call_args_list]
    assert set(call_names) == {"faithfulness", "answer_relevancy", "context_precision"}
