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
benchmark validate data/replays/fdn/ --verbose
benchmark validate data/replays/fdn/ --report results/validation_report.json
benchmark validate data/replays/fdn/ --verbose --stop-on-divergence

## Upload results
git add -f benchmarks/sos/results/gemma4_2026-05-12T01-59/


