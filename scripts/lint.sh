#!/usr/bin/env bash
# lint.sh — code quality helpers
#
# Usage:
#   ./scripts/lint.sh format   # run black + isort (rewrites files)
#   ./scripts/lint.sh lint     # run pylint (report only, no changes)
#   ./scripts/lint.sh all      # format then lint
#
# Run from the project root. Requires the virtualenv to be active,
# or the tools to be available on PATH.

set -euo pipefail

SOURCES="main.py data/ metrics/ tests/"

format() {
    echo "==> isort"
    python -m isort $SOURCES

    echo "==> black"
    python -m black $SOURCES
}

lint() {
    echo "==> pylint"
    python -m pylint $SOURCES
}

all() {
    format
    lint
}

case "${1:-all}" in
    format) format ;;
    lint)   lint   ;;
    all)    all    ;;
    *)
        echo "Unknown command: $1"
        echo "Usage: $0 [format|lint|all]"
        exit 1
        ;;
esac