#!/bin/bash
set -e

echo "Installing package..."
pip install -e . --quiet

echo "Generating 100-doc corpus..."
python scripts/generate_corpus.py --num-docs 100 --seed 42

echo "Building FAISS index..."
python scripts/ingest.py

echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
