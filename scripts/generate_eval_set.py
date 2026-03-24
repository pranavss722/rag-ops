"""Generate a synthetic evaluation dataset for RAGAS evaluation."""

import json
import random
from pathlib import Path

CATEGORIES = {
    "machine_learning": [
        (
            "What is gradient descent?",
            "Gradient descent is an optimization algorithm that iteratively adjusts parameters to minimize a loss function by moving in the direction of steepest descent.",
        ),
        (
            "How does a transformer architecture work?",
            "Transformers use self-attention mechanisms to process input sequences in parallel, computing relationships between all positions simultaneously.",
        ),
        (
            "What is overfitting in machine learning?",
            "Overfitting occurs when a model learns noise in the training data rather than the underlying pattern, leading to poor generalization on unseen data.",
        ),
        (
            "Explain batch normalization.",
            "Batch normalization normalizes layer inputs across the mini-batch, reducing internal covariate shift and allowing higher learning rates.",
        ),
        (
            "What is transfer learning?",
            "Transfer learning reuses a model trained on one task as the starting point for a model on a different but related task.",
        ),
    ],
    "systems_design": [
        (
            "What is a load balancer?",
            "A load balancer distributes incoming network traffic across multiple servers to ensure no single server bears too much demand.",
        ),
        (
            "Explain the CAP theorem.",
            "The CAP theorem states that a distributed system can only guarantee two of three properties: consistency, availability, and partition tolerance.",
        ),
        (
            "What is a circuit breaker pattern?",
            "The circuit breaker pattern prevents cascading failures by detecting failures and temporarily stopping requests to a failing service.",
        ),
        (
            "How does horizontal scaling work?",
            "Horizontal scaling adds more machines to a pool of resources, distributing the workload across multiple nodes.",
        ),
        (
            "What is eventual consistency?",
            "Eventual consistency guarantees that if no new updates are made, all replicas will eventually converge to the same value.",
        ),
    ],
    "databases": [
        (
            "What is a B-tree index?",
            "A B-tree index is a self-balancing tree data structure that maintains sorted data and allows searches, insertions, and deletions in logarithmic time.",
        ),
        (
            "Explain write-ahead logging.",
            "Write-ahead logging ensures durability by writing changes to a log before applying them to the database, enabling crash recovery.",
        ),
        (
            "What is MVCC?",
            "Multi-Version Concurrency Control allows multiple transactions to access the database concurrently by maintaining multiple versions of data.",
        ),
        (
            "How does database sharding work?",
            "Database sharding partitions data across multiple database instances based on a shard key, distributing both data and query load.",
        ),
        (
            "What is a connection pool?",
            "A connection pool maintains a cache of database connections that can be reused, reducing the overhead of establishing new connections.",
        ),
    ],
    "apis": [
        (
            "What is REST API versioning?",
            "REST API versioning manages breaking changes by using URL paths, headers, or query parameters to route requests to different API versions.",
        ),
        (
            "Explain OAuth 2.0 authorization.",
            "OAuth 2.0 is an authorization framework that enables applications to obtain limited access to user accounts via access tokens.",
        ),
        (
            "What is an idempotency key?",
            "An idempotency key ensures that retrying the same request produces the same result, preventing duplicate operations.",
        ),
        (
            "How does API rate limiting work?",
            "API rate limiting restricts the number of requests a client can make in a time window, protecting services from overload.",
        ),
        (
            "What is GraphQL?",
            "GraphQL is a query language for APIs that lets clients request exactly the data they need, reducing over-fetching and under-fetching.",
        ),
    ],
}


def generate_eval_set(num_pairs: int = 50, seed: int = 42) -> list[dict]:
    """Generate a deterministic evaluation dataset."""
    rng = random.Random(seed)

    all_pairs = []
    for category, pairs in CATEGORIES.items():
        for question, answer in pairs:
            all_pairs.append(
                {
                    "question": question,
                    "ground_truth": answer,
                    "context_source": f"{category}_doc.txt",
                    "category": category,
                }
            )

    # Expand to desired size by creating variations
    result = []
    for i in range(num_pairs):
        base = rng.choice(all_pairs)
        if i < len(all_pairs):
            result.append(all_pairs[i % len(all_pairs)])
        else:
            variation = {
                "question": f"Explain in detail: {base['question'].lower().rstrip('?')}",
                "ground_truth": base["ground_truth"],
                "context_source": base["context_source"],
                "category": base["category"],
            }
            result.append(variation)

    return result


if __name__ == "__main__":
    eval_set = generate_eval_set(num_pairs=50, seed=42)
    output = Path(__file__).resolve().parent.parent / "data" / "eval_set.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        for entry in eval_set:
            f.write(json.dumps(entry) + "\n")
    print(f"Generated {len(eval_set)} evaluation pairs -> {output}")
