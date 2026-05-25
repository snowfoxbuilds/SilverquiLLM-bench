# TODO

Reference: post-05-24 run analysis on `docker/copilot-gpt-5.4/results/sos-copilot-gpt-5.4-2026-05-24T08-05`. Goal: a stable benchmark substrate for models and harnesses — staging correctness and live-mode observability come first; agent/harness prompt iteration is on-roadmap but deferred.

## Phase 16: Workspace as Pre-Built Directory (post 05-24 run)

Scope: Restructure the workspace from per-file staging assembled by `silverquillm/workspace.py` into a real pre-built directory at `benchmarks/sos/workspace/` in the bench repo, copied wholesale at stage time. Driven by ADR-007. The 05-24 run exposed assembly fragility (missing `AGENTS.md`/`PROJECT_MAP.md`, no pytest config, no `.git/`, no FDN test exemplars); rather than patching per-file staging item-by-item, we move the workspace into a real inspectable, dev-testable directory.

Reference: `silverquillm/workspace.py`, ADR-007, [WORKSPACE-CONTRACT.md](http://workspace-contract.md/), [BENCHMARK-RUNNER.md](http://benchmark-runner.md/), [CONTEXT.md](http://context.md/) (Workspace, SOS Card Stub, FDN Reference Tests terms).

---

Sequencing note: Items 1.1–1.7 below replace what was previously a single mega-item. The split exists because structural moves of `engine/` and `cards/` touch many import sites and must be completed atomically within their commit — a half-finished move leaves the codebase un-importable. Items are ordered so all purely additive work lands first, then the two dangerous moves, then dependent items.

- [ ] **1.1 Create workspace skeleton and author static files**
  Detail: Purely additive commit. Create the empty directory structure and author the static workspace files. Nothing is moved yet; existing tests still pass.

  - Create directories: `benchmarks/sos/workspace/{engine,cards/fdn,cards/sos,tests/engine}/`. Add `.gitkeep` or initial `__init__.py` files where needed for Python package discovery.
  - Author `benchmarks/sos/workspace/AGENTS.md` — orientation doc only: task framing ("implement SOS cards in `cards/sos/{card_id}/card_impl.py`"), hard rules (card location, staged-test integrity, additive-only engine modifications — cross-reference [WORKSPACE-CONTRACT.md](http://workspace-contract.md/) Decisions), canonical test commands (`pytest` from workspace root discovers FDN reference tests + `tests/engine/` via the workspace `pytest.ini` `python_files` config), engine extension scope (may add files/methods and modify existing function bodies; may NOT rename, move, or delete anything existing in `engine/` — no refactoring), git availability, and a pointer to `PROJECT_MAP.md` for the directory layout. Does NOT duplicate the directory map.
  - Author `benchmarks/sos/workspace/PROJECT_MAP.md` — directory summary only: one line per top-level file/directory. No helper API reference, no task framing, no commands — strictly a navigation lookup.
  - Author `benchmarks/sos/workspace/pytest.ini` setting `timeout = 30` and `python_files = test_*.py tests.py` so colocated FDN reference tests (`cards/fdn/{cn}/tests.py`) are discovered alongside `tests/engine/test_*.py`.
  - Author `benchmarks/sos/workspace/.gitignore` covering `__pycache__/`, `*.pyc`, `.pytest_cache/`, `*.log`, `*.jsonl`, `.coverage`, `htmlcov/`, `decisions.md.tmp`.
  Files: `benchmarks/sos/workspace/{AGENTS.md,PROJECT_MAP.md,pytest.ini,.gitignore}` (new), `benchmarks/sos/workspace/{engine,cards/fdn,cards/sos,tests/engine}/` (new empty dirs).

  Testability: `ls benchmarks/sos/workspace/{AGENTS.md,PROJECT_MAP.md,pytest.ini,.gitignore}` succeeds. Existing `pytest` from repo root still passes (nothing moved yet).

- [ ] **1.2 Move ****`rulebook.txt`**** into the workspace**
  Detail: Move the rulebook from its current location (root `rulebook.txt` or `docs/rulebook.txt` — locate via `find . -name 'rulebook.txt' -not -path './.git/*'`) to `benchmarks/sos/workspace/rulebook.txt` via `git mv` so history is preserved. Update any documentation references in other markdown files to the new path (`grep -rln 'rulebook.txt' --include='*.md' .`).

  Files: current `rulebook.txt` location (moved), any markdown files referencing it.

  Testability: `ls benchmarks/sos/workspace/rulebook.txt` succeeds; the old path no longer exists; `git log --follow benchmarks/sos/workspace/rulebook.txt` shows continuous history.

- [ ] **1.3 Move workspace test infrastructure into the workspace**
  Detail: `git mv` the workspace-local test files from top-level `tests/` into `benchmarks/sos/workspace/tests/`, and move `docs/test_utils.md` alongside its `.py` counterpart. Bodies stay identical — only locations change:

  - `tests/test_utils.py` → `benchmarks/sos/workspace/tests/test_utils.py`
  - `tests/__init__.py` → `benchmarks/sos/workspace/tests/__init__.py`
  - `tests/conftest.py` → `benchmarks/sos/workspace/tests/conftest.py`
  - `tests/engine/` → `benchmarks/sos/workspace/tests/engine/` (replaces the empty dir from Item 1.1)
  - `docs/test_utils.md` → `benchmarks/sos/workspace/tests/test_utils.md`
  - Top-level `pytest.ini` → delete (the workspace-local `pytest.ini` from Item 1.1 becomes canonical). If host-side `silverquillm/` tests need separate pytest config, move it into a `[tool.pytest.ini_options]` block in repo-root `pyproject.toml` in the same commit.
  Sweep imports of the moved test helpers (`grep -rln '^from tests\.\|^import tests\.\|from tests import' --include='*.py' .`) and update each to the new path. Note: `tests/engine/` test files themselves don't need import updates yet because `engine/` hasn't moved — those updates happen as part of Item 1.4.

  Files: paths listed above (moved), top-level `pytest.ini` (deleted), `pyproject.toml` (optional host-side pytest config), any callers of `tests.test_utils` (import updates).

  Testability: `pytest benchmarks/sos/workspace/tests/engine/` runs (tests may still pass against the old top-level `engine/` since `engine/` hasn't moved yet — that is Item 1.4). After Phase 16 fully lands, `cd benchmarks/sos/workspace && pytest tests/engine/` passes.

- [ ] **1.4 Move ****`engine/`**** to ****`benchmarks/sos/workspace/engine/`**** and update all imports (LARGE STRUCTURAL MOVE)**
  Detail: Single commit that relocates the engine package and rewrites every import site. **This commit will produce intermediate broken-test states during execution. Do not abort partway through. Do not commit a partial move.** The done-state criteria below are non-negotiable; if you cannot reach them, abandon the working tree and start the item fresh.

  - Step A: `git mv engine benchmarks/sos/workspace/engine` (preserve history). If the directory-level `git mv` fails for any reason, fall back to per-file `git mv` of each file under `engine/`.
  - Step B: Enumerate all import sites: `grep -rln '^from engine\b\|^import engine\b' --include='*.py' . | sort -u`. Expected locations: every file in `silverquillm/` that touches game logic, every file in `tests/audited/`, possibly some `cards/` files that import engine internals.
  - Step C: Update each matched file: `from engine.X` → `from benchmarks.sos.workspace.engine.X`, `import engine` → `import benchmarks.sos.workspace.engine as engine` (preserve the local `engine` alias where existing code relies on it). Use a scripted sed pass for the common cases and hand-edit any complex ones.
  - Step D: Iterate on remaining `ImportError`s until done-state holds.
  Done-state verification (all three must hold before committing):

  1. `grep -rln '^from engine\b\|^import engine\b' --include='*.py' .` returns zero matches outside `benchmarks/sos/workspace/engine/` itself.
  2. `pytest` from repo root exits 0 (full host-side suite, including audited tests).
  3. `python -c "from benchmarks.sos.workspace.engine.card import CardImpl; from benchmarks.sos.workspace.engine.casting import cast_spell, cast_spell_free, resolve_top; print('ok')"` succeeds.
  Files: `engine/**` (moved), `silverquillm/**` (import updates), `tests/audited/**` (import updates), any `cards/**` files that import engine internals (import updates).

  Testability: Per the three done-state checks. Add a focused unit test `tests/test_engine_import_surface.py` (host-side) asserting each of `CardImpl`, `cast_spell`, `cast_spell_free`, `resolve_top` is importable from `benchmarks.sos.workspace.engine.*`.

- [ ] **1.5 Move ****`cards/`**** to ****`benchmarks/sos/workspace/cards/`**** and normalize SOS stubs (LARGE STRUCTURAL MOVE)**
  Detail: Single commit that relocates the cards directory, rewrites all `cards.*` import sites, and brings SOS stub files to the canonical class form. **Same atomicity rule as Item 1.4: do not commit a partial move. Do not abort partway through.**

  - Step A: `git mv cards benchmarks/sos/workspace/cards` (preserve history).
  - Step B: Enumerate import sites: `grep -rln '^from cards\b\|^import cards\b' --include='*.py' . | sort -u`. Update each from `from cards.X` → `from benchmarks.sos.workspace.cards.X` and `import cards` → `import benchmarks.sos.workspace.cards as cards`.
  - Step C: Normalize SOS card stubs to the canonical form `class CardName(CardImpl):\n    """TODO: ..."""\n    pass`. Files currently docstring-only that need a class declaration added (post-move paths): `benchmarks/sos/workspace/cards/sos/spg_158/card_impl.py`, `.../sos_195/card_impl.py`, `.../sos_217/card_impl.py`, `.../sos_218/card_impl.py`. The `CardName` class name follows the same PascalCase-from-card-name convention used in already-normalized stubs (`sos_5`, `sos_55`).
  - Step D: Iterate on remaining errors until done-state holds.
  Done-state verification (all three must hold before committing):

  1. `grep -rln '^from cards\b\|^import cards\b' --include='*.py' .` returns zero matches outside `benchmarks/sos/workspace/cards/`.
  2. `pytest` from repo root exits 0.
  3. Every SOS card module is a valid class definition: `python -c "import ast, glob; [ast.parse(open(f).read()) for f in glob.glob('benchmarks/sos/workspace/cards/sos/*/card_impl.py')]; print('ok')"` succeeds, and a parametrized check confirms each module contains at least one class inheriting from `CardImpl`.
  Files: `cards/**` (moved), `silverquillm/**` (imports), `tests/audited/**` (imports), the four normalized SOS stub files.

  Testability: Per done-state checks. Add a parametrized unit test that imports every `benchmarks.sos.workspace.cards.sos.*.card_impl` module dynamically and asserts each defines a class inheriting from `CardImpl`.

- [ ] **1.6 Author FDN Reference Tests at ****`benchmarks/sos/workspace/cards/fdn/{cn}/tests.py`**
  Detail: Author 3–5 illustrative FDN test files covering representative mechanics: Converge mana-color tracking, modal spell, targeted ETB, multi-blocker combat, replacement effect. Choose the specific FDN collector numbers based on which already-implemented FDN cards cleanly exercise each mechanic (inspect `benchmarks/sos/workspace/cards/fdn/{cn}/card_impl.py` to confirm). Use `benchmarks/sos/workspace/tests/test_utils.py` helpers and follow the patterns established in `benchmarks/sos/workspace/tests/engine/`. These tests are illustrative learning material the agent will see; they may overlap freely with audited FDN tests at `benchmarks/sos/data/tests/audited/fdn/` (no contamination concern — the agent is not graded on either FDN suite).

  Files: `benchmarks/sos/workspace/cards/fdn/{cn}/tests.py` for 3–5 chosen FDN cards (new).

  Testability: `cd benchmarks/sos/workspace && pytest cards/fdn/` discovers and passes the new tests. Each test imports from `benchmarks.sos.workspace.engine` and `benchmarks.sos.workspace.cards.fdn.{cn}.card_impl` (paths now correct after Items 1.4 and 1.5).

- [ ] **1.7 Move audited tests to ****`benchmarks/sos/data/tests/audited/`**** and update evaluator paths**
  Detail: Move host-side audited tests from top-level `tests/audited/` to `benchmarks/sos/data/tests/audited/{fdn,sos}/`. This consolidates the bench-side input layout under `benchmarks/sos/data/` ("everything the bench owns but the agent never sees"). Also update `silverquillm/evaluator.py` so audited-test paths and `test_utils.py` resolution both point at the new locations:

  - Audited tests path: `_REPO_ROOT / "benchmarks/sos/data/tests/audited"` (or `_BENCHMARK_SET_ROOT / "data/tests/audited"` if Item 2 has already landed — either form is fine).
  - `test_utils.py` source for eval tempdir copies: `_REPO_ROOT / "benchmarks/sos/workspace/tests/test_utils.py"` (now alongside the workspace).
  - Update any import statements in the moved audited test files from old `engine`/`cards` paths to `benchmarks.sos.workspace.engine`/`benchmarks.sos.workspace.cards` (consequence of Items 1.4 and 1.5; these may already be updated as part of those items' import sweeps).
  Files: `tests/audited/**` → `benchmarks/sos/data/tests/audited/**` (moved), `silverquillm/evaluator.py` (path updates).

  Testability: `ls tests/audited/` fails (path no longer exists); `ls benchmarks/sos/data/tests/audited/{fdn,sos}/` succeeds. A small end-to-end evaluation run (`silverquillm run --cards 1` then `silverquillm evaluate <run>`) produces a `run_summary.json` matching a pre-restructure baseline.

- [ ] **Rewrite ****`stage_workspace()`**** to the four-step form**
  Detail: Replace per-file assembly in `silverquillm/workspace.py` with `cp -r` + per-run writes + `git init`:

  ```python
_BENCHMARK_SET_NAME = "sos"  # module-level; promote to CLI flag when adding a second target set
_BENCHMARK_SET_ROOT = _REPO_ROOT / "benchmarks" / _BENCHMARK_SET_NAME

def stage_workspace(tmp_run_dir: Path, prompt_text: str, run_manifest: dict) -> Path:
    src = _BENCHMARK_SET_ROOT / "workspace"
    dst = tmp_run_dir / "workspace"
    shutil.copytree(src, dst)
    (dst / "prompt.md").write_text(prompt_text, encoding="utf-8")
    (dst / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=dst, check=True)
    subprocess.run(["git", "add", "-A"], cwd=dst, check=True)
    subprocess.run(["git", "-c", "user.name=runner", "-c", "user.email=runner@silverquillm", "commit", "-q", "-m", "initial workspace"], cwd=dst, check=True)
    return dst
  ```

  Drop `_REFERENCE_DOCS`, `_RULEBOOK_SRC`, `_RULES_OVERVIEW_SRC`, and every per-file copy helper. Assert `_BENCHMARK_SET_ROOT / "workspace"` exists and is non-empty before `copytree` (cheap pre-flight; raises `FileNotFoundError` with a clear message if the canonical directory is missing). The new function is roughly 15 lines plus imports.

  Files: `silverquillm/workspace.py`.

  Testability: `silverquillm run --cards 1` produces a staged directory matching `benchmarks/sos/workspace/` byte-for-byte plus `prompt.md` and `run_manifest.json`. `git -C <staged_dir> log --oneline` shows exactly one commit. Add `tests/integration/test_stage_workspace.py` asserting the staged tree equals the source tree plus the two per-run files.

- [ ] **Delete deprecated per-file staging code**
  Detail: After Item 2 (the `stage_workspace()` rewrite) lands, remove the now-unused per-file staging helpers and constants from `silverquillm/workspace.py`. These were used by the old per-file workspace assembly and are dead code once `stage_workspace()` is the four-step `cp -r` form. Specifically delete:

  - `_REFERENCE_DOCS` constant
  - `_RULEBOOK_SRC`, `_RULES_OVERVIEW_SRC` constants
  - Any helpers that built per-file copies (`_stage_reference_docs`, `_copy_with_replacement`, etc.)
  Audited-test relocation and `evaluator.py` path updates are handled in Item 1.7, not here.

  Files: `silverquillm/workspace.py`.

  Testability: `grep -rn '_REFERENCE_DOCS\|_RULEBOOK_SRC\|_RULES_OVERVIEW_SRC\|_stage_reference_docs' silverquillm/` returns zero matches. `silverquillm run --cards 1` still produces a valid staged workspace (the deleted code was unreachable after Item 2).

- [ ] **Add CI-time workspace structure test**
  Detail: Author `tests/test_workspace_structure.py` (host-side, not staged into the workspace). Asserts `benchmarks/sos/workspace/` contains the expected top-level entries: `engine/`, `cards/fdn/`, `cards/sos/`, `tests/`, `AGENTS.md`, `PROJECT_MAP.md`, `rulebook.txt`, `pytest.ini`, `.gitignore`. Replaces the old per-file hard-error enumeration that used to live in `stage_workspace()` — drift is now caught at PR-review time rather than at run time.

  Files: `tests/test_workspace_structure.py` (new).

  Testability: Run the test against current `benchmarks/sos/workspace/` — passes. Temporarily rename or delete a top-level entry locally; the test fails with a message naming the missing entry. CI catches it before merge.

## Phase 17: TUI Telemetry Fixes (live-mode observability)

Scope: Make `silverquillm logs --live` actually populate every tab during a run. Currently only `[system]` populates live; the others are unwritten, written-only-on-exit, or written by an unwired callback. Sequencing matters: items 1–3 produce the missing files, then item 4 hides any channels that remain structurally empty.

Reference: `silverquillm/telemetry.py`, `silverquillm/runner.py`, `silverquillm/cli.py`, `silverquillm/logs_viewer.py`, `docs/specs/RUN-ARTIFACTS-AND-TELEMETRY.md`.

---

- [ ] **Write ****`docker_stdout.log`**** and ****`docker_stderr.log`**** directly to ****`run_dir`**** during the run**
  Detail: `silverquillm/runner.py:_drain_pipe` currently writes to `output/docker_stdout.tmp` and `output/docker_stderr.tmp` during the run; `ContainerLifecycle.run()` copies them to `output/docker_stdout.log` / `docker_stderr.log` only after the container exits; `cli.py:_harvest_results` then copies those into `run_dir`. As a result, the `[stdout]` and `[stderr]` tabs are empty until the run finishes.

  Change `_drain_pipe` to open `run_dir / "docker_stdout.log"` (and stderr) directly in append mode (line-buffered) and write each line as it arrives. Drop the `.tmp` intermediate. Update `ContainerLifecycle.run()` to no longer perform the post-exit `shutil.copy2` step. Update `_harvest_results` in `cli.py` to skip these two files (they're already in `run_dir`). This intentionally breaks the `.tmp` + `.log` copy convention for these channels; document the carve-out in `KEY_DECISIONS.md`.

  Thread-safety: append-mode writes from a single `_drain_pipe` thread per stream are safe. Use `open(..., "a", buffering=1, encoding="utf-8", errors="replace")` so lines flush immediately.

  Files: `silverquillm/runner.py` (`_drain_pipe`, `ContainerLifecycle.run`, `ContainerLifecycle.__init__` — receive `run_dir` if not already), `silverquillm/cli.py` (`_harvest_results`), `KEY_DECISIONS.md`.

  Testability: Start a run; while it's executing, `tail -f docker/<image>/results/<run>/docker_stdout.log` shows lines arriving in real time. `silverquillm logs --run <run> --live` shows the `[stdout]` tab populating live. After the run, the file is well-formed and complete (no missing lines vs. previous behavior).

- [ ] **Wire ****`snapshot_callback`**** in ****`cli.py`**** so ****`snapshot_telemetry.jsonl`**** populates**
  Detail: `ContainerLifecycle.__init__` accepts a `snapshot_callback` parameter (called every 60s by the existing snapshot loop — `_SNAPSHOT_INTERVAL = 60`), but `silverquillm/cli.py:run()` instantiates `ContainerLifecycle(...)` without passing one. As a result, `snapshot_telemetry.jsonl` is never written and the `[snapshot]` tab is permanently empty.

  In `cli.py`, define a callback that:

  1. Walks the staged workspace (`cards/`, `engine/`, `tests/`).
  2. Computes the delta payload per `docs/specs/RUN-ARTIFACTS-AND-TELEMETRY.md` (changed `card_impl.py` count, changed engine files, completed-like card impls per the existing heuristic, etc.).
  3. Appends one JSON line to `run_dir / "snapshot_telemetry.jsonl"`.
  Pass it as `snapshot_callback=` to `ContainerLifecycle`. If the snapshot logic already exists in a helper, reuse it; otherwise extract a `silverquillm/snapshot.py:snapshot_once(workspace, run_dir, card_name_map)` helper. Snapshot payload stays IDs-only per the SETTLED scope carve-out (no `card_name` in this high-cadence file).

  Files: `silverquillm/cli.py` (`run()` — add callback wiring), optional `silverquillm/snapshot.py` (new helper).

  Testability: Start a 5-minute run; after 60s, `snapshot_telemetry.jsonl` exists with at least one line; after 3 minutes, at least 3 lines. Each line parses as JSON and contains the keys documented in `RUN-ARTIFACTS-AND-TELEMETRY.md`. Live TUI `[snapshot]` tab updates every 60s.

- [ ] **Tee runner ****`click.echo`**** calls into ****`runner.log`**** and ****`runner_errors.log`**
  Detail: The `[runner]` and `[error]` tabs in `logs_viewer.py` map to `run_dir / "runner.log"` and `run_dir / "runner_errors.log"`, but nothing in the codebase writes to these files. Add a small helper in `cli.py`:

  ```python
def _runner_log(run_dir: Path, msg: str, *, err: bool = False) -> None:
    click.echo(msg, err=err)
    target = run_dir / ("runner_errors.log" if err else "runner.log")
    with target.open("a", encoding="utf-8") as f:
        f.write(msg.rstrip("\n") + "\n")
  ```

  Route every existing `click.echo(...)` call in `run()`, `_harvest_results()`, `_evaluate_results()`, `_generate_run_summary()`, and any caught-exception print path through this helper. Pass `run_dir` explicitly (or wrap in a tiny `RunnerContext` so callers don't repeat themselves). Best-effort: if `run_dir` doesn't exist yet (very early in `run()`), skip the file write but still call `click.echo`.

  Files: `silverquillm/cli.py`.

  Testability: After a run, `runner.log` exists in `run_dir` and contains the same lines that were printed to the terminal. Trigger an error path (e.g. invalid `--cards` value); confirm the message appears in `runner_errors.log`. Live TUI `[runner]` tab populates as the run progresses.

- [ ] **Hide structurally-empty channels in live mode with rediscovery polling**
  Detail: `LogsViewer.__init__` currently registers all channels in `CHANNEL_ORDER` when `live=True`, regardless of whether the backing file exists. After Phase 17 items 1–3 the file-existence check becomes meaningful, so any not-yet-written channel files no longer create permanently-empty tabs.

  Change `LogsViewer.__init__` to register only channels whose file currently exists. Add a `_discover_new_channels()` method called every 1s (mirroring the existing `_reload_all` cadence) that scans `run_dir` for new channel files and registers them dynamically. New tabs appear in `CHANNEL_ORDER` position with a transient "new" badge (~3s) so the user notices them.

  Files: `silverquillm/logs_viewer.py`.

  Testability: Start a run; immediately open `silverquillm logs --live`. Initially only `[system]` (and any other already-existing files) appear. As `runner.log`, `docker_stdout.log`, `snapshot_telemetry.jsonl` populate, new tabs appear within ~1s. At no point is an empty tab shown.

- [ ] **Emit a bootstrap line on first ****`FastTelemetry._poll_mtimes`**** pass**
  Detail: `FastTelemetry._poll_mtimes` records baseline mtimes on its first poll but emits zero events (the diff logic requires `prev is not None`). On cycle 1 of a run, this leaves `fast_telemetry.jsonl` empty until the agent first edits a card or engine file — making the `[edit]` tab look broken for several minutes during the cycle-1 thrash.

  On the first poll only, emit a synthetic line `{"ts": ..., "event": "polling_started", "watched_paths": <count>, "sample_paths": [<first 3>]}` so the tab shows immediate signal. Subsequent polls behave as today.

  Files: `silverquillm/telemetry.py` (`FastTelemetry._poll_mtimes`).

  Testability: Start a run; within 2 seconds, `fast_telemetry.jsonl` contains the `polling_started` line. Live TUI `[edit]` tab shows it. Edit a workspace card file; the next poll emits the standard mtime-change line.

- [ ] **Drop ****`progress.jsonl`**** channel and entrypoint emission**
  Detail: Per 2026-05-24 grilling, `progress.jsonl` is removed from the design entirely — not enough use to justify the harness/agent protocol surface.

  - Remove `progress` from `CHANNEL_ORDER` in `silverquillm/logs_viewer.py`.
  - Remove the SIGTERM-time `progress.jsonl` write in the Docker entrypoint (`docker/<image>/entrypoint.mjs`).
  - Remove any `progress.jsonl` references in `silverquillm/cli.py` and `silverquillm/runner.py`.
  Files: `silverquillm/logs_viewer.py`, Docker entrypoint script, `silverquillm/cli.py`, `silverquillm/runner.py`.

  Testability: `grep -rn 'progress\.jsonl' silverquillm/ docker/` returns zero matches. `silverquillm logs --run <run>` no longer lists a `[progress]` tab. End-to-end run + `--live` mode shows 7 channels not 8.
