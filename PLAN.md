# RAG Pipeline — Implementation Plan

> **Rule:** No implementation code until this plan is approved.
> Every task follows TDD: write the failing test FIRST, then implement.

---

## Milestone 1: Environment & Corpus

### M1-T1: Verify dev environment boots
- **File:** `tests/test_health.py` (already exists)
- **Test (Red):** `pytest tests/test_health.py` passes with the existing health check test.
- **Work:** `pip install -e ".[dev]"`, verify pytest + ruff work.
- **Done when:** `pytest -xvs` green, `ruff check .` clean.

### M1-T2: Create corpus generation script
- **File:** `scripts/generate_corpus.py`
- **Test (Red):** `tests/test_corpus.py::test_generate_corpus_creates_files` — assert script produces exactly 10,000 `.txt` files in `data/corpus/`, each non-empty, with deterministic content (same seed = same output).
- **Work:** Generate synthetic technical docs (topics: APIs, databases, ML, networking, security, etc.). Use `random` with fixed seed. Each doc: 200–800 words, has a title line and 2–5 sections with headers.
- **Done when:** Test green. Running script twice produces identical output.

### M1-T3: Add corpus metadata manifest
- **File:** `scripts/generate_corpus.py` (modify)
- **Test (Red):** `tests/test_corpus.py::test_manifest_json_created` — assert `data/corpus/manifest.json` is written with 10,000 entries, each having `filename`, `title`, `topic`, `num_sections`.
- **Work:** Write manifest alongside docs.
- **Done when:** Test green. Manifest is valid JSON matching file count.

---

## Milestone 2: Ingestion Pipeline

### M2-T1: Implement document loader
- **File:** `app/ingestion.py`
- **Test (Red):** `tests/test_ingestion.py::test_load_documents_returns_langchain_docs` — given a temp dir with 3 `.txt` files, `load_documents(path)` returns a list of 3 LangChain `Document` objects with correct `page_content` and `metadata["source"]`.
- **Work:** Use `DirectoryLoader` or manual loader. Populate `metadata` with source filename.
- **Done when:** Test green.

### M2-T2: Implement recursive chunker
- **File:** `app/ingestion.py`
- **Test (Red):** `tests/test_ingestion.py::test_chunk_documents_splits_correctly` — given a single 2000-char document, `chunk_documents([doc])` returns multiple chunks. Assert each chunk ≤ 512 tokens, overlap exists between consecutive chunks, and metadata contains `source`, `chunk_index`, `section_header`.
- **Work:** `RecursiveCharacterTextSplitter` with `chunk_size=512`, `chunk_overlap=64` (token-based via tiktoken). Extract section header from nearest `#` line above chunk start.
- **Done when:** Test green. Metadata fields present on every chunk.

### M2-T3: Implement embedding + FAISS index builder
- **File:** `app/ingestion.py`
- **Test (Red):** `tests/test_ingestion.py::test_build_index_creates_faiss_store` — given 10 chunks, `build_index(chunks)` returns a FAISS vectorstore. Assert `store.index.ntotal == 10`. Mock the OpenAI embedding call.
- **Work:** Use `OpenAIEmbeddings` + `FAISS.from_documents()`. Save index to `data/faiss_index/`.
- **Done when:** Test green. Index file written to disk.

### M2-T4: Implement index persistence (save/load)
- **File:** `app/ingestion.py`
- **Test (Red):** `tests/test_ingestion.py::test_save_and_load_index_roundtrip` — build an index, save it, load it back, assert `ntotal` matches and a similarity search returns results.
- **Work:** `FAISS.save_local()` / `FAISS.load_local()`.
- **Done when:** Test green. Roundtrip preserves all vectors.

### M2-T5: Create end-to-end ingestion CLI
- **File:** `scripts/ingest.py`
- **Test (Red):** `tests/test_ingestion.py::test_ingest_cli_builds_index` — run `ingest.py` against a small temp corpus (5 docs), assert FAISS index exists and `ntotal > 0`.
- **Work:** CLI script: load → chunk → embed → save. Print stats (doc count, chunk count, index size).
- **Done when:** Test green. Script runs end-to-end.

---

## Milestone 3: Retrieval

### M3-T1: Implement query embedding
- **File:** `app/retrieval.py`
- **Test (Red):** `tests/test_retrieval.py::test_embed_query_returns_vector` — `embed_query("test question")` returns a list of floats with length matching embedding dimension. Mock OpenAI.
- **Work:** Thin wrapper around `OpenAIEmbeddings.embed_query()`.
- **Done when:** Test green.

### M3-T2: Implement FAISS search
- **File:** `app/retrieval.py`
- **Test (Red):** `tests/test_retrieval.py::test_search_returns_top_k_with_scores` — given a pre-built index with 20 chunks, `search(query, k=5)` returns exactly 5 results, each with `document`, `score`, and correct metadata.
- **Work:** `FAISS.similarity_search_with_score()`. Return structured results.
- **Done when:** Test green. Results sorted by score.

