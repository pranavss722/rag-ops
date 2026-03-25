#!/bin/bash
set -e

echo "Installing package..."
pip install -e . --quiet

echo "Fetching Wikipedia articles (hardcoded files already in repo)..."
python scripts/generate_football_corpus.py --wiki-only

echo "Building FAISS index..."
python scripts/ingest.py

echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
