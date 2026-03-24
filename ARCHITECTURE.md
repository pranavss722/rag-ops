# Architecture

## Module Responsibilities

| Module | File | Responsibility | Dependencies |
|--------|------|---------------|-------------|
| **API Layer** | `app/main.py` | HTTP endpoints, request validation, orchestration | All modules below |
| **Ingestion** | `app/ingestion.py` | Document loading, recursive chunking, FAISS index build/save/load | LangChain, FAISS |
| **Retrieval** | `app/retrieval.py` | Query embedding, vector similarity search, result schema | FAISS, OpenAI Embeddings |
| **Generation** | `app/generation.py` | Prompt construction with citation template, LLM call, response parsing | OpenAI Chat API |
| **Tracing** | `app/tracing.py` | Langfuse client, span helpers (4 span types), cost calculation | Langfuse SDK |
| **Corpus Generator** | `scripts/generate_corpus.py` | Deterministic synthetic document creation (seeded RNG) | None (stdlib only) |
| **Ingestion CLI** | `scripts/ingest.py` | End-to-end pipeline: load -> chunk -> embed -> save | `app/ingestion` |
| **Evaluation** | `scripts/evaluate.py` | RAGAS metric computation, Langfuse score push | RAGAS, Langfuse |

## Data Flow

### Ingestion (Offline)

```
data/corpus/*.txt
    |
    v
load_documents()          Read .txt files -> LangChain Document objects
    |                     Metadata: {source: filename}
    v
chunk_documents()         RecursiveCharacterTextSplitter
    |                     512 chars per chunk, 64 char overlap
    |                     Metadata added: {chunk_index, section_header}
    v
build_index()             OpenAI text-embedding-3-small -> FAISS.from_documents()
    |
    v
save_index()              FAISS.save_local() -> data/faiss_index/
```

### Query (Online)

```
POST /query {question, top_k}
    |
    v
_get_index()              Load FAISS index from disk (lazy, per-request)
    |
    v
search()                  Embed query -> FAISS.similarity_search_with_score()
    |                     Returns: list[RetrievalResult] with content, score, metadata
    v
build_prompt()            Inject retrieved chunks into citation-grounded template
    |                     Each chunk labeled with [source_filename]
    v
generate_answer()         OpenAI gpt-4o chat completion (temperature=0)
    |                     Returns: GenerationResult with answer, usage, model
    v
calculate_cost()          Token counts x model pricing table -> USD
    |
    v
_trace_query()            4 Langfuse spans: embed, retrieve, generate, cost
    |
    v
QueryResponse             {answer, sources, trace_id, latency_ms, cost_usd}
```

## Key Design Decisions

### 1. TDD from Day One

Every function was written test-first: failing test -> minimal implementation -> green -> refactor. This produced 34 tests covering all modules before any integration was attempted.

**Why:** A RAG pipeline has many failure modes (bad embeddings, empty retrieval, LLM refusals, tracing failures). Tests at every layer catch regressions early and serve as living documentation of expected behavior.

### 2. Decoupled Modules

Each module (`ingestion`, `retrieval`, `generation`, `tracing`) is independently testable with no cross-imports between peer modules. The API layer (`main.py`) is the only orchestrator.

**Why:** This allows swapping components without cascading changes. Want to replace FAISS with Pinecone? Only `ingestion.py` and `retrieval.py` change. Want to switch from GPT-4o to Claude? Only `generation.py` changes. Tests for unrelated modules remain green.

### 3. Lazy Client Initialization

The OpenAI client in `generation.py` uses a lazy singleton pattern (`_get_client()`). The FAISS index in `main.py` is loaded per-request via `_get_index()`. Neither is instantiated at import time.

**Why:** Module-level `OpenAI()` calls fail at import time if `OPENAI_API_KEY` isn't set, breaking test collection for every test file that transitively imports the module. Lazy init means tests can import and mock without needing real credentials.

### 4. Tracing Never Breaks the Query Path

The `_trace_query()` function wraps all Langfuse calls in a `try/except` that returns `"trace-unavailable"` on any failure. Tracing is fire-and-forget.

**Why:** Observability is critical but not on the critical path. If Langfuse is down, misconfigured, or not running (local dev without Docker), queries must still work. The alternative -- letting tracing exceptions propagate -- would mean a monitoring outage causes a service outage. This is unacceptable in production.

### 5. Deterministic Synthetic Corpus

The corpus generator uses `random.Random(seed=42)` (not `random.seed()` global state) for reproducibility. Running with the same seed always produces identical documents.

**Why:** A portfolio project must be self-contained. Any reviewer can clone the repo, run the generator, and get the exact same dataset -- making results reproducible, benchmarks comparable, and the demo fully offline (no dataset downloads).

### 6. Embeddings Injected, Not Hardcoded

`build_index()`, `search()`, and `run_ingestion()` all accept an `embeddings` parameter rather than constructing their own `OpenAIEmbeddings` internally.

**Why:** This is what makes the test suite fast and free. Tests inject `FakeEmbeddings` (deterministic, zero-cost) while production code passes `OpenAIEmbeddings`. Dependency injection at the function level -- no framework needed.

## Cost Model

Every query's cost is calculated from token counts and a pricing lookup table:

```python
MODEL_PRICING = {
    "gpt-4o":                   ($2.50/1M prompt,  $10.00/1M completion),
    "gpt-4o-mini":              ($0.15/1M prompt,   $0.60/1M completion),
    "text-embedding-3-small":   ($0.02/1M tokens,   $0.00),
    "text-embedding-3-large":   ($0.13/1M tokens,   $0.00),
}
```

**Per-query cost breakdown:**

| Step | Typical Tokens | Estimated Cost |
|------|---------------|----------------|
| Embed query | ~20 tokens | ~$0.0000004 |
| LLM prompt (context + query) | ~800 tokens | ~$0.002 |
| LLM completion | ~150 tokens | ~$0.0015 |
| **Total per query** | ~970 tokens | **~$0.0017** |

At 1,000 queries/day, estimated daily cost: **~$1.70**

The model name normalizer (`_normalize_model`) handles OpenAI's versioned model strings (e.g., `gpt-4o-2024-08-06` -> `gpt-4o`) by matching the longest known prefix, ensuring cost tracking works regardless of which model snapshot the API returns.

The `/stats` endpoint aggregates these per-query costs into session-level metrics, giving immediate visibility into total spend without needing to open the Langfuse dashboard.