### M3-T3: Define retrieval result schema
- **File:** `app/retrieval.py`
- **Test (Red):** `tests/test_retrieval.py::test_retrieval_result_schema` — assert `RetrievalResult` has fields: `content: str`, `score: float`, `metadata: dict`. Validate with sample data.
- **Work:** Pydantic model for retrieval results.
- **Done when:** Test green. Schema validates correctly.

---

## Milestone 4: Generation

### M4-T1: Implement prompt builder
- **File:** `app/generation.py`
- **Test (Red):** `tests/test_generation.py::test_build_prompt_includes_context_and_query` — `build_prompt(query, chunks)` returns a string containing the query text and all chunk contents. Assert context section and question section are both present.
- **Work:** Jinja2 or f-string template. System prompt instructs grounded answers with citations.
- **Done when:** Test green. Prompt includes all chunks and the user query.

### M4-T2: Implement LLM call wrapper
- **File:** `app/generation.py`
- **Test (Red):** `tests/test_generation.py::test_generate_answer_returns_response` — `generate_answer(prompt)` returns a `GenerationResult` with `answer: str`, `usage: dict` (prompt_tokens, completion_tokens, total_tokens). Mock OpenAI.
- **Work:** Call `openai.chat.completions.create()`. Parse response + usage.
- **Done when:** Test green. Usage dict has all 3 token fields.

### M4-T3: Define generation result schema
- **File:** `app/generation.py`
- **Test (Red):** `tests/test_generation.py::test_generation_result_schema` — validate `GenerationResult` Pydantic model with `answer`, `usage`, `model` fields.
- **Work:** Pydantic model.
- **Done when:** Test green.

---

## Milestone 5: Tracing

### M5-T1: Initialize Langfuse client
- **File:** `app/tracing.py`
- **Test (Red):** `tests/test_tracing.py::test_get_langfuse_client_returns_instance` — `get_langfuse()` returns a `Langfuse` instance. Uses env vars. Test with mock/dummy credentials.
- **Work:** Singleton Langfuse client from env vars.
- **Done when:** Test green.

### M5-T2: Implement trace context manager
- **File:** `app/tracing.py`
- **Test (Red):** `tests/test_tracing.py::test_trace_context_creates_trace` — `create_trace(name, metadata)` returns a trace object with correct name. Mock Langfuse.
- **Work:** Wrapper that creates a Langfuse trace and yields it.
- **Done when:** Test green.

### M5-T3: Implement span helpers for each pipeline stage
- **File:** `app/tracing.py`
- **Test (Red):** `tests/test_tracing.py::test_span_helpers_record_correct_metrics` — call each span helper (`span_embed`, `span_retrieve`, `span_generate`, `span_cost`) with sample data. Assert each records the expected `name`, `input`, `output`, and `metadata`. Mock Langfuse.
- **Work:** 4 functions, one per span type. Each takes a trace + metrics dict and creates a span.
- **Done when:** Test green. All 4 spans produce correct structure.

### M5-T4: Define pricing lookup table
- **File:** `app/tracing.py`
- **Test (Red):** `tests/test_tracing.py::test_calculate_cost_for_known_model` — `calculate_cost(model="gpt-4o", prompt_tokens=1000, completion_tokens=500)` returns expected USD float based on known pricing.
- **Work:** Dict mapping model names to (prompt_price_per_1k, completion_price_per_1k). Pure function.
- **Done when:** Test green. Covers gpt-4o, gpt-4o-mini, text-embedding-3-small.

---

## Milestone 6: FastAPI `/query` Endpoint

### M6-T1: Define request/response schemas
- **File:** `app/main.py`
- **Test (Red):** `tests/test_api.py::test_query_request_schema_validation` — assert `QueryRequest` requires `question: str` and optional `top_k: int = 5`. Assert `QueryResponse` has `answer`, `sources`, `trace_id`, `latency_ms`, `cost_usd`.
- **Work:** Pydantic models.
- **Done when:** Test green.

### M6-T2: Implement /query endpoint orchestration
- **File:** `app/main.py`
- **Test (Red):** `tests/test_api.py::test_query_endpoint_returns_answer` — POST `/query` with `{"question": "What is an API?"}`. Mock retrieval + generation. Assert 200 response with all `QueryResponse` fields populated.
- **Work:** Wire together: embed query → FAISS search → build prompt → LLM call → trace. Return structured response.
- **Done when:** Test green. All pipeline stages called in order.

### M6-T3: Add error handling for /query
- **File:** `app/main.py`
- **Test (Red):** `tests/test_api.py::test_query_endpoint_handles_empty_index` — POST `/query` when no index exists returns 503 with meaningful error message.
- **Work:** Graceful error handling for missing index, LLM failures, empty results.
- **Done when:** Test green.

---

## Milestone 7: RAGAS Evaluation

