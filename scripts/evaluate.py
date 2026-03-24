"""RAGAS evaluation runner — measures faithfulness, relevancy, and context precision."""

from collections.abc import Callable
from typing import Any


def _evaluate_with_ragas(eval_data: list[dict]) -> dict[str, float]:
    """Run RAGAS evaluation on prepared data. Separated for mockability."""
    from datasets import Dataset
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas import evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import answer_relevancy, context_precision, faithfulness

    llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o"))
    embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small"))

    dataset = Dataset.from_list(eval_data)
    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision],
        llm=llm,
        embeddings=embeddings,
    )

    def _extract_score(val):
        if isinstance(val, list):
            valid = [v for v in val if v is not None and not (isinstance(v, float) and v != v)]
            return sum(valid) / len(valid) if valid else 0.0
        return float(val)

    return {
        "faithfulness": _extract_score(result["faithfulness"]),
        "answer_relevancy": _extract_score(result["answer_relevancy"]),
        "context_precision": _extract_score(result["context_precision"]),
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


if __name__ == "__main__":
    import sys
    import time
    from pathlib import Path

    # Ensure we import from this project, not another installed 'app' package
    project_root = str(Path(__file__).resolve().parent.parent)
    sys.path.insert(0, project_root)

    from dotenv import load_dotenv

    load_dotenv()

    from langchain_openai import OpenAIEmbeddings

    from app.generation import build_prompt, generate_answer
    from app.ingestion import load_index
    from app.retrieval import search
    from app.tracing import calculate_cost
    from scripts.generate_eval_set import generate_eval_set

    INDEX_DIR = Path("data/faiss_index")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    print("Loading FAISS index...")
    store = load_index(INDEX_DIR, embeddings=embeddings)
    print(f"Index loaded: {store.index.ntotal} vectors")

    print("Generating evaluation dataset (50 Q&A pairs)...")
    eval_set = generate_eval_set(num_pairs=50, seed=42)

    print(f"Running {len(eval_set)} queries through the pipeline...")
    eval_data = []
    total_cost = 0.0
    start = time.perf_counter()

    for i, entry in enumerate(eval_set):
        results = search(entry["question"], store=store, embeddings=embeddings, k=5)
        prompt = build_prompt(entry["question"], results)
        gen = generate_answer(prompt)

        cost = calculate_cost(
            gen.model, gen.usage["prompt_tokens"], gen.usage["completion_tokens"]
        )
        total_cost += cost

        # Pass actual chunk text as contexts — RAGAS needs the retrieved text
        contexts = [r.content for r in results]
        eval_data.append(
            {
                "question": entry["question"],
                "answer": gen.answer,
                "contexts": contexts,
                "ground_truth": entry["ground_truth"],
            }
        )
        print(f"  [{i + 1}/{len(eval_set)}] ${cost:.4f} | {entry['question'][:55]}...")

    query_time = time.perf_counter() - start
    print(f"\nAll queries complete in {query_time:.1f}s (API cost: ${total_cost:.4f})")

    print("\nRunning RAGAS evaluation (this calls OpenAI for LLM-as-judge)...")
    scores = _evaluate_with_ragas(eval_data)

    print("\n" + "=" * 50)
    print("RAGAS EVALUATION RESULTS")
    print("=" * 50)
    for metric, score in scores.items():
        print(f"  {metric:25s} {score:.4f}")
    print(f"\n  Total API cost (queries): ${total_cost:.4f}")
    print("=" * 50)
