"""Generate a synthetic corpus of technical documents for the RAG pipeline."""

import json
import random
from datetime import UTC, datetime
from pathlib import Path

CATEGORIES = ["machine_learning", "systems_design", "databases", "apis", "networking", "security"]

TOPICS: dict[str, list[str]] = {
    "machine_learning": [
        "gradient descent optimization",
        "transformer architectures",
        "convolutional neural networks",
        "reinforcement learning policies",
        "feature engineering pipelines",
        "hyperparameter tuning strategies",
        "model evaluation metrics",
        "transfer learning approaches",
        "attention mechanisms in NLP",
        "batch normalization techniques",
    ],
    "systems_design": [
        "load balancer architectures",
        "microservices communication patterns",
        "distributed consensus algorithms",
        "event-driven architecture",
        "caching strategies at scale",
        "message queue design patterns",
        "service mesh implementation",
        "circuit breaker patterns",
        "rate limiting algorithms",
        "database sharding strategies",
    ],
    "databases": [
        "B-tree index structures",
        "write-ahead logging",
        "MVCC concurrency control",
        "query optimization techniques",
        "columnar storage formats",
        "replication topologies",
        "connection pooling strategies",
        "schema migration patterns",
        "time-series data modeling",
        "full-text search indexing",
    ],
    "apis": [
        "REST API versioning strategies",
        "GraphQL schema design",
        "gRPC service definitions",
        "API gateway patterns",
        "OAuth 2.0 authorization flows",
        "webhook delivery guarantees",
        "API rate limiting design",
        "idempotency key patterns",
        "pagination cursor strategies",
        "OpenAPI specification design",
    ],
    "networking": [
        "TCP congestion control",
        "DNS resolution strategies",
        "TLS handshake optimization",
        "HTTP/2 multiplexing",
        "WebSocket connection management",
        "CDN cache invalidation",
        "BGP routing policies",
        "NAT traversal techniques",
        "QUIC protocol advantages",
        "zero-trust network architecture",
    ],
    "security": [
        "JWT token validation",
        "SQL injection prevention",
        "cross-site scripting defenses",
        "certificate pinning strategies",
        "secrets management patterns",
        "RBAC authorization models",
        "input sanitization techniques",
        "CORS policy configuration",
        "encryption at rest strategies",
        "audit logging best practices",
    ],
}

SECTION_TEMPLATES = [
    "Overview",
    "Core Concepts",
    "Implementation Details",
    "Trade-offs and Considerations",
    "Best Practices",
    "Common Pitfalls",
    "Performance Characteristics",
    "Real-world Applications",
    "Comparison with Alternatives",
    "Monitoring and Observability",
]

VOCABULARY = {
    "machine_learning": [
        "model",
        "training",
        "inference",
        "loss",
        "gradient",
        "epoch",
        "batch",
        "layer",
        "activation",
        "weights",
        "bias",
        "regularization",
        "dropout",
        "learning rate",
        "optimizer",
        "convergence",
        "overfitting",
        "underfitting",
        "validation",
        "cross-validation",
        "precision",
        "recall",
        "F1 score",
        "embedding",
        "latent space",
        "backpropagation",
        "tensor",
        "pipeline",
    ],
    "systems_design": [
        "throughput",
        "latency",
        "availability",
        "partition tolerance",
        "consistency",
        "replication",
        "failover",
        "load balancing",
        "horizontal scaling",
        "vertical scaling",
        "service discovery",
        "health check",
        "deployment",
        "rollback",
        "canary release",
        "blue-green deployment",
        "observability",
        "tracing",
        "metrics",
        "alerting",
        "container",
        "orchestration",
        "idempotent",
        "eventual consistency",
        "CAP theorem",
    ],
    "databases": [
        "index",
        "query plan",
        "transaction",
        "isolation level",
        "deadlock",
        "normalization",
        "denormalization",
        "partition",
        "shard",
        "replica",
        "WAL",
        "checkpoint",
        "vacuum",
        "ACID",
        "BASE",
        "primary key",
        "foreign key",
        "join",
        "subquery",
        "materialized view",
        "connection pool",
        "prepared statement",
        "cursor",
        "batch insert",
        "bulk load",
    ],
    "apis": [
        "endpoint",
        "request",
        "response",
        "status code",
        "header",
        "payload",
        "serialization",
        "deserialization",
        "middleware",
        "interceptor",
        "retry",
        "timeout",
        "circuit breaker",
        "backoff",
        "throttling",
        "authentication",
        "authorization",
        "token",
        "scope",
        "grant type",
        "schema",
        "validation",
        "documentation",
        "versioning",
        "deprecation",
    ],
    "networking": [
        "packet",
        "socket",
        "port",
        "protocol",
        "handshake",
        "bandwidth",
        "throughput",
        "jitter",
        "round-trip time",
        "hop",
        "routing table",
        "subnet",
        "CIDR",
        "firewall",
        "proxy",
        "certificate",
        "cipher suite",
        "session",
        "connection pool",
        "keep-alive",
        "DNS record",
        "TTL",
        "load balancer",
        "reverse proxy",
        "CDN",
    ],
    "security": [
        "vulnerability",
        "exploit",
        "patch",
        "encryption",
        "decryption",
        "hash",
        "salt",
        "token",
        "certificate",
        "key rotation",
        "access control",
        "privilege escalation",
        "audit trail",
        "compliance",
        "penetration test",
        "threat model",
        "attack surface",
        "zero-day",
        "sandbox",
        "isolation",
        "authentication factor",
        "session management",
        "input validation",
        "output encoding",
        "security header",
    ],
}


