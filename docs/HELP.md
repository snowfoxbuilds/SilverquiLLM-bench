# venv

python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Testing repo

pytest --ignore=tests/audited/sos/
pytest --ignore=tests/audited/

# Docker
docker build -t silverquillm-qwen-pi-blind:latest docker/qwen-pi-blind/

# Smoke
silverquillm smoke --image silverquillm-qwen-pi-blind:latest

# Test inside docker
docker run --rm -it --network=host   -v /tmp/test-workspace:/workspace   -v /tmp/test-output:/output   --entrypoint /bin/bash   silverquillm-qwen-pi-blind:latest
node /app/entrypoint.mjs 2>&1

# Validation
silverquillm run \
  --image silverquillm-qwen-pi-blind:latest \
  --timeout 600 

## Upload results
git add -f benchmarks/sos/results/gemma4_2026-05-12T01-59/


