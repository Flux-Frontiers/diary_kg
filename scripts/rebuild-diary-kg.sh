#!/usr/bin/env bash
# Rebuild DiaryKG SQLite knowledge graph and LanceDB semantic index.
# Invoked by pre-commit after pytest succeeds.
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "--- DiaryKG rebuild: SQLite ---"
poetry run diarykg-build-sqlite --repo "$REPO_ROOT" --wipe

echo "--- DiaryKG rebuild: LanceDB ---"
poetry run diarykg-build-lancedb --repo "$REPO_ROOT" --wipe

echo "--- DiaryKG rebuild: complete ---"
