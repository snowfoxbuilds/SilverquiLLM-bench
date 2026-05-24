# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Create workspace skeleton and author static files

### Implementation
- `benchmarks/sos/workspace/.gitignore` — Git ignore rules for workspace (pycache, pytest_cache, logs, coverage)
- `benchmarks/sos/workspace/AGENTS.md` — Workspace orientation doc with task framing, hard rules, test commands, engine scope
- `benchmarks/sos/workspace/PROJECT_MAP.md` — Directory summary with one line per top-level entry
- `benchmarks/sos/workspace/pytest.ini` — Pytest config with timeout=30 and python_files discovery pattern
- `benchmarks/sos/workspace/engine/__init__.py` — Empty init for engine package discovery
- `benchmarks/sos/workspace/cards/__init__.py` — Empty init for cards package discovery
- `benchmarks/sos/workspace/cards/fdn/__init__.py` — Empty init for fdn package discovery
- `benchmarks/sos/workspace/cards/sos/__init__.py` — Empty init for sos package discovery
- `benchmarks/sos/workspace/tests/__init__.py` — Empty init for tests package discovery
- `benchmarks/sos/workspace/tests/engine/__init__.py` — Empty init for tests/engine package discovery

## Item 2: Move rulebook.md into the workspace

### Implementation
- `benchmarks/sos/workspace/rulebook.md` — Comprehensive MTG rules reference created in workspace (no prior file existed to move)


## Item 3: Move workspace test infrastructure into the workspace

### Tests
- (no dedicated test file — verified via existing workspace engine tests and host-side tests)

### Implementation
- `benchmarks/sos/workspace/tests/__init__.py` — moved from tests/__init__.py via git mv
- `benchmarks/sos/workspace/tests/test_utils.py` — moved from tests/test_utils.py via git mv
- `benchmarks/sos/workspace/tests/conftest.py` — moved from tests/conftest.py via git mv
- `benchmarks/sos/workspace/tests/engine/` — moved entire directory from tests/engine/ via git mv
- `benchmarks/sos/workspace/tests/test_utils.md` — moved from docs/test_utils.md via git mv
- `tests/audited/**/*.py` — updated ~550 files: import path changed to benchmarks.sos.workspace.tests.test_utils
- `tests/test_integration.py` — updated import path to benchmarks.sos.workspace.tests.test_utils
- `silverquillm/evaluator.py` — updated test_utils.py copy path to benchmarks/sos/workspace/tests/test_utils.py
- `silverquillm/workspace.py` — updated test_utils.md staging path to benchmarks/sos/workspace/tests/test_utils.md
- `tests/test_test_utils_doc.py` — updated DOC_PATH to benchmarks/sos/workspace/tests/test_utils.md

## Item 4: Move engine/ to benchmarks/sos/workspace/engine/ and update imports

### Tests
- `tests/test_engine_import_surface.py` — asserts CardImpl, cast_spell, cast_spell_free, resolve_top importable from new path

### Implementation
- `benchmarks/sos/workspace/engine/` — engine package moved here from repo root via git mv
- `benchmarks/sos/workspace/engine/casting.py` — added resolve_top() function
- `silverquillm/workspace.py` — updated engine_dir and _stage_engine_tests paths to new location
- `tests/test_engine_import_surface.py` — new test file for import surface verification
- `tests/__init__.py` — recreated (needed for pytest discovery)
- `tests/test_scaffold.py` — updated paths to reflect engine's new location
- `tests/test_workspace.py` — updated engine_dir fixture to new path
- `tests/test_workspace_engine_tests.py` — updated fake repo structure for graceful-missing test
- `tests/test_event_type_migration.py` — updated regex patterns to match new import paths
- `cards/**/*.py` — ~270 files updated from engine.* to benchmarks.sos.workspace.engine.*
- `tests/audited/**/*.py` — ~530 files updated from engine.* to benchmarks.sos.workspace.engine.*
- `benchmarks/sos/workspace/tests/**/*.py` — ~26 files updated from engine.* to benchmarks.sos.workspace.engine.*

