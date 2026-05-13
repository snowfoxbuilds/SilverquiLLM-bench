# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Add --cards filter to silverquillm run

### Tests
- `tests/test_card_filter.py` — Tests for card_filter workspace staging, prompt content, CLI option parsing, and defaults

### Implementation
- `silverquillm/workspace.py` — Added `card_filter` param to `stage_workspace()` and `_stage_cards()`; split prompt into `_PROMPT_ALL`/`_PROMPT_SUBSET`
- `silverquillm/cli.py` — Added `--cards`, `--cards-dir`, `--engine-dir` to `run` and `smoke`; repo-relative defaults via `_REPO_ROOT`; `_generate_run_summary` writes `card_filter` to `run_summary.json`

## Item 2: Implement multi-channel output capture

### Tests
- `tests/test_multichannel_output.py` — Tests for harvest of log files, format_log_lines tagging/coloring/interleaving, and logs CLI command

### Implementation
- `docker/homelab-pi-blind/entrypoint.mjs` — Added timestamped agentStdout()/agentStderr() helpers; stderr interceptor for agent runtime capture; try/catch/finally for guaranteed exit_code
- `docker/local-pi-blind/entrypoint.mjs` — Same multi-channel output changes as homelab variant
- `silverquillm/cli.py` — Updated _harvest_results to copy all .log files; added `logs` command for colorized interleaved log viewing; added format_log_lines() helper

## Item 3: Generate FDN card specs and templates

### Tests
- `tests/audited/fdn/` — 1487 audited FDN tests (pre-existing, all pass)
- `tests/test_card_loader_unified.py` — Card loader tests validating FDN spec loading

### Implementation
- `scripts/generate_fdn_specs.py` — Pre-existing script that fetches Scryfall data and generates cards/fdn/ directory tree (286 subdirs with card_spec.json + card_impl.py)

## Item 4: Migrate FDN card implementations into per-card templates

### Tests
- `tests/test_fdn_card_migration.py` — Migration tests: file counts, CardImpl subclasses, registry population, spot-checks
- `tests/audited/fdn/` — 1487 audited FDN tests (all pass via conftest card_impl injection)
- `tests/cards/` — 25 per-category card test files (all pass, still import from cards.foundations)

### Implementation
- `cards/fdn/*/card_impl.py` (286 files) — Filled per-card templates with implementations; all 286 now set default `name` from card_spec.json
- `cards/fdn/utils.py` — Shared helpers: TapLand, GainLand, make_vanilla, _tap_cost
- `cards/registry.py` — Added register_fdn_cards() with logging.warning on import failures (no longer silent)
