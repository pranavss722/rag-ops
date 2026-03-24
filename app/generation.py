"""Generation module — LLM-powered answer synthesis."""

from openai import OpenAI
from pydantic import BaseModel

from app.retrieval import RetrievalResult

SYSTEM_PROMPT = """\
You are a helpful technical assistant. Answer the user's question using ONLY the \
provided context chunks. Cite sources by filename in square brackets (e.g. [doc_001.txt]).

If the context does not contain enough information to answer, say so explicitly. \
Do not make up information."""

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


class GenerationResult(BaseModel):
    """Result from the LLM generation step."""

    answer: str
    usage: dict
    model: str


def build_prompt(query: str, chunks: list[RetrievalResult]) -> str:
    """Build a prompt with context chunks and the user query."""
    context_parts = []
    for i, chunk in enumerate(chunks):
        source = chunk.metadata.get("source", "unknown")
        context_parts.append(f"[{source}] (chunk {i}):\n{chunk.content}")

    context_block = "\n\n---\n\n".join(context_parts)

    return f"""{SYSTEM_PROMPT}

## Context

{context_block}

## Question

{query}"""


def generate_answer(prompt: str, model: str = "gpt-4o") -> GenerationResult:
    """Call the LLM and return a structured result."""
    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        max_tokens=1024,
    )

    return GenerationResult(
        answer=response.choices[0].message.content or "",
        usage={
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        },
        model=response.model,
    )
