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
