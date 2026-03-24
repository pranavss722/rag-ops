"""Document ingestion module — chunking, embedding, and indexing."""

import re
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


def load_documents(corpus_dir: Path) -> list[Document]:
    """Load all .txt files from a directory as LangChain Documents."""
    corpus_dir = Path(corpus_dir)
    docs = []
    for filepath in sorted(corpus_dir.glob("*.txt")):
        content = filepath.read_text(encoding="utf-8")
        docs.append(
            Document(
                page_content=content,
                metadata={"source": filepath.name},
            )
        )
    return docs


def _detect_section_header(full_text: str, chunk_text: str) -> str | None:
    """Find the nearest markdown heading above the chunk start position."""
    chunk_start = full_text.find(chunk_text[:80])
    if chunk_start == -1:
        return None
    preceding = full_text[:chunk_start]
    headers = re.findall(r"^##?\s+(.+)$", preceding, re.MULTILINE)
    return headers[-1] if headers else None


def chunk_documents(
    docs: list[Document],
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[Document]:
    """Split documents into chunks with metadata preservation."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    all_chunks: list[Document] = []
    for doc in docs:
        splits = splitter.split_text(doc.page_content)
        for i, chunk_text in enumerate(splits):
            section = _detect_section_header(doc.page_content, chunk_text)
            all_chunks.append(
                Document(
                    page_content=chunk_text,
                    metadata={
                        **doc.metadata,
                        "chunk_index": i,
                        "section_header": section,
                    },
                )
            )

    return all_chunks


def build_index(chunks: list[Document], embeddings: Embeddings) -> FAISS:
    """Build a FAISS vector store from document chunks."""
    return FAISS.from_documents(chunks, embeddings)


def save_index(store: FAISS, path: Path) -> None:
    """Persist a FAISS index to disk."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    store.save_local(str(path))


def load_index(path: Path, embeddings: Embeddings) -> FAISS:
    """Load a FAISS index from disk."""
    return FAISS.load_local(str(path), embeddings, allow_dangerous_deserialization=True)
