#!/bin/bash
set -e

echo "Installing package..."
pip install -e . --quiet

echo "Building FAISS index from knowledge base..."
python scripts/ingest.py

echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