def _generate_sentence(rng: random.Random, vocab: list[str]) -> str:
    templates = [
        "The {noun} is essential for achieving optimal {adj} in production systems.",
        "When implementing {noun}, engineers must consider the impact on {adj}.",
        "A well-designed {noun} approach ensures reliable {adj} under load.",
        "Modern architectures leverage {noun} to improve {adj} significantly.",
        "Understanding {noun} helps teams avoid common issues with {adj}.",
        "The relationship between {noun} and {adj} is critical for system reliability.",
        "Teams often underestimate the complexity of {noun} when scaling {adj}.",
        "Best practices for {noun} include careful monitoring of {adj} metrics.",
        "Production deployments require robust {noun} strategies alongside {adj}.",
        "The evolution of {noun} has transformed how we approach {adj}.",
        "Careful tuning of {noun} parameters directly affects {adj} outcomes.",
        "Organizations that invest in {noun} see measurable improvements in {adj}.",
    ]
    template = rng.choice(templates)
    return template.format(noun=rng.choice(vocab), adj=rng.choice(vocab))


def _generate_paragraph(
    rng: random.Random, vocab: list[str], min_sentences: int = 3, max_sentences: int = 7
) -> str:
    n = rng.randint(min_sentences, max_sentences)
    return " ".join(_generate_sentence(rng, vocab) for _ in range(n))


def _generate_document(
    rng: random.Random, doc_id: int, category: str, topic: str
) -> tuple[str, dict]:
    vocab = VOCABULARY[category]
    title = f"{topic.title()}: A Technical Deep Dive"

    num_sections = rng.randint(2, 5)
    sections = rng.sample(SECTION_TEMPLATES, num_sections)

    lines = [f"# {title}", ""]

    for section in sections:
        lines.append(f"## {section}")
        lines.append("")
        num_paragraphs = rng.randint(1, 3)
        for _ in range(num_paragraphs):
            lines.append(_generate_paragraph(rng, vocab))
            lines.append("")

    content = "\n".join(lines)
    word_count = len(content.split())

    metadata = {
        "doc_id": f"doc_{doc_id:05d}",
        "title": title,
        "category": category,
        "word_count": word_count,
        "generated_at": datetime.now(UTC).isoformat(),
    }

    return content, metadata


def generate_corpus(output_dir: Path, num_docs: int = 10_000, seed: int = 42) -> None:
    """Generate synthetic technical documents."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    manifest_entries = []

    for i in range(num_docs):
        category = rng.choice(CATEGORIES)
        topic = rng.choice(TOPICS[category])
        content, metadata = _generate_document(rng, i, category, topic)

        # Ensure word count is in range by padding or trimming
        words = content.split()
        while len(words) < 200:
            extra = _generate_paragraph(rng, VOCABULARY[category])
            content += "\n" + extra
            words = content.split()

        if len(words) > 800:
            words = words[:800]
            content = " ".join(words)

        metadata["word_count"] = len(content.split())

        filename = f"doc_{i:05d}.txt"
        (output_dir / filename).write_text(content, encoding="utf-8")
        manifest_entries.append(metadata)

    manifest_path = output_dir / "manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as f:
        for entry in manifest_entries:
            f.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate synthetic technical corpus")
    parser.add_argument("--num-docs", type=int, default=10_000, help="Number of documents")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory")
    args = parser.parse_args()

    default_path = Path(__file__).resolve().parent.parent / "data" / "corpus"
    corpus_path = Path(args.output_dir) if args.output_dir else default_path
    print(f"Generating {args.num_docs} documents in {corpus_path}...")
    generate_corpus(output_dir=corpus_path, num_docs=args.num_docs, seed=args.seed)
    print("Done.")
