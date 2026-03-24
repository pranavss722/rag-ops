"""Tests for the synthetic corpus generator."""

import json
import sys
from pathlib import Path

import pytest


@pytest.fixture
def corpus_dir(tmp_path):
    """Run generate_corpus into a temp directory and return the path."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from generate_corpus import generate_corpus

    generate_corpus(output_dir=tmp_path / "corpus", num_docs=100, seed=42)
    return tmp_path / "corpus"


def test_generate_corpus_creates_files(corpus_dir):
    txt_files = list(corpus_dir.glob("*.txt"))
    assert len(txt_files) == 100, f"Expected 100 files, got {len(txt_files)}"
    for f in txt_files:
        content = f.read_text(encoding="utf-8")
        assert len(content.strip()) > 0, f"{f.name} is empty"


def test_generate_corpus_is_deterministic(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from generate_corpus import generate_corpus

    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    generate_corpus(output_dir=dir_a, num_docs=10, seed=42)
    generate_corpus(output_dir=dir_b, num_docs=10, seed=42)

    for f in sorted(dir_a.glob("*.txt")):
        content_a = f.read_text(encoding="utf-8")
        content_b = (dir_b / f.name).read_text(encoding="utf-8")
        assert content_a == content_b, f"{f.name} differs between runs"


def test_corpus_doc_word_count(corpus_dir):
    for f in list(corpus_dir.glob("*.txt"))[:10]:
        words = f.read_text(encoding="utf-8").split()
        assert 200 <= len(words) <= 800, f"{f.name} has {len(words)} words, expected 200-800"


def test_manifest_jsonl_created(corpus_dir):
    manifest = corpus_dir / "manifest.jsonl"
    assert manifest.exists(), "manifest.jsonl not created"

    entries = [
        json.loads(line) for line in manifest.read_text(encoding="utf-8").strip().splitlines()
    ]
    assert len(entries) == 100

    required_keys = {"doc_id", "title", "category", "word_count", "generated_at"}
    for entry in entries:
        assert required_keys.issubset(entry.keys()), f"Missing keys in {entry}"
