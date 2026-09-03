# venv

python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Testing repo

# Repository validation (platform/tooling tests) — from repo root, same as CI:
python -m pytest tests/ -q

# Workspace validation (engine_tests + colocated FDN card tests) — from the workspace dir:
cd benchmarks/sos/workspace
pytest

# Audited SOS/FDN grading is not a direct pytest target — it runs through the
# evaluator/validation harness. See the Validation and Test Validation sections
# below (silverquillm run / silverquillm rescore).

# Docker
docker build -t silverquillm-local-pi-blind:latest docker/local-pi-blind/

docker build -t silverquillm-cc-opus-48-bare-xhigh-planned:latest docker/cc-opus-48-bare-xhigh-planned/

docker build -t silverquillm-cc-fable-5-bare-xhigh-planned:latest docker/cc-fable-5-bare-xhigh-planned/

# Smoke
silverquillm smoke --image silverquillm-local-pi-blind:latest
silverquillm smoke --image silverquillm-copilot-gpt-4.1:latest
silverquillm smoke --image silverquillm-cc-sonnet-single:latest

# Validation
silverquillm run --image silverquillm-cc-opus-48-plan-tdd-v2-xhigh:latest --cards 1,4,13,57,97,120,201,226,245,257  --timeout 360000

silverquillm run --image silverquillm-cc-opus-48-bare-xhigh-planned:latest --cards 1,4,13,57,97,120,201,226,245,257  --timeout 360000;\
silverquillm run --image silverquillm-cc-fable-5-bare-xhigh-planned:latest --cards 1,4,13,57,97,120,201,226,245,257  --timeout 360000

silverquillm run \
  --image silverquillm-local-pi-blind:latest \
  --timeout 600 

# Resume

silverquillm resume sos-copilot-claude-opus-4.6-2026-05-25T22-52 --timeout 360000

# Difficult cards
--cards 1,4,13,57,97,120,201,226,245,257

# TUI

silverquillm logs --run sos-copilot-gpt-4.1-2026-05-24T06-51 

# Workspace setup
rm -rf /tmp/test-staging && mkdir /tmp/test-staging 

python -c "
from pathlib import Path
from silverquillm.workspace import stage_workspace
ws, out = stage_workspace(Path('/tmp/test-staging'), card_filter=['1','7','13'])
print('workspace:', ws)
print('output:', out)
"

# Test inside docker
docker run --rm -it --network=host \
  -v /tmp/test-staging/workspace:/workspace \
  -v /tmp/test-staging/output:/output \
  --entrypoint /bin/bash \
  silverquillm-local-pi-blind:latest

node /app/entrypoint.mjs 2>&1


# Upload results
git add -f docker/local-pi-blind/results/sos-2026-05-12T01-59/

rm -rf docker/*/validated_results/*/workspace_final/.git

# Aggregate results
python3 scripts/validated_results_to_csv.py   --output aggregated_results.csv

# Rerun results
silverquillm rescore docker/copilot-sonnet-single/results/sos-copilot-sonnet-single-2026-05-26T19-33

ls -d docker/*/validated_results/*/ \
  | xargs -P 12 -I {} sh -c \
    'silverquillm rescore "{}" >"{}/rescore.log" 2>&1 || echo "FAILED: {}"'


# Test Validation
# Full harvest → benchmarks/sos/analysis/harvested_results.jsonl
python scripts/harvest_validated_results.py --bench sos
# Cross-impl breadth summary → benchmarks/sos/analysis/harvested_summary.json
python scripts/harvest_validated_results.py --bench sos --summary


# Private results repo (#39 §3 / #63) — a local clone of the private results repo
export SILVERQUILLM_RESULTS_REPO=~/src/silverquillm-results   # or pass --results-repo everywhere
# Lay out an empty clone: schema AGENTS.md + results/ + runs.jsonl
# (refuses any non-empty target except a bare .git; a failed init rolls itself back)
silverquillm results-init "$SILVERQUILLM_RESULTS_REPO"
# Backfill the legacy corpus (plan first, then write; re-runs skip byte-identical
# records and abort on any conflicting existing record — nothing is overwritten)
python scripts/migrate_validated_results.py --dry-run
python scripts/migrate_validated_results.py
# Regenerate the derived index after any change under results/
python scripts/rebuild_results_index.py
# Harvest from the results repo instead of the docker/ walk (identical rows)
python scripts/harvest_validated_results.py --bench sos --results-repo "$SILVERQUILLM_RESULTS_REPO"
# Then commit in the results repo clone — the writer never runs git