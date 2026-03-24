# RAG Ops — Architectural Design

## Decision 1: Corpus & Data Strategy

**Choice:** Synthetic 10K technical documents, generated via a reproducible script.

- Dataset is fully self-contained — no external downloads or proprietary data.
- Script lives in `scripts/generate_corpus.py` and is deterministic (seeded).
- Output goes to `data/` directory (gitignored except `.gitkeep`).
- Portfolio-friendly: any reviewer can `python scripts/generate_corpus.py` and get the same dataset.

## Decision 2: Chunking Strategy

**Choice:** Recursive character splitting — 512 tokens, 64-token overlap.

- Use LangChain's `RecursiveCharacterTextSplitter`.
- Metadata preserved per chunk:
  - `source` — original filename
  - `chunk_index` — integer position within the document
  - `section_header` — detected heading if present, else `null`
- Chunk size tuned for `text-embedding-3-small` context window.
- Overlap ensures no context is lost at chunk boundaries.

## Decision 3: Observability — Langfuse Tracing

**Choice:** Full-loop tracing on every request with 4 dedicated spans.

| Span                | Metrics Captured                              |
|---------------------|-----------------------------------------------|
| `embed_query`       | Embedding latency (ms), model name            |
| `faiss_retrieval`   | Retrieval latency (ms), top-k scores, k value |
| `llm_generation`    | LLM latency (ms), prompt/completion/total tokens, model name |
| `cost_calculation`  | Cost-per-query (USD), computed from token counts x model pricing |

- Every `/query` request produces a single Langfuse **trace** containing these spans.
- Enables a real cost/latency dashboard in Langfuse UI — not just logs.
- Token-based cost calculation uses a pricing lookup table (configurable per model).

## Resolved Decisions

- [x] **Embedding model:** `text-embedding-3-small` (1536-dim) — best cost/performance ratio for this corpus size. `text-embedding-3-large` offered no measurable retrieval improvement on synthetic docs.
- [x] **Generation LLM:** `gpt-4o` at temperature 0 — deterministic outputs for reproducible evaluation. Model is configurable via `generate_answer(prompt, model=...)`.
- [x] **Retrieval:** Pure FAISS with top-k=5 — hybrid BM25+FAISS adds complexity without benefit on a homogeneous synthetic corpus. FAISS alone provides sub-millisecond search over 91K vectors.
- [x] **Re-ranking:** None — cross-encoder re-ranking is unnecessary at k=5. The FAISS distance scores provide sufficient ranking signal.
- [x] **Guardrails:** Citation grounding via system prompt (model must cite `[source_filename]`). No PII filtering needed (synthetic corpus). RAGAS evaluation runs as a separate offline step, not per-response.
