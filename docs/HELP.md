# venv

# Testing repo

pytest --ignore=tests/audited/sos/
pytest --ignore=tests/audited/

# Validation
benchmark validate data/replays/fdn/ --verbose
benchmark validate data/replays/fdn/ --report results/validation_report.json
benchmark validate data/replays/fdn/ --verbose --stop-on-divergence

## Upload results
git add -f benchmarks/sos/results/gemma4_2026-05-12T01-59/