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
docker build -t silverquillm-copilot-gpt-4.1:latest docker/copilot-gpt-4.1/
docker build -t silverquillm-copilot-gpt-5.4-mini:latest docker/copilot-gpt-5.4-mini/
docker build -t silverquillm-copilot-gpt-5.4:latest docker/copilot-gpt-5.4/
docker build -t silverquillm-copilot-claude-opus-4.6:latest docker/copilot-claude-opus-4.6/

# Smoke
silverquillm smoke --image silverquillm-local-pi-blind:latest
silverquillm smoke --image silverquillm-copilot-gpt-4.1:latest

# Validation
silverquillm run --image silverquillm-local-pi-blind:latest --cards 1,7,13,44,97 --timeout 36000
silverquillm run --image silverquillm-copilot-gpt-4.1:latest --cards 1,7,13,44,97 --timeout 36000
silverquillm run --image silverquillm-copilot-gpt-5.4-mini:latest --timeout 360000
silverquillm run --image silverquillm-copilot-gpt-5.4:latest --timeout 360000
silverquillm run --image silverquillm-copilot-claude-opus-4.6:latest --timeout 360000

silverquillm run \
  --image silverquillm-local-pi-blind:latest \
  --timeout 600 

# Resume

silverquillm resume sos-copilot-claude-opus-4.6-2026-05-25T22-52 --timeout 360000

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


## Upload results
git add -f docker/local-pi-blind/results/sos-2026-05-12T01-59/


