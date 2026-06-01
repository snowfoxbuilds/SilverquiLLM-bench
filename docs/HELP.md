# venv

python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# sync specs

python3 sync_notion_specs.py

# Testing repo

pytest --ignore=tests/audited/sos/
pytest --ignore=tests/audited/
pytest tests/audited/fdn tests/engine

# Docker
docker build -t silverquillm-local-pi-blind:latest docker/local-pi-blind/


docker build -t silverquillm-cc-sonnet-single:latest docker/cc-sonnet-single/
docker build -t silverquillm-cc-opus-single:latest docker/cc-opus-single/docker build -t silverquillm-cc-opus-48-single:latest docker/cc-opus-48-single/
docker build -t silverquillm-cc-opus-48-bare:latest docker/cc-opus-48-bare/
docker build -t silverquillm-cc-opus-46-bare-high:latest docker/cc-opus-46-bare-high/

docker build -t silverquillm-cc-opus-48-bare-xhigh:latest docker/cc-opus-48-bare-xhigh/
docker build -t silverquillm-cc-opus-48-single-xhigh:latest docker/cc-opus-48-single-xhigh/
docker build -t silverquillm-cc-opus-48-xhigh-cheap-impl:latest docker/cc-opus-48-xhigh-cheap-impl/
docker build -t silverquillm-cc-opus-48-xhigh-cheap-review:latest docker/cc-opus-48-xhigh-cheap-review/


# Smoke
silverquillm smoke --image silverquillm-local-pi-blind:latest
silverquillm smoke --image silverquillm-copilot-gpt-4.1:latest
silverquillm smoke --image silverquillm-cc-sonnet-single:latest

# Validation
silverquillm run --image silverquillm-local-pi-blind:latest --cards 1,7,13,44,97 --timeout 36000



silverquillm run --image silverquillm-cc-sonnet-single:latest --cards 1,4,13,57,97,120,201,226,245,257  --timeout 360000;\
silverquillm run --image silverquillm-cc-opus-single:latest --cards 1,4,13,57,97,120,201,226,245,257  --timeout 360000;\
silverquillm run --image silverquillm-cc-opus-single:latest --cards 1,4,13,57,97,120,201,226,245,257  --timeout 360000;\

silverquillm run --image silverquillm-cc-opus-48-bare:latest --cards 1,4,13,57,97,120,201,226,245,257  --timeout 360000;\

silverquillm run --image silverquillm-cc-opus-46-bare-high:latest --cards 1,4,13,57,97,120,201,226,245,257  --timeout 360000;\
silverquillm run --image silverquillm-cc-opus-46-bare-high:latest --cards 1,4,13,57,97,120,201,226,245,257  --timeout 360000;\
silverquillm run --image silverquillm-cc-opus-48-single:latest --cards 1,4,13,57,97,120,201,226,245,257  --timeout 360000;\
silverquillm run --image silverquillm-cc-opus-48-single:latest --cards 1,4,13,57,97,120,201,226,245,257  --timeout 360000;\


silverquillm run --image silverquillm-cc-opus-48-bare-xhigh:latest --cards 1,4,13,57,97,120,201,226,245,257  --timeout 360000;\
silverquillm run --image silverquillm-cc-opus-48-single-xhigh:latest --cards 1,4,13,57,97,120,201,226,245,257  --timeout 360000;\
silverquillm run --image silverquillm-cc-opus-48-xhigh-cheap-impl:latest --cards 1,4,13,57,97,120,201,226,245,257  --timeout 360000;\
silverquillm run --image silverquillm-cc-opus-48-xhigh-cheap-review:latest --cards 1,4,13,57,97,120,201,226,245,257  --timeout 360000;\


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