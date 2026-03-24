"""Tests for the ingestion pipeline."""

from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings


def _create_sample_files(tmp_path: Path, count: int = 3) -> Path:
    """Create sample .txt files in a temp directory."""
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    for i in range(count):
        (corpus_dir / f"doc_{i:03d}.txt").write_text(
            f"# Document {i}\n\n## Section A\n\nThis is sample content for document {i}. "
            f"It contains enough text to be meaningful for testing purposes.\n",
            encoding="utf-8",
        )
    return corpus_dir


def test_load_documents_returns_langchain_docs(tmp_path):
    from app.ingestion import load_documents

    corpus_dir = _create_sample_files(tmp_path, count=3)
    docs = load_documents(corpus_dir)

    assert len(docs) == 3
    for doc in docs:
        assert isinstance(doc, Document)
        assert len(doc.page_content) > 0
        assert "source" in doc.metadata


def test_chunk_documents_splits_correctly():
    from app.ingestion import chunk_documents

    # Create a document long enough to be split into multiple chunks
    long_content = (
        "# Main Title\n\n## Section One\n\n"
        + ("This is a test sentence with enough words to fill up space. " * 120)
        + "\n\n## Section Two\n\n"
        + ("Another paragraph with different content for the second section. " * 120)
    )
    doc = Document(page_content=long_content, metadata={"source": "test.txt"})

    chunks = chunk_documents([doc])

    assert len(chunks) > 1, "Document should be split into multiple chunks"

    for i, chunk in enumerate(chunks):
        assert isinstance(chunk, Document)
        assert len(chunk.page_content) > 0
        assert chunk.metadata["source"] == "test.txt"
        assert chunk.metadata["chunk_index"] == i
        assert "section_header" in chunk.metadata


def test_chunk_documents_preserves_overlap():
    from app.ingestion import chunk_documents

    # Use varied words so overlap detection is meaningful
    words = [f"word{i}" for i in range(2000)]
    long_content = "# Title\n\n## Section\n\n" + " ".join(words)
    doc = Document(page_content=long_content, metadata={"source": "overlap.txt"})

    chunks = chunk_documents([doc])

    assert len(chunks) >= 2, "Expected multiple chunks"
    # Check overlap between non-header chunks (skip first if it's just the header)
    content_chunks = [c for c in chunks if len(c.page_content) > 100]
    if len(content_chunks) >= 2:
        for i in range(len(content_chunks) - 1):
            end_of_current = content_chunks[i].page_content[-200:]
            start_of_next = content_chunks[i + 1].page_content[:200]
            overlap_words = set(end_of_current.split()) & set(start_of_next.split())
            assert len(overlap_words) > 0, f"No overlap between content chunks {i} and {i + 1}"


class FakeEmbeddings(Embeddings):
    """Deterministic fake embeddings for testing."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(i)] * 128 for i in range(len(texts))]

    def embed_query(self, text: str) -> list[float]:
        return [0.5] * 128


def test_build_index_creates_faiss_store():
    from app.ingestion import build_index

    chunks = [
        Document(
            page_content=f"Chunk {i} content", metadata={"source": "test.txt", "chunk_index": i}
        )
        for i in range(10)
    ]

    store = build_index(chunks, embeddings=FakeEmbeddings())

    assert store.index.ntotal == 10


def test_save_and_load_index_roundtrip(tmp_path):
    from app.ingestion import build_index, load_index, save_index

    chunks = [
        Document(
            page_content=f"Chunk {i} about testing",
            metadata={"source": "rt.txt", "chunk_index": i},
        )
        for i in range(5)
    ]
    emb = FakeEmbeddings()

    store = build_index(chunks, embeddings=emb)
    save_index(store, tmp_path / "index")

    loaded = load_index(tmp_path / "index", embeddings=emb)
    assert loaded.index.ntotal == 5

    results = loaded.similarity_search("testing", k=2)
    assert len(results) == 2
    assert all("source" in r.metadata for r in results)


def test_ingest_cli_builds_index(tmp_path):
    from scripts.ingest import run_ingestion

    corpus_dir = _create_sample_files(tmp_path, count=5)
    index_dir = tmp_path / "faiss_index"

    stats = run_ingestion(
        corpus_dir=corpus_dir,
        index_dir=index_dir,
        embeddings=FakeEmbeddings(),
    )

    assert index_dir.exists()
    assert stats["doc_count"] == 5
    assert stats["chunk_count"] > 0
    assert stats["index_vectors"] > 0
