# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Wire up workspace reference material correctly

### Tests
- `tests/test_workspace_reference_material.py` — Validates rulebook, rules_overview, hard errors on missing sources, prompt text, and module constants

### Implementation
- `silverquillm/workspace.py` — Changed _RULEBOOK_SRC to comprehensive_rules.txt, added _RULES_OVERVIEW_SRC, reduced _REFERENCE_DOCS to only test_utils.md, removed stub fallback (hard error for all sources), updated _PROMPT_TEXT
- `docs/specs/WORKSPACE-CONTRACT.md` — Added rules_overview.md, removed engine_api.md and base_classes.py from workspace layout

## Item 2: --cards-aware status / summary / postmortem plumbing

### Tests
- `tests/test_cli_cards_filter.py` — Validates card_filter in _write_card_statuses, _harvest_results, _evaluate_results, _generate_run_summary with collector_number normalization

### Implementation
- `silverquillm/cli.py` — Added card_filter param to _harvest_results/_write_card_statuses/_evaluate_results/_generate_run_summary, filter compares against spec collector_number with str(int(x)) normalization for numeric values
- `silverquillm/evaluator.py` — Added CardResult, EngineResult, FullEvalResult dataclasses and evaluate() function


## Item 4: Complete event-type strings→classes migration

### Implementation
- `docs/specs/CARD-INTERFACE.md` — Rewrote Replacement Effects example to use typed event classes and game.replacement_manager.register() API

## Item 5: Add engine-extension permission line to the agent prompt

### Implementation
- `silverquillm/workspace.py` — Appended engine-extension permission sentence to `_PROMPT_TEXT` constant

## Item 6: Add fast-tier (1 Hz) command-line telemetry

### Implementation
- `silverquillm/telemetry.py` — New module with FastTelemetry class: 1 Hz poll loop tailing progress.jsonl/system.log and stat-checking card/engine mtimes, writing to per-channel files
- `silverquillm/runner.py` — Integrated FastTelemetry into ContainerLifecycle via optional run_dir parameter; starts on container launch, stops on exit

## Item 7: Tabbed log viewer (live + archived modes)

### Implementation
- `silverquillm/logs_viewer.py` — New module: LogsViewer class with alt-screen, raw-mode, tab-per-channel TUI; stream_plain non-TTY fallback
- `silverquillm/cli.py` — Added `logs` subcommand with --run, --live, --archived options and run directory discovery

## Item 8: Propagate card names into slow-cadence artifacts

### Implementation
- `silverquillm/card_names.py` — New module: build_card_name_map and resolve_card_names_in_line for card ID→name resolution
- `silverquillm/cli.py` — Added card_name to status.json entries, result.json, and progress.jsonl enrichment during harvest
- `silverquillm/runner.py` — Added card_name_map param to ContainerLifecycle; resolves names at terminal print time
- `tests/test_cli_cards_filter.py` — Updated status.json assertions to match new dict format with card_name field
