# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Remove --cards-dir and --engine-dir CLI flags

### Tests
- `tests/test_workspace.py` — Verifies stage_workspace signature has no cards_dir/engine_dir params
- `tests/test_cli_docker.py` — Verifies _harvest_results signature has no cards_dir param; CLI flags removed

### Implementation
- `silverquillm/cli.py` — Removed cards_dir param from _harvest_results and _write_card_statuses; use _REPO_ROOT internally
- `silverquillm/workspace.py` — Removed cards_dir/engine_dir params from stage_workspace; signature is now (output_dir, *, card_filter)

## Item 2: Add --cards filter to silverquillm run

### Tests
- `tests/test_workspace.py` — Verifies stage_workspace signature and workspace structure
- `tests/test_cli_docker.py` — Verifies CLI flags, docker args, harvest, and smoke tests

### Implementation
- `silverquillm/cli.py` — Added --cards Click option, parsed into card_filter list with zero-pad normalization, passed to stage_workspace
- `silverquillm/workspace.py` — Implemented card_filter in _stage_cards (SOS filtering by collector_number with numeric normalization), dynamic prompt text, click.echo of filter

## Item 3: Write run_manifest.json during workspace staging

### Implementation
- `silverquillm/cli.py` — Write run_manifest.json (timeout_seconds + deadline_utc) after staging, copy it in _harvest_results; moved json import to module level

## Item 4: Update Docker entrypoints

### Implementation
- `docker/homelab-pi-blind/entrypoint.mjs` — Removed engine_work copy, added system.log logging, agent_stdout.log capture, SIGTERM handler
- `docker/local-pi-blind/entrypoint.mjs` — Removed engine_work copy, added system.log logging, agent_stdout.log capture, SIGTERM handler