Item 1.4 (revision): Fix remaining stale engine references
Tests
tests/test_engine_import_surface.py — verifies engine import surface and no stale references
Implementation
cards/fdn/fdn_97/card_impl.py — updated bare engine import to full benchmarks path
silverquillm/cli.py — updated two _REPO_ROOT / "engine" path references to new location
silverquillm/replay/executor.py — reworded comments to avoid false-positive "from engine" grep matches
benchmarks/sos/workspace/tests/engine/test_game_state.py — reworded docstring to avoid false-positive grep match

## Item 5: Move cards/ to benchmarks/sos/workspace/cards/ and normalize SOS stubs

### Implementation
- `benchmarks/sos/workspace/cards/` — entire cards directory moved here from repo root via git mv
- `benchmarks/sos/workspace/cards/fdn/__init__.py` — recreated for package discovery (placeholder was removed before move)
- `benchmarks/sos/workspace/cards/**/*.py` — ~115 internal files updated from cards.* to benchmarks.sos.workspace.cards.*
- `benchmarks/sos/workspace/engine/basic_lands.py` — updated cards.registry import to new path
- `benchmarks/sos/workspace/tests/engine/test_lazy_targets.py` — updated cards.fdn imports to new path
- `benchmarks/sos/workspace/tests/engine/test_cast_spell_free.py` — updated cards.fdn imports to new path
- `silverquillm/workspace.py` — updated cards_dir from _REPO_ROOT/"cards" to new workspace path
- `silverquillm/cli.py` — updated cards_dir references to new workspace path
- `silverquillm/card_spec.py` — updated cards.registry import to new path
- `benchmarks/sos/fetch_data.py` — updated cards.scryfall import to new path
- `scripts/generate_audited_stubs.py` — updated cards.registry string references to new path
- `tests/audited/fdn/conftest.py` — updated _FDN_CARDS_DIR path and cards.registry import
- `tests/audited/sos/conftest.py` — updated importlib.import_module call and cards.registry import
- `tests/test_audited_infrastructure.py` — updated sys.modules string keys and cards.registry imports
- `tests/test_card_filter.py` — updated source cards/sos path reference
- `tests/test_card_spec.py` — updated cards.registry import
- `tests/test_cli_cards_filter.py` — updated cards/sos path references
- `tests/test_cli_docker.py` — updated cards path reference
- `tests/test_event_type_migration.py` — updated cards/fdn path reference
- `tests/test_integration.py` — updated cards.fdn imports
- `tests/test_scaffold.py` — updated cards package path and import references
- `tests/test_soa_mystical_archives.py` — updated cards.registry and patch target paths
- `tests/test_sos_regenerated_artifacts.py` — updated cards/sos path reference
- `tests/test_sos_restructure.py` — updated CARDS_SOS path to new location
- `tests/test_sos_stubs.py` — updated all cards module references to new path

## Item 6: Author FDN Reference Tests

### Implementation
- `benchmarks/sos/workspace/cards/fdn/fdn_13/tests.py` — Fleeting Flight tests: replacement effect (combat damage prevention), +1/+1 counter, flying grant
- `benchmarks/sos/workspace/cards/fdn/fdn_15/tests.py` — Hare Apparent tests: targeted ETB token creation based on board-state counting
- `benchmarks/sos/workspace/cards/fdn/fdn_200/tests.py` — Goblin Surprise tests: modal spell with pump mode and token mode
- `benchmarks/sos/workspace/cards/fdn/fdn_205/tests.py` — Seismic Rupture tests: sweeper dealing damage to non-flying creatures
- `benchmarks/sos/workspace/cards/fdn/fdn_242/tests.py` — Lathril tests: menace keyword and combat damage trigger creating tokens
- `benchmarks/sos/workspace/pytest.ini` — added --import-mode=importlib for tests.py module name collision avoidance
- `tests/test_tier_naming.py` — updated cards.registry import
