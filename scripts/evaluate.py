"""RAGAS evaluation runner — measures faithfulness, relevancy, and context precision."""

from collections.abc import Callable
from typing import Any


def _evaluate_with_ragas(eval_data: list[dict]) -> dict[str, float]:
    """Run RAGAS evaluation on prepared data. Separated for mockability."""
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import answer_relevancy, context_precision, faithfulness

    dataset = Dataset.from_list(eval_data)
    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision],
    )
    return {
        "faithfulness": float(result["faithfulness"]),
        "answer_relevancy": float(result["answer_relevancy"]),
        "context_precision": float(result["context_precision"]),
    }


def run_evaluation(
    eval_set: list[dict],
    pipeline_fn: Callable[[str], dict[str, Any]],
) -> dict[str, float]:
    """Run the full evaluation pipeline.

    Args:
        eval_set: List of dicts with question, ground_truth, context_source.
        pipeline_fn: Callable that takes a question and returns
                     {"answer": str, "contexts": list[str]}.

    Returns:
        Dict with faithfulness, answer_relevancy, context_precision scores.
    """
    eval_data = []
    for entry in eval_set:
        result = pipeline_fn(entry["question"])
        eval_data.append(
            {
                "question": entry["question"],
                "answer": result["answer"],
                "contexts": result["contexts"],
                "ground_truth": entry["ground_truth"],
            }
        )

    return _evaluate_with_ragas(eval_data)


def push_scores_to_langfuse(client, trace_id: str, scores: dict[str, float]) -> None:
    """Push RAGAS scores to Langfuse as score objects."""
    for name, value in scores.items():
        client.score(
            name=name,
            value=value,
            trace_id=trace_id,
        )
