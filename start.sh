#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/backend"

echo "=== Yarn Color Map ==="
echo ""

# Run scraper (skips stores already in cache unless --fresh is passed)
if [[ "$1" == "--fresh" ]]; then
    echo "Clearing cache..."
    rm -f yarn_cache.json
fi

echo "Running scraper..."
python3 scrape.py

echo ""
echo "Starting server at http://localhost:8000"
python3 main.py
