#!/bin/bash
# Azure App Service startup command:  bash startup.sh
# Builds the sample databases (idempotent) and starts the secured HTTP server.
set -e
cd "$(dirname "$0")"
python seed_db.py
python ingest_docs.py
export HOST=0.0.0.0
export PORT="${PORT:-8000}"
exec python server.py --http
