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

# Smoke
silverquillm smoke --image silverquillm-local-pi-blind:latest

# Test inside docker
docker run --rm -it --network=host   -v /tmp/test-workspace:/workspace   -v /tmp/test-output:/output   --entrypoint /bin/bash   silverquillm-local-pi-blind:latest
node /app/entrypoint.mjs 2>&1

# Validation
silverquillm run --image silverquillm-local-pi-blind:latest --cards 1,7,13,44,97 --timeout 36000

silverquillm run \
  --image silverquillm-local-pi-blind:latest \
  --timeout 600 

## Upload results
git add -f docker/local-pi-blind/results/sos-2026-05-12T01-59/


