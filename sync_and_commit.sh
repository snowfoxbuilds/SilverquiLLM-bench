#!/bin/bash
# sync_and_commit.sh
#
# Syncs Notion spec pages to the repo and commits if anything changed.
#
# Usage:
#   export NOTION_TOKEN=ntn_...
#   ./sync_and_commit.sh <PROJECT_ROOT_ID> [OUTPUT_DIR]

set -euo pipefail

PROJECT_ID="${1:?Usage: sync_and_commit.sh <PROJECT_ROOT_ID> [OUTPUT_DIR]}"
OUTPUT_DIR="${2:-.}"

cd "$OUTPUT_DIR"

python3 sync_notion_specs.py --project-root-id "$PROJECT_ID" --output-dir .

if git diff --quiet docs/ AGENTS.md 2>/dev/null; then
    echo "No changes."
else
    git add docs/ AGENTS.md
    git commit -m "docs: sync specs from Notion $(date +%Y-%m-%d)"
    git push
    echo "Pushed."
fi
