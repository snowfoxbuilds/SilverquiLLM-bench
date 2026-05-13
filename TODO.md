# TODO

## Phase 8: Fix PR #11 Regressions & Harden Pipeline

Scope: Fix all regressions introduced by the Phase 7 harness refactor (PR #11), including workspace contamination, broken output streaming, false-positive violation detection, and empty postmortem logs. Add structural safeguards (preflight isolation check, signal handling) to prevent this class of bug from recurring. Clean up remaining backlog tech debt.

These are all bugs and regressions discovered during post-merge Pipeline Validation Runs on 2026-05-12. Every item was root-caused by reading the PR #11 codebase at commit `e6f0b47`. See [KNOWN-ISSUES.md](http://known-issues.md/) (Issues #10–#15) and the conversation log for full analysis.

Reference files in current codebase:

- `silverquillm/adapters/opencode.py` — `configure_opencode()` with wrong `repo_root`, `run()` streaming logic
- `silverquillm/strategies.py` — `BlindStrategy`/`ImplTestStrategy` with `ThreadPoolExecutor`, `CardRunResult` missing `agent_output`
- `silverquillm/agent_session.py` — `_is_allowed_path()` missing `.pytest_cache`, `_get_postmortem_path()` using `card_name` instead of `card_dir_name`, `_generate_agent_thoughts()` same issue
- `silverquillm/cli.py` — regression postmortem path uses `card_name`, no signal handler for graceful interrupt
- `silverquillm/preflight.py` — `_check_card_specs_dir()` uses flat glob but cards are in subdirectories
- `silverquillm/adapters/base.py` — `run_with_retries()` already has timeout+kill support (use this instead of ThreadPoolExecutor)
---

- [x] **Fix ****`repo_root`**** contamination in ****`OpenCodeAdapter`**
  Detail: `OpenCodeAdapter.configure_opencode()` in `silverquillm/adapters/opencode.py` sets `"repo_root": str(_REPO_ROOT)` which points to the actual repo root (`/repos/SilverquiLLM-bench/`). This tells the agent (opencode) that its file navigation boundary is the entire repo. The agent can read all existing card implementations in `cards/`, all tests in `tests/`, all engine source in `engine/`, and all harness code in `silverquillm/`. This is a **critical contamination hole** — benchmark results are meaningless when the agent can see reference implementations.

  Additionally, `.workspace/` is a hidden directory (starts with `.`), so globs from the repo root skip it — the agent can't even find its own workspace files (`card_spec.json`, `template.py`, etc.) through the repo root's glob.

  **Fix:** Change one line:

  ```python
# BEFORE:
"repo_root": str(_REPO_ROOT),
# AFTER:
"repo_root": str(workspace),
  ```

  This confines the agent's entire file navigation world to `.workspace/`, which `setup_workspace()` already populates with the curated set of files (card_spec, template, engine_[api.md](http://api.md/), base_classes, foundations, engine).

  Also add explicit deny paths to the permissions block as defense-in-depth:

  ```python
"permissions": {
    "allow_read": [str(workspace)],
    "allow_write": [str(workspace)],
    "deny_read": [str(_REPO_ROOT / "cards"), str(_REPO_ROOT / "tests"),
                   str(_REPO_ROOT / "silverquillm"), str(_REPO_ROOT / "benchmarks")],
},
  ```

  The module-level `_REPO_ROOT` constant in `opencode.py` should remain — it's still needed for the deny paths. But it must NEVER be passed as `repo_root` in the agent config.

  Files to change:

  - `silverquillm/adapters/opencode.py` — `configure_opencode()` method
  Testability: Unit test with a mock: call `configure_opencode(workspace)` and assert `config["repo_root"] == str(workspace)`. Assert `_REPO_ROOT` does NOT appear in the returned config's `repo_root` field.

- [x] **Fix ****`.pytest_cache`**** and other tool-cache false contamination**
  Detail: `_is_allowed_path()` in `silverquillm/agent_session.py` only allows `__pycache__` in its directory check. When the agent runs pytest during implementation, `.pytest_cache/v/cache/nodeids` is modified. The contamination checker flags this as a violation, and `run_card()` overwrites the result to `CardRunStatus.no_output` — even though the implementation is correct. This was the direct cause of `tested=no_output` in validation runs.

  **Fix:**

  1. Add a `_IGNORED_DIRS` frozenset near the existing `_IGNORED_SUFFIXES`:
  ```python
_IGNORED_DIRS: frozenset[str] = frozenset({
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".eggs",
    ".hypothesis",
    ".nox",
})
  ```

  1. In `_is_allowed_path()`, replace `if "__pycache__" in path.parts: return True` with `if _IGNORED_DIRS.intersection(path.parts): return True`
  2. In `_snapshot_mtimes()`, prune ignored dirs from `os.walk()` so they're never even scanned:
  ```python
dirs[:] = [
    d for d in dirs
    if (Path(dirpath) / d).resolve() != git_dir
    and d not in _IGNORED_DIRS
]
  ```

  Files to change:

  - `silverquillm/agent_session.py` — `_IGNORED_DIRS` constant, `_is_allowed_path()`, `_snapshot_mtimes()`
  Testability: Unit test: create a `.pytest_cache/v/cache/nodeids` file, run `_check_violations()` → no violation. Unit test: create a file in `tests/` → violation detected (not affected by the fix).

- [x] **Fix preflight ****`_check_card_specs_dir()`**** flat glob**
  Detail: `_check_card_specs_dir()` in `silverquillm/preflight.py` uses `path.glob("*.json")` to find card spec files. But card specs are in subdirectories: `cards/1/card_spec.json`, `cards/2/card_spec.json`, etc. The flat glob finds nothing, causing preflight to fail with "card_specs_dir contains no card spec files".

  **Fix:** Change the glob pattern:

  ```python
# BEFORE:
specs = list(path.glob("*.json"))
# AFTER:
specs = list(path.glob("*/card_spec.json"))
  ```

  Files to change:

  - `silverquillm/preflight.py` — `_check_card_specs_dir()` function
  Testability: Unit test: create `tmp/1/card_spec.json` and `tmp/2/card_spec.json` → `_check_card_specs_dir(tmp)` passes. Unit test: empty dir → fails with clear error.

- [x] **Standardize all per-card paths on ****`card_dir_name`**
  Detail: The harness uses two different identifiers for per-card subdirectories under `<run_dir>/cards/`:

  - `card_dir_name` (collector number, e.g. `"42"`) — used by `save_card_result()` and `save_card_result_v2()` in `cli.py`
  - `card_name` (display name, e.g. `"Ajani's Response"`) — used by `_get_postmortem_path()` and `_generate_agent_thoughts()` in `agent_session.py`
  This creates TWO separate directories for the same card. The run summary then counts both, reporting `Cards run: 2` when only 1 card was run. Post-eval also can't correlate the postmortem with the result because they're in different directories.

  **Fix:**

  1. Add a `card_id: str` field to the `AgentSession` dataclass (default `""`). This stores the `card_dir_name` value and is used for ALL path construction.
  2. In `cli.py`, pass `card_dir_name` when constructing `AgentSession`:
  ```python
session = AgentSession(
    config=cfg, card_spec=spec, card_dir=card_dir,
    card_id=str(card_dir_name),  # NEW
    run_engine_dir=run_engine_dir, run_dir=run_dir,
)
  ```

  1. In `agent_session.py`, update `run_card()` to use `self.card_id` instead of `self.card_name` in:
    - All `_get_postmortem_path(self.run_dir, ...)` calls (~4 occurrences)
    - `_generate_agent_thoughts(self.run_dir, ...)`
    - `append_raw_log(raw_log_path, ...)` — use `card_id` for consistency in path, but `card_name` is fine in the JSON content
  2. In `harvest_results()`, use `self.card_id` instead of `self.card_name` for the postmortem path.
  3. In `cli.py`, fix the regression postmortem path:
  ```python
# BEFORE:
pm_path = run_dir / "cards" / card_name / "postmortem.jsonl"
# AFTER:
pm_path = run_dir / "cards" / str(card_dir_name) / "postmortem.jsonl"
  ```

  `card_name` (display name) is still fine for log messages, markdown headings, and JSON field values — just not filesystem paths.

  Files to change:

  - `silverquillm/agent_session.py` — add `card_id` field, update all path-construction code
  - `silverquillm/cli.py` — pass `card_dir_name` as `card_id`, fix regression postmortem path
  Testability: Run a single card → exactly ONE subdirectory under `cards/`. Run summary reports `Cards run: 1`. Postmortem, agent_thoughts, result.json all in the same directory.

- [x] **Wire agent output through strategy → ****`CardRunResult`**** → postmortem**
  Detail: Both `BlindStrategy` and `ImplTestStrategy` call `adapter.run(prompt, workspace)` which returns the agent's full output (thinking, tool calls, responses). But the strategies **discard this return value**. `run_card()` in `AgentSession` then logs a placeholder to the postmortem: `prompt="(strategy-level)"`, `response=f"status={result.status.value}"`. This means `agent_thoughts.md` (which reads from the postmortem) is nearly empty.

  **Fix:**

  1. Add `agent_output: str = ""` and `prompt_used: str = ""` fields to `CardRunResult` dataclass in `silverquillm/strategies.py`.
  2. In both strategy `run_card()` methods, capture the adapter's return value and pass it through all return paths:
  ```python
output = adapter.run(prompt, workspace)  # capture
# ...
return CardRunResult(
    status=CardRunStatus.completed,
    agent_output=output,     # pass through
    prompt_used=prompt,      # pass through
    files_written=[impl_path],
    runtime_ms=elapsed_ms,
)
  ```

  For timeout paths, set `agent_output=""` (adapter was killed).

  1. In `run_card()` in `agent_session.py`, use `result.agent_output` and `result.prompt_used` for the postmortem:
  ```python
_append_postmortem(
    postmortem_path=postmortem_path,
    prompt=result.prompt_used or "(strategy-level)",
    response=result.agent_output or f"status={result.status.value}",
    tokens=_estimate_tokens(result.agent_output) if result.agent_output else None,
    timing_ms=elapsed * 1000,
    status="success" if result.status == CardRunStatus.completed else result.status.value,
)
  ```

  1. Do the same for the raw log `append_raw_log()` call.
  Files to change:

  - `silverquillm/strategies.py` — add fields to `CardRunResult`, capture output in both strategies
  - `silverquillm/agent_session.py` — use `result.agent_output`/`result.prompt_used` in postmortem and raw log
  Testability: Run mock adapter that returns "test output" → `postmortem.jsonl` contains "test output" in the response field. `agent_thoughts.md` has rich content (not just a status string).

- [ ] **Replace ****`ThreadPoolExecutor`**** with direct adapter call in strategies**
  Detail: Both `BlindStrategy` and `ImplTestStrategy` wrap the adapter call in `ThreadPoolExecutor.submit()`, which moves the adapter's `run()` method to a worker thread. The adapter streams output via `sys.stderr.write()` in `OpenCodeAdapter.run()`, but this streaming is effectively swallowed when running in a worker thread context. This caused all model thinking, tool calls, and ANSI-colored output to disappear after PR #11.

  The `ThreadPoolExecutor` was added for hard-timeout + kill support, but `base.py` already has `run_with_retries()` which does the same thing via `signal.SIGALRM` (main thread) or threading fallback (non-main thread), plus calls `adapter.kill()` on timeout.

  **Fix:** In both strategies, replace:

  ```python
pool = ThreadPoolExecutor(max_workers=1)
future = pool.submit(adapter.run, prompt, workspace)
try:
    future.result(timeout=timeout)
except (TimeoutError, FuturesTimeoutError, subprocess.TimeoutExpired):
    if hasattr(adapter, "kill"): adapter.kill()
    pool.shutdown(wait=False, cancel_futures=True)
    ...
  ```

  With:

  ```python
try:
    output = adapter.run_with_retries(prompt, workspace, timeout=timeout, retries=0)
except TimeoutError:
    if hasattr(adapter, "kill"): adapter.kill()
    ...
except subprocess.TimeoutExpired:
    if hasattr(adapter, "kill"): adapter.kill()
    ...
  ```

  Remove the `ThreadPoolExecutor` and `FuturesTimeoutError` imports if no longer used.

  **This item depends on the previous item** ("Wire agent output") because `output` must be captured from the return value.

  Files to change:

  - `silverquillm/strategies.py` — replace `ThreadPoolExecutor` with direct call in both strategies, remove unused imports
  Testability: Run a card → model thinking and tool calls are visible in stderr in real time. Timeout still works: mock adapter that blocks → times out → `adapter.kill()` called.

  ⚠️ **Testing guidance (**[**TESTING-CONVENTIONS.md**](http://testing-conventions.md/)** compliance):** All timeout tests must use `threading.Event.wait()` adapters, patch `os.getpgid`/`os.killpg`, and set explicit mock PIDs.

- [x] **Remove stale ****`iterations/`**** directory creation**
  Detail: The old multi-round `run_test_informed()` flow created `iterations/` subdirectories in results. The Phase 7 refactor moved to single-prompt `ImplTestStrategy` but didn't clean up all references. Result directories still contain a stale `iterations/` folder.

  **Fix:**

  1. Search all Python files for `iterations` directory creation: `grep -rn "iterations" silverquillm/ --include="*.py"`
  2. Remove or update any code that creates `iterations/` subdirectories, copies files into `iterations/N/` structure, or references `iterations/` in path construction.
  3. Check `silverquillm/prompts.py` — if `impl_test_mode_prompt()` mentions "iterations" or "rounds" in its instructions to the agent, update to reflect the single-prompt model. The agent self-manages its own internal iteration.
  4. Check `silverquillm/results.py` — `save_card_result()` and `save_card_result_v2()` may be writing iteration-structured output.
  5. Check `silverquillm/run_utils.py` — `_session_results_to_dicts()` may reference iteration fields.
  Files to change:

  - Any file creating `iterations/` directories (find via grep)
  - `silverquillm/prompts.py` — update prompt language if needed
  - `silverquillm/results.py` — remove iteration-structured output if present
  Testability: Run mock adapter in impl_test mode → result directory is flat: `card_impl.py`, `tests.py`, `result.json`, `postmortem.jsonl`, `agent_thoughts.md`, `engine_diff.patch`. No `iterations/` subdirectory.

- [x] **Add signal handler for graceful interrupt cleanup in CLI**
  Detail: When the benchmark is interrupted (Ctrl+C or SIGTERM), the opencode subprocess can continue running as an orphan because it runs in its own process group (`start_new_session=True`). While `teardown()` now calls `kill()`, the signal handler ensures the active adapter is killed immediately on interrupt — before Python's default `KeyboardInterrupt` propagation, which may be blocked in I/O.

  **Fix:**

  1. Add `_active_session: AgentSession | None = None` at module level in `silverquillm/cli.py`.
  2. Define `_interrupt_handler(signum, frame)` that calls `_active_session._adapter.kill()` (with try/except) then raises `KeyboardInterrupt`.
  3. Register the handler at the start of `run()` command: `signal.signal(signal.SIGINT, _interrupt_handler)` and `signal.signal(signal.SIGTERM, _interrupt_handler)`.
  4. In the card loop, set `_active_session = session` before `run_card()` and clear it in the `finally` block.
  5. Add `except KeyboardInterrupt: click.echo("Interrupted..."); break` to exit the card loop cleanly but still run post-loop summary/aggregation.
  6. Restore original signal handlers after the card loop.
  Files to change:

  - `silverquillm/cli.py` — signal handler, `_active_session` tracking, `KeyboardInterrupt` handling in card loop
  Testability: Start a benchmark run → Ctrl+C → verify no orphan opencode processes (`ps aux | grep opencode`). Verify run summary still prints (partial results). Verify `.workspace/` is cleaned up.

- [ ] **Add preflight workspace isolation check**
  Detail: The `repo_root` contamination bug (item 1) was a one-liner that went undetected for the entire PR #11 development cycle. A structural safeguard is needed to catch any future mechanism by which the agent escapes the workspace — not just `repo_root` misconfiguration, but also environment variables, symlinks, or other adapter config fields.

  **Fix:** Add a deterministic canary-based check to `silverquillm/preflight.py`:

  1. Create a canary file at `_REPO_ROOT / ".canary_preflight"` with a random UUID
  2. Create a minimal workspace via `setup_workspace()` (or just `mkdir` + `git init`)
  3. Launch the adapter with a simple prompt: `"Print the exact contents of the file at <canary_path>"`
  4. Check the adapter's output — if the UUID appears, the agent escaped the workspace → fail preflight
  5. Delete the canary file in a `finally` block
  This is fully deterministic (just string matching on the UUID), fast (one short adapter call), and catches the entire class of workspace escape bugs.

  Wire it into `preflight_check()` as an optional check (skip with `--skip-isolation-check` flag, since it requires a working adapter and makes an LLM call).

  Files to change:

  - `silverquillm/preflight.py` — add `_check_workspace_isolation()` function
  - `silverquillm/cli.py` — add `--skip-isolation-check` flag, pass to `preflight_check()`
  Testability: Unit test with mock adapter that returns the canary UUID → preflight fails. Mock adapter that returns unrelated text → preflight passes.

- [ ] **Fix ****`test_timeout_enforcement.py`**** (PR #11 agent-killer tests)**
  Detail: The tests in `tests/test_timeout_enforcement.py` from PR #11 have critical problems that must be fixed:

  **Problem 1 — ****`TestOpenCodeAdapterKill.test_kill_terminates_active_process`**** kills the container:**

  - `mock_proc = MagicMock()` → `mock_proc.pid` is auto-MagicMock → `int(MagicMock()) == 1`
  - `os.getpgid(1)` returns process group of PID 1 (init)
  - `os.killpg(1, SIGTERM)` sends SIGTERM to the entire container → all agents die
  - Fix: set `mock_proc.pid = 99999` explicitly and patch `os.getpgid` + `os.killpg`
  **Problem 2 — ****`_SleepForeverAdapter`**** uses ****`while True: time.sleep(0.1)`****:**

  - If the timeout code under test is broken, these tests hang forever
  - Fix: replace with `threading.Event.wait(timeout=60)` pattern
  **Problem 3 — ****`_SlowConcreteAdapter`**** uses ****`time.sleep(9999)`****:**

  - Same hang risk
  - Fix: use `threading.Event.wait()` or mock `time.sleep`
  Apply all 7 rules from [TESTING-CONVENTIONS.md](http://testing-conventions.md/) to this file. Every `os.getpgid`, `os.killpg`, `signal.signal`, `signal.alarm` call must be patched.

  Files to change:

  - `tests/test_timeout_enforcement.py` — rewrite all adapter mocks and kill tests per conventions
  Testability: `pytest tests/test_timeout_enforcement.py -v` completes in under 30 seconds. No real signals sent. No process groups killed.

- [ ] **Add ****`run_summary.json`**** top-level aggregation**
  Detail: Currently, results are scattered across per-card directories with no top-level summary. We designed a 4-tier schema earlier:

  **Tier 1 — Run metadata:** `model`, `strategy`, `timestamp`, `card_count`, `timeout_seconds`, `harness_version` (git SHA)

  **Tier 2 — Aggregate scores:** `pass_rate`, `avg_score`, `median_score`, `cards_completed`, `cards_timed_out`, `cards_violated`, `total_runtime_ms`

  **Tier 3 — Per-card summary array:** `card_id`, `card_name`, `status`, `score`, `tests_passed`, `tests_total`, `runtime_ms`, `violation`

  **Tier 4 — Comparison hooks:** `previous_run_id` (optional), `delta_pass_rate`, `regressions[]`, `improvements[]`

  Emit `run_summary.json` at the run directory root after all cards complete. Include partial results if interrupted (signal handler writes what's available).

  Files to change:

  - `silverquillm/cli.py` — generate and write `run_summary.json` after card loop
  - `silverquillm/results.py` — add `generate_run_summary()` function
  Testability: Run 2 cards → `run_summary.json` exists at run root, `card_count == 2`, `pass_rate` matches per-card results. Interrupt mid-run → partial summary still written.

- [ ] **Simplify or remove ****`rules_skill.py`**
  Detail: `rules_skill.py` is a 26KB file that is over-engineered now that rules are a greppable file. Either strip it down to a simple grep helper or remove it entirely. A `test_rules_skill.py` also exists and would need updating.

  Files to change:

  - `silverquillm/rules_skill.py` — simplify or delete
  - `tests/test_rules_skill.py` — update or delete
  Testability: If simplified: grep-based tests pass. If removed: no import errors, `test_package_rename.py` updated.

- [ ] **Fix PROJECT_**[**MAP.md**](http://map.md/)** ASCII art alignment**
  Detail: Architecture diagram in `PROJECT_MAP.md` has misaligned box characters after PR #5 edits. Cosmetic cleanup pass needed.

  Files to change:

  - `PROJECT_MAP.md` — realign ASCII art boxes
  Testability: Visual inspection.

- [ ] **Fix ****`get_targets()`**** snapshot-at-call-time issue**
  Detail: Filter closures in `get_targets()` snapshot legal targets when called, not when evaluated. Currently mitigated by `on_resolve()` re-checking legality, but could produce incorrect behavior if target validation is re-checked mid-stack (e.g. for "fizzle" checks).

  **Fix:** Defer filter evaluation to the point where targets are actually chosen. Make filters lazy — accept `game` state at evaluation time rather than capture time.

  Files to change:

  - Card implementations that define target filters — update to use lazy evaluation
  - `engine/casting.py` — pass `game` to filter at evaluation time
  Testability: Unit test: add a spell to the stack that modifies legal targets → second spell's target filter should see updated state.

- [ ] **Refactor ****`chosen_targets`**** off card instance**
  Detail: `chosen_targets` is stored as mutable state directly on the `CardImpl` object (`card.chosen_targets = chosen_targets` in `casting.py`, 83 hits across codebase). If card copying or cloning enters scope, targets from the original leak to the copy. The targets should live on the `StackObject` (which already has a `targets` field) and be accessed through the stack, not the card.

  **Fix:** Remove `card.chosen_targets` assignment in `cast_spell()`. Update `on_resolve` callbacks and card implementations to read targets from the `StackObject.targets` field instead of `self.chosen_targets`.

  Files to change:

  - `engine/casting.py` — remove `card.chosen_targets` assignment
  - Card implementations (83 files) that read `self.chosen_targets` — update to accept targets as parameter or read from stack
  Testability: Grep for `chosen_targets` on card instances → 0 hits outside `StackObject`. Existing card tests still pass.
