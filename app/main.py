"""FastAPI application entry point for the RAG Pipeline."""

import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel

from app.generation import build_prompt, generate_answer
from app.retrieval import search
from app.tracing import calculate_cost

app = FastAPI(title="RAG Pipeline", version="0.1.0")

INDEX_DIR = Path("data/faiss_index")

# In-memory query stats for the /stats endpoint
query_stats: list[dict] = []


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5


class QueryResponse(BaseModel):
    answer: str
    sources: list[dict]
    trace_id: str
    latency_ms: float
    cost_usd: float


def _get_index() -> FAISS | None:
    """Load the FAISS index from disk, or return None if it doesn't exist."""
    if not INDEX_DIR.exists():
        return None
    try:
        return FAISS.load_local(
            str(INDEX_DIR),
            OpenAIEmbeddings(model="text-embedding-3-small"),
            allow_dangerous_deserialization=True,
        )
    except Exception:
        return None


def _trace_query(latency_ms: float, cost_usd: float, **kwargs) -> str:
    """Send tracing data to Langfuse. Returns trace ID."""
    try:
        from app.tracing import (
            create_trace,
            get_langfuse,
            span_cost,
            span_embed,
            span_generate,
            span_retrieve,
        )

        client = get_langfuse()
        trace = create_trace(client, name="rag-query", metadata=kwargs.get("metadata"))
        if "embed_ms" in kwargs:
            span_embed(trace, latency_ms=kwargs["embed_ms"], model=kwargs.get("embed_model", ""))
        if "retrieve_ms" in kwargs:
            span_retrieve(
                trace,
                latency_ms=kwargs["retrieve_ms"],
                top_k_scores=kwargs.get("scores", []),
                k=kwargs.get("k", 5),
            )
        if "generate_ms" in kwargs:
            span_generate(
                trace,
                latency_ms=kwargs["generate_ms"],
                model=kwargs.get("model", ""),
                prompt_tokens=kwargs.get("prompt_tokens", 0),
                completion_tokens=kwargs.get("completion_tokens", 0),
                total_tokens=kwargs.get("total_tokens", 0),
            )
        span_cost(trace, cost_usd=cost_usd, breakdown=kwargs.get("cost_breakdown", {}))
        return trace.id
    except Exception:
        return "trace-unavailable"


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    start = time.perf_counter()

    index = _get_index()
    if index is None:
        raise HTTPException(
            status_code=503, detail="FAISS index not available. Run ingestion first."
        )

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    results = search(req.question, store=index, embeddings=embeddings, k=req.top_k)
    prompt = build_prompt(req.question, results)
    gen = generate_answer(prompt)

    latency_ms = (time.perf_counter() - start) * 1000
    cost_usd = calculate_cost(
        gen.model, gen.usage["prompt_tokens"], gen.usage["completion_tokens"]
    )

    trace_id = _trace_query(
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        model=gen.model,
        prompt_tokens=gen.usage["prompt_tokens"],
        completion_tokens=gen.usage["completion_tokens"],
        total_tokens=gen.usage["total_tokens"],
    )

    query_stats.append({"latency_ms": round(latency_ms, 2), "cost_usd": cost_usd})

    return QueryResponse(
        answer=gen.answer,
        sources=[{"source": r.metadata.get("source", ""), "score": r.score} for r in results],
        trace_id=trace_id,
        latency_ms=round(latency_ms, 2),
        cost_usd=cost_usd,
    )


@app.get("/stats")
async def stats() -> dict:
    if not query_stats:
        return {"total_queries": 0, "avg_latency_ms": 0, "avg_cost_usd": 0, "total_cost_usd": 0}

    total = len(query_stats)
    total_cost = sum(s["cost_usd"] for s in query_stats)
    total_latency = sum(s["latency_ms"] for s in query_stats)

    return {
        "total_queries": total,
        "avg_latency_ms": round(total_latency / total, 2),
        "avg_cost_usd": round(total_cost / total, 6),
        "total_cost_usd": round(total_cost, 6),
    }