### M7-T1: Create evaluation dataset generator
- **File:** `scripts/generate_eval_set.py`
- **Test (Red):** `tests/test_evaluation.py::test_eval_set_has_required_columns` — generated eval set is a list of dicts with keys: `question`, `ground_truth`, `context_source`.
- **Work:** Generate 50 Q&A pairs derived from the synthetic corpus. Deterministic (seeded).
- **Done when:** Test green. 50 pairs with non-empty values.

### M7-T2: Implement RAGAS evaluation runner
- **File:** `scripts/evaluate.py`
- **Test (Red):** `tests/test_evaluation.py::test_ragas_runner_returns_scores` — `run_evaluation(eval_set, pipeline)` returns dict with keys: `faithfulness`, `answer_relevancy`, `context_precision`. Mock the pipeline calls.
- **Work:** Use RAGAS `evaluate()` with the 3 metrics. Feed through our pipeline.
- **Done when:** Test green. All 3 scores are floats in [0, 1].

### M7-T3: Push RAGAS scores to Langfuse
- **File:** `scripts/evaluate.py`
- **Test (Red):** `tests/test_evaluation.py::test_scores_pushed_to_langfuse` — after evaluation, assert Langfuse `score()` was called once per metric per sample. Mock Langfuse.
- **Work:** Log each score as a Langfuse score attached to the trace.
- **Done when:** Test green.

---

## Milestone 8: Cost Dashboard

### M8-T1: Implement per-query cost metadata
- **File:** `app/tracing.py` (modify)
- **Test (Red):** `tests/test_tracing.py::test_cost_metadata_attached_to_trace` — after a full traced query, the trace metadata contains `cost_usd`, `prompt_tokens`, `completion_tokens`, `embedding_tokens`.
- **Work:** `span_cost` helper aggregates all token counts and calculates total cost. Attaches as trace-level metadata.
- **Done when:** Test green.

### M8-T2: Add /stats endpoint
- **File:** `app/main.py`
- **Test (Red):** `tests/test_api.py::test_stats_endpoint_returns_aggregates` — GET `/stats` returns `total_queries`, `avg_latency_ms`, `avg_cost_usd`, `total_cost_usd`. Mock underlying data.
- **Work:** Simple in-memory counter (or query Langfuse API). Aggregates over recent queries.
- **Done when:** Test green.

---

## Milestone 9: Docker & Deployment Readiness

### M9-T1: Create application Dockerfile
- **File:** `Dockerfile`
- **Test (Red):** `tests/test_docker.py::test_dockerfile_exists_and_valid` — assert `Dockerfile` exists, contains `FROM python`, `EXPOSE`, and `CMD` with uvicorn.
- **Work:** Multi-stage build. Python 3.11-slim. Install deps, copy app, run uvicorn.
- **Done when:** Test green. `docker build .` succeeds.

### M9-T2: Add app service to docker-compose.yml
- **File:** `docker-compose.yml` (modify)
- **Test (Red):** `tests/test_docker.py::test_compose_has_app_service` — parse `docker-compose.yml`, assert `app` service exists with correct deps, ports, env vars.
- **Work:** Add `app` service depending on `langfuse`, `redis`. Mount `.env`. Expose 8000.
- **Done when:** Test green.

### M9-T3: Create startup check script
- **File:** `scripts/healthcheck.py`
- **Test (Red):** `tests/test_docker.py::test_healthcheck_script_returns_status` — `healthcheck.py` hits `/health` and returns 0 on success, 1 on failure. Mock httpx.
- **Work:** Simple script for Docker HEALTHCHECK directive.
- **Done when:** Test green.

### M9-T4: Write README.md
- **File:** `README.md`
- **Test (Red):** N/A (documentation).
- **Work:** Quick-start guide: clone → `.env` → `docker compose up` → generate corpus → ingest → query. Architecture diagram (mermaid). Links to DESIGN.md and PLAN.md.
- **Done when:** A new dev can go from clone to working query in < 5 minutes.

---

## Dependency Graph

```
M1-T1 ──► M1-T2 ──► M1-T3
                │
                ▼
M2-T1 ──► M2-T2 ──► M2-T3 ──► M2-T4 ──► M2-T5
                                            │
                ┌───────────────────────────┘
                ▼
M3-T1 ──► M3-T2 ──► M3-T3
                       │
                       ▼
M4-T1 ──► M4-T2 ──► M4-T3
                       │
                       ▼
M5-T1 ──► M5-T2 ──► M5-T3 ──► M5-T4
                                 │
                ┌────────────────┘
                ▼
M6-T1 ──► M6-T2 ──► M6-T3
            │          │
            ▼          ▼
M7-T1 ──► M7-T2 ──► M7-T3      M8-T1 ──► M8-T2
                                             │
                                             ▼
                                M9-T1 ──► M9-T2 ──► M9-T3 ──► M9-T4
```

---

**Total: 9 milestones, 28 tasks. Each task < 5 minutes. All TDD.**
