"""Observability module — Langfuse tracing integration."""

from langfuse import Langfuse

# Pricing per 1M tokens (prompt, completion)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
}


def get_langfuse() -> Langfuse:
    """Create and return a Langfuse client (reads config from env vars)."""
    return Langfuse()


def create_trace(client: Langfuse, name: str, metadata: dict | None = None):
    """Create a new Langfuse trace."""
    return client.trace(name=name, metadata=metadata)


def span_embed(trace, latency_ms: float, model: str) -> None:
    """Record an embedding span."""
    trace.span(
        name="embed_query",
        input={"model": model},
        output={"latency_ms": latency_ms},
    )


def span_retrieve(trace, latency_ms: float, top_k_scores: list[float], k: int) -> None:
    """Record a FAISS retrieval span."""
    trace.span(
        name="faiss_retrieval",
        input={"k": k},
        output={"latency_ms": latency_ms, "top_k_scores": top_k_scores},
    )


def span_generate(
    trace,
    latency_ms: float,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
) -> None:
    """Record an LLM generation span."""
    trace.span(
        name="llm_generation",
        input={"model": model},
        output={
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
    )


def span_cost(trace, cost_usd: float, breakdown: dict) -> None:
    """Record a cost calculation span."""
    trace.span(
        name="cost_calculation",
        input={"breakdown": breakdown},
        output={"cost_usd": cost_usd},
    )


def _normalize_model(model: str) -> str:
    """Normalize model name by stripping date suffixes (e.g. gpt-4o-2024-08-06 -> gpt-4o)."""
    for key in sorted(MODEL_PRICING, key=len, reverse=True):
        if model.startswith(key):
            return key
    return model


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost in USD for a given model and token counts."""
    normalized = _normalize_model(model)
    prompt_price, completion_price = MODEL_PRICING.get(normalized, (0.0, 0.0))
    return (prompt_tokens * prompt_price / 1_000_000) + (
        completion_tokens * completion_price / 1_000_000
    )


def build_cost_metadata(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    embedding_tokens: int = 0,
) -> dict:
    """Build cost metadata dict for attaching to a Langfuse trace."""
    gen_cost = calculate_cost(model, prompt_tokens, completion_tokens)
    embed_cost = calculate_cost("text-embedding-3-small", embedding_tokens, 0)
    return {
        "cost_usd": gen_cost + embed_cost,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "embedding_tokens": embedding_tokens,
    }
