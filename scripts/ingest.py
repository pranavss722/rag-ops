"""End-to-end ingestion CLI: load → chunk → embed → save FAISS index."""

from pathlib import Path

from langchain_core.embeddings import Embeddings

from app.ingestion import build_index, chunk_documents, load_documents, save_index


def run_ingestion(
    corpus_dir: Path,
    index_dir: Path,
    embeddings: Embeddings,
) -> dict:
    """Run the full ingestion pipeline and return stats."""
    docs = load_documents(corpus_dir)
    print(f"Loaded {len(docs)} documents")

    chunks = chunk_documents(docs)
    print(f"Created {len(chunks)} chunks")

    store = build_index(chunks, embeddings=embeddings)
    save_index(store, index_dir)
    print(f"Saved index with {store.index.ntotal} vectors to {index_dir}")

    return {
        "doc_count": len(docs),
        "chunk_count": len(chunks),
        "index_vectors": store.index.ntotal,
    }


if __name__ == "__main__":
    from dotenv import load_dotenv
    from langchain_openai import OpenAIEmbeddings

    load_dotenv()
    run_ingestion(
        corpus_dir=Path("data/corpus"),
        index_dir=Path("data/faiss_index"),
        embeddings=OpenAIEmbeddings(model="text-embedding-3-small"),
    )
