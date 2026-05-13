Known issues encountered during benchmark runner development, with fixes applied.

---

## Issue #1: Setup questions validation blocks benchmark runs

`Status:` ✅ Fixed

`Root cause:` The `setup_questions.json` pre-flight quiz parsed free-text LLM responses for keyword matches. Thinking tokens leaked into responses (e.g., `"Thinking: The user is asking..."`) causing keyword matching to fail. Additionally, the quiz-style validation was a spec-vs-implementation mismatch — the [BENCHMARK-RUNNER.md](http://benchmark-runner.md/) spec intended agent-emitted diagnostic questions, not runner-quizzes-agent.

`Symptoms:`

- Q3, Q5, Q7 failed validation
- `RuntimeError: Adapter failed setup-questions validation; aborting run`
- Benchmark couldn't proceed past setup phase
`Fix:` Removed `setup_questions.json` and `silverquillm/setup_questions.py` entirely. Removed the validation block from `setup_workspace()`. Natural failures in the blind phase surface workspace issues without a fragile text-parsing gate.

`Files changed:`

- `setup_questions.json` — deleted
- `silverquillm/setup_questions.py` — deleted
- `silverquillm/agent_session.py` — removed import and validation block
---

## Issue #2: `--thinking` flag removed from opencode adapter

`Status:` ✅ Fixed (by design)

`Root cause:` The `opencode.py` adapter was ported from an earlier inline implementation. The `--thinking` flag was deemed invalid for the `opencode run` CLI and explicitly removed.

`Symptoms:` Agent thinking tokens appeared in stdout text instead of being separated, but this only affected text-evaluated responses (setup questions), not tool-call-based implementation phases.

`Fix:` `--thinking` flag intentionally removed. Thinking tokens in stdout are a non-issue for the implementation phases where the agent uses tool calls to write files.

`Files changed:`

- `silverquillm/adapters/opencode.py` — docstring documents the removal
---

## Issue #3: Postmortem and log files written to wrong directory

`Status:` ✅ Fixed

`Root cause:` `_get_postmortem_path()` used `config.output_dir` (e.g., `benchmarks/sos/results/`) instead of the run-specific directory (e.g., `benchmarks/sos/results/gemma4_2026-05-12/`). Different runs' postmortems would overwrite each other.

`Symptoms:`

- Postmortem files appeared at `benchmarks/sos/results/Plains/postmortem.jsonl` instead of under the run directory
- Cross-run contamination of log files
- Messy results folder
`Fix:` Added `run_dir` field to `AgentSession`. Updated `_get_postmortem_path()`, `_generate_agent_thoughts()`, and `append_raw_log()` to use `run_dir` instead of `config.output_dir`. Updated `cli.py` to pass `run_dir` when constructing sessions.

`Files changed:`

- `silverquillm/agent_session.py` — added `run_dir` field, updated path functions
- `silverquillm/cli.py` — passes `run_dir` to `AgentSession`
---

## Issue #4: Contamination checker flags runner's own log files

`Status:` ✅ Fixed

`Root cause:` `output_dir` was inside `benchmarks/` which is a protected directory. When the runner wrote `postmortem.jsonl` and `raw_agent_log.jsonl` to the output directory, the contamination checker flagged them as violations.

`Symptoms:`

- `Contamination violation: .../benchmarks/sos/results/raw_agent_log.jsonl was created`
- `Contamination violation: .../benchmarks/sos/results/Plains/postmortem.jsonl was created`
`Fix:` Updated `_check_violations()` to accept an `output_dir` parameter and skip files under it. Updated all call sites to pass the output directory.

`Files changed:`

- `silverquillm/agent_session.py` — `_check_violations()` signature and both loops
---

## Issue #5: Agent can't find workspace files (temp dir sandbox doesn't work with opencode)

`Status:` ✅ Fixed

`Root cause:` `setup_workspace()` created a temp directory (`/tmp/bench_agent_XXXX/`) and copied files there. But opencode auto-discovers the repo root via `.git/` and operates from there. The agent always looked for files at `/repos/SilverquiLLM-bench/` and never found `template.py`, `card_spec.json`, `engine_api.md`, or `base_classes.py` in the temp dir.

`Symptoms:`

- `Read /repos/SilverquiLLM-bench/template.py failed — File not found`
- `Glob "**/template.py" 0 matches`
- Agent produced no implementations (status: `no_output` for all cards)
`Attempted fixes that didn't work:`

- Setting `repo_root` in opencode config to workspace — opencode ignores it
- Running `git init` in workspace — opencode still finds the real repo
- Adding `./` prefixes to prompt file paths — agent still uses absolute repo paths
`Fix:` Replaced `tempfile.mkdtemp()` with `_REPO_ROOT / ".workspace"`. The workspace is now inside the repo tree so the agent naturally discovers it. Added `.workspace/` to `.gitignore`. Added stale workspace cleanup at run start. Added `harvest_results()` to copy output files to the run results directory before cleanup.

`Files changed:`

- `silverquillm/agent_session.py` — workspace creation, `harvest_results()` method
- `silverquillm/cli.py` — stale workspace cleanup, calls `harvest_results()`
- `silverquillm/prompts.py` — all prompts reference `.workspace/` paths
- `.gitignore` — added `.workspace/`
---

## Issue #6: `__pycache__` .pyc files trigger false contamination violations

`Status:` ✅ Fixed

`Root cause:` Python auto-generates `.pyc` files in `__pycache__/` directories when importing modules. The agent imports from `engine/`, `cards/`, `tests/` during its run, creating `.pyc` files in protected directories. The contamination checker flagged these as violations.

`Symptoms:`

- Dozens of violations like `Contamination violation: .../tests/cards/__pycache__/test_scryfall.cpython-312-pytest-9.0.3.pyc was created`
- `blind=violation, tested=skipped` — blind implementation discarded despite being valid
- Agent's work thrown away due to false positives
`Fix:` Added `__pycache__` skip in both loops of `_check_violations()`:

```javascript
if "__pycache__" in path.parts:
    continue
```

`Files changed:`

- `silverquillm/agent_session.py` — `_check_violations()` both loops
---

## Issue #7: Collector number collision between base set and mystical archives

`Status:` ✅ Fixed

`Root cause:` The SOS base set (`cards/6/`) and mystical archives (`cards/soa_6/`) both have `"collector_number": "6"` in their `card_spec.json`. The code used `collector_number` as both the filter key and filesystem ID, causing `--cards 6` to match both cards and results to overwrite each other at `cards/6/`.

`Symptoms:`

- `--cards 6` selected 2 cards instead of 1
- Second card's results overwrote first card's results
- Eval only saw 1 card despite 2 being run
- Regressions ran against wrong card
`Fix:` Injected `card_dir_name` (the filesystem directory name, e.g., `"6"` vs `"soa_6"`) into each spec during `load_card_specs()`. Changed `filter_by_collectors()` and the CLI orchestration loop to use `card_dir_name` as the unique ID instead of `collector_number`.

`Files changed:`

- `silverquillm/card_loader.py` — `load_card_specs()` injects `card_dir_name`, `filter_by_collectors()` matches on it
- `silverquillm/cli.py` — uses `card_dir_name` for results directories and card IDs
---

## Issue #8: Eval reports 0/1 instead of actual test counts

`Status:` ✅ Fixed

`Root cause:` Three compounding issues in the evaluator:

1. **Missing engine imports** — `run_tests()` created a temp dir with only `card_impl.py`. Agent tests that import engine modules (`from engine.game import Game`) or test utilities (`from test_utils import create_game`) failed because neither was on `PYTHONPATH`.
2. **`tests.py`**** shadows ****`tests/`**** package** — Agent tests used `from tests.test_utils import ...`. Pytest ran a file called `tests.py`, which Python resolved as the local module instead of the repo's `tests/` package. `ModuleNotFoundError: 'tests' is not a package`.
3. **Agent imports wrong module name** — Prompt said write to `blind_impl.py` / `tested_impl.py` but tests should import from `card_impl`. Agents sometimes wrote `from tested_impl import ...` instead, which didn't exist in the eval temp dir.
All three caused pytest collection errors, reported as `0/1` (1 collection error, 0 tests passed) instead of the real test count.

`Fix:`

- Added `_REPO_ROOT` to `PYTHONPATH` in `run_tests()` for engine imports
- Copied `test_utils.py` to temp dir for flat imports
- Renamed test file to `test_card.py` in temp dir to avoid shadowing `tests/` package
- Copied impl as `card_impl.py`, `blind_impl.py`, AND `tested_impl.py` in temp dir
- Standardized on `card_impl.py` as the single implementation filename throughout prompts and runner
`Files changed:`

- `silverquillm/evaluator.py` — `run_tests()` rewritten
- `silverquillm/prompts.py` — all prompts use `card_impl.py` as output filename
- `silverquillm/agent_session.py` — blind phase looks for `card_impl.py`, template written as both `template.py` and `card_impl.py`
---

## Issue #9: Stale workspace from aborted runs

`Status:` ✅ Fixed

`Root cause:` If a benchmark run was aborted (Ctrl+C, crash, OOM), the `.workspace/` directory persisted with stale files from the previous run. The next run would start with contaminated workspace state.

`Fix:` Added stale workspace cleanup at the start of the `run` command in `cli.py`, before the orchestration loop begins. Per-card cleanup in `AgentSession.cleanup()` handles the normal case between cards.

`Files changed:`

- `silverquillm/cli.py` — stale workspace cleanup block before orchestration loop
---

## Issue #10: Self-eval ignores engine modifications (`engine_diff.patch` not applied)

`Status:` 🔴 Open

`Root cause:` The evaluator's `run_tests()` copies `card_impl.py` and `tests.py` (renamed `test_card.py`) to a temp directory, but does **not** apply engine changes the agent made during its run. Cards that require engine extensions (e.g. new hooks, reordered logic, added player attributes) pass in the agent's workspace but fail in the isolated eval environment.

`Symptoms:`

- `postmortem.jsonl` shows `tests_passing: true` (agent ran tests in workspace, they passed)
- `result.json` self_eval shows failures on the same tests
- Discrepancy is always on tests that exercise engine-modified behavior
`Evidence from gemma4 2026-05-12 run:`

- **Eager Glyphmage (#11, simple tier):** Agent modified `engine/zones.py` to register triggers *before* firing `ENTERS_BATTLEFIELD` (so a card's own ETB trigger can see itself enter). All 5 tests passed locally. Self-eval: 2/5 — the 3 ETB tests fail because the eval uses the original `zones.py` where triggers register *after* the event fires.
- **Ral Zarek (#97, expert tier):** Agent added `turns_to_skip` to `engine/player.py` and skip-turn logic to `engine/turn.py` for the −7 ability. All 6 tests passed locally. Self-eval: 5/6 — `test_skip_turns_execution` fails because the eval engine has no skip-turn support.
`Impact:` Cards that correctly require engine changes are scored as partial failures. In the gemma4 run, fixing this would change the result from 3/5 fully passing to 5/5.

`Suggested fix:` In `run_tests()`, after copying `card_impl.py` and `test_card.py` to the temp dir, also apply the card's `engine_diff.patch` (or copy the modified engine directory from the workspace). The patch file is already captured by the harness — it just isn't used during eval.

`Files to change:`

- `silverquillm/evaluator.py` — `run_tests()` should apply engine patches to the temp dir
---

## Issue #11: `test_utils.md` documents wrong import path

`Status:` 🔴 Open

`Root cause:` The `test_utils.md` reference document (provided to the agent in the workspace) says to import helpers as `from tests.test_utils import create_game, set_board_state, cast_spell`. But the actual workspace layout has `test_utils.py` as a flat file at the `.workspace/` root — there is no `tests/` package. When the agent follows the documented import, the file `tests.py` (which the agent is writing) shadows any potential `tests` package, causing `ModuleNotFoundError: 'tests' is not a package`.

`Symptoms:`

- `ModuleNotFoundError: No module named 'tests.test_utils'; 'tests' is not a package`
- Agent wastes an entire correction iteration just fixing the import line
`Evidence from gemma4 2026-05-12 run:`

- **Ajani's Response (#6):** Wasted iteration 1 of 2 on this import error (fixed in round 2)
- **Ral Zarek (#97):** Wasted iteration 1 of 2 on this import error (fixed in round 2)
- **Plains (#267):** Same error in first tested attempt, fixed on retry
- **Rancorous Archaic (#2):** Also hit the error but self-corrected within the same round
`Related:` Partially overlaps with Issue #8 (which fixed the eval side). Issue #8's fix standardized the eval temp dir but did not update the agent-facing `test_utils.md` documentation.

`Impact:` Wastes one of the agent's limited correction iterations (typically 2 rounds max) on a trivial import fix that is entirely the harness's fault.

`Suggested fix:` Update `.workspace/test_utils.md` to use `from test_utils import create_game, set_board_state, cast_spell` (flat import matching the actual workspace layout).

`Files to change:`

- `tests/test_utils.md` (source) → update import examples to `from test_utils import ...`
- `silverquillm/agent_session.py` — if `test_utils.md` is copied during workspace setup, ensure the updated version is used
---

## Issue #12: Template doesn't import `GameState` (common `NameError` for agents)

`Status:` 🔴 Open

`Root cause:` The `template.py` skeleton provides `from engine.card import *` and `from engine.types import *`, but `GameState` lives in `engine.game_state` and is not re-exported by either module. Nearly every non-trivial card implementation needs `GameState` for type hints in `register_triggers()`, `on_resolve()`, loyalty ability methods, etc. The agent must discover the correct import path by trial and error.

`Symptoms:`

- `NameError: name 'GameState' is not defined` on the first test run
- Agent spends tokens grepping the engine source to find where `GameState` is defined
`Evidence from gemma4 2026-05-12 run:`

- **Plains (#267):** Hit `NameError: name 'GameState' is not defined` in `card_impl.py`, had to add `from engine.game_state import GameState`
- **Ral Zarek (#97):** Same `NameError`, same fix
- **Eager Glyphmage (#11):** Model preemptively imported it after reading engine source (avoided the error but spent tokens finding it)
`Impact:` Low severity (agents recover quickly), but wastes tokens and occasionally a correction iteration. Easily preventable.

`Suggested fix:` Add `from engine.game_state import GameState` to `template.py`, or re-export `GameState` from `engine.types`.

`Files to change:`

- `silverquillm/agent_session.py` — update the template content written to `.workspace/template.py`
- Alternatively: `engine/types.py` — add `from .game_state import GameState` to exports
---

## Issue #13: In-run test verification always reports `tests_passing: false` (iteration loop broken)

`Status:` 🔴 Open

`Root cause:` The harness's in-run test checker (which determines whether the agent's tests pass after each tested-phase round) reports `tests_passing: false` even when the agent's tests are correct. The self-eval — which copies the same `card_impl.py` and `tests.py` to a temp dir with `PYTHONPATH` set to `_REPO_ROOT` — finds all tests passing. The discrepancy likely stems from the in-run checker running tests in `.workspace/` with a different environment (working directory, `PYTHONPATH`, module resolution) than the self-eval temp dir.

`Symptoms:`

- All cards end with `status: max_rounds_exhausted` even though implementations and tests are correct
- `postmortem.jsonl` shows `tests_passing: false` for every tested-phase round
- `result.json` self_eval shows all tests passing (110/110 across 4 cards in the qwen3.6 run)
- Agent never gets positive feedback — the iteration loop is broken
`Evidence from qwen3.6 2026-05-12 run:`

- **Plains (#267, trivial):** 21/21 self-eval, `tests_passing: false` in-run. Model confirmed tests passed when it ran pytest manually.
- **Eager Glyphmage (#11, simple):** 34/34 self-eval, `tests_passing: false` in-run
- **Ajani's Response (#6, medium):** 26/26 self-eval, `tests_passing: false` in-run
- **Rancorous Archaic (#2, complex):** 29/29 self-eval, `tests_passing: false` in-run
- All 4 non-violated cards: 110/110 in self-eval, 0/4 reported as passing during the run
`Distinct from Issue #10:` Issue #10 is about engine patches not being applied in self-eval (causing self-eval failures). Issue #13 is the inverse — self-eval passes fine, but the in-run checker fails. Both are evaluator bugs but with different root causes.

`Impact:` Critical. The iteration loop is completely broken — with `max_test_rounds: 1`, every card is doomed to `max_rounds_exhausted` regardless of code quality. Even with higher `max_test_rounds`, the agent would burn all rounds without ever getting a "tests passed" signal.

`Suggested fix:` Align the in-run test checker's environment with the self-eval environment. Specifically: copy `card_impl.py` and `tests.py` to a temp dir, set `PYTHONPATH` to include `_REPO_ROOT`, rename `tests.py` to `test_card.py` (to avoid shadowing), and run pytest there — exactly as `run_tests()` does in the self-eval path.

`Files to change:`

- `silverquillm/agent_session.py` — the in-run test verification logic needs to mirror `evaluator.py:run_tests()`
---

## Issue #14: `timeout_per_card` not enforced

`Status:` 🔴 Open

`Root cause:` The `config.yaml` specifies `timeout_per_card: 300` (5 minutes), but individual phases and total per-card times far exceed this limit. The timeout mechanism is either unimplemented or not wired into the adapter's subprocess execution.

`Symptoms:`

- Individual phases run for 15–28 minutes with no interruption
- Total per-card wall time reaches 35+ minutes (7× over limit)
- Benchmark runs take hours instead of the expected ~25 minutes (5 cards × 300s)
`Evidence from qwen3.6 2026-05-12 run (timeout_per_card: 300):`

- **Plains (#267, trivial):** tested phase = 1,700s (28 min), total = 1,848s
- **Ral Zarek (#97, expert):** tested phase = 1,346s (22 min), total = 2,128s
- **Eager Glyphmage (#11, simple):** tested phase = 930s (15 min), total = 1,332s
- **Rancorous Archaic (#2, complex):** tested phase = 790s (13 min), total = 1,152s
- **Ajani's Response (#6, medium):** tested phase = 626s (10 min), total = 867s
- Every single card exceeded the 300s limit, most by 3–7×
`Impact:` Benchmark runs are unpredictably long. A 5-card run that should take ~25 minutes took ~2 hours. For larger card sets, this makes runs impractical.

`Suggested fix:` Implement a timeout wrapper around the adapter's `run()` call. After `timeout_per_card` seconds, kill the subprocess and record `status: timeout`. The opencode adapter should use `subprocess.Popen` with a timer or `asyncio.wait_for`.

`Files to change:`

- `silverquillm/adapters/opencode.py` — add subprocess timeout
- `silverquillm/agent_session.py` — enforce timeout at the session level as a fallback
---

## Issue #15: `harvest_results()` doesn't capture files for violation-status cards

`Status:` 🔴 Open

`Root cause:` When a card receives a contamination violation status, `harvest_results()` either skips file copying or runs before the agent finishes writing files. The result directory ends up with `engine_diff.patch` and `result.json` but is missing `blind_impl.py`, `tested_impl.py`, `card_impl.py`, and `tests.py`.

`Symptoms:`

- Self-eval errors: "Missing blind_[impl.py](http://impl.py/)", "Missing [tests.py](http://tests.py/)", "Missing tested_[impl.py](http://impl.py/)"
- Self-eval reports 0/0 tests (can't evaluate at all)
- The agent's implementation and tests are completely lost — can't be scored or inspected
- Only `engine_diff.patch` survives (if the agent modified engine files)
`Evidence from qwen3.6 2026-05-12 run:`

- **Ral Zarek (#97, expert):** Status `violation`. Card 97 result directory contains only `engine_diff.patch` (188KB — model made extensive engine changes for turn-skipping), `iterations/`, and `result.json`. No implementation or test files. Self-eval: 0/0 with missing-file errors. The model likely wrote a working implementation but it was never captured.
`Impact:` Violated cards are completely unevaluable. Even if the violation was a false positive (e.g. from `__pycache__` files or overly broad contamination checks), the agent's work is lost. For Ral Zarek, the model spent 2,128s of compute and produced a 188KB engine patch — all unrecoverable.

`Suggested fix:` Always copy `card_impl.py`, `tests.py`, `blind_impl.py`, and `tested_impl.py` from `.workspace/` to the results directory, regardless of violation status. Violations should be recorded in `result.json` but should not prevent file harvesting. This allows post-hoc re-evaluation and debugging.

`Files to change:`

- `silverquillm/agent_session.py` — `harvest_results()` should run unconditionally, not skip on violation
- `silverquillm/cli.py` — ensure harvest is called before violation status is set, or decouple harvest from status
---

## Issue #16: `repo_root` contamination — agent can read entire repo

`Status:` 🔴 Open

`Root cause:` `OpenCodeAdapter.configure_opencode()` sets `"repo_root": str(_REPO_ROOT)` which points to the actual repo root (`/repos/SilverquiLLM-bench/`). The refactoring agent that wrote PR #11 confused the harness's internal `_REPO_ROOT` (where the harness finds its own files) with the agent's `repo_root` config (what the agent sees as its file boundary). Opencode uses `repo_root` as its navigation root for all glob, grep, and read operations.

`Symptoms:`

- Agent reads `cards/foundations/simple_spells.py`, `engine/casting.py`, `tests/test_integration.py`, etc.
- Agent globs find 75 test files, 28 card implementations — full contamination
- `.workspace/` is a hidden dir, so globs from repo root skip it — agent can't find its own workspace files
- `Glob "**/card_spec.json" 0 matches` despite `card_spec.json` existing in `.workspace/`
- Agent falls back to reading the entire repo as reference material
`Fix:` Change `"repo_root": str(_REPO_ROOT)` to `"repo_root": str(workspace)` in `OpenCodeAdapter.configure_opencode()`. One line.

`Files to change:`

- `silverquillm/adapters/opencode.py` — `configure_opencode()` method
---

## Issue #17: `.pytest_cache` false contamination → `no_output`

`Status:` 🔴 Open

`Root cause:` The Phase 7 refactor switched contamination detection from a denylist (only flag known-bad directories) to an allowlist (flag everything not explicitly allowed). The allowlist includes `__pycache__` but not `.pytest_cache`. When the agent runs pytest during implementation, `.pytest_cache/v/cache/nodeids` is modified. The contamination checker flags this, and `run_card()` overwrites the result to `CardRunStatus.no_output`.

`Symptoms:`

- `Contamination violation: /repos/SilverquiLLM-bench/.pytest_cache/v/cache/nodeids was modified`
- `tested=no_output` despite agent successfully writing `card_impl.py` and `tests.py`
- All scores zeroed for the card
`Fix:` Add `_IGNORED_DIRS` frozenset containing `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, etc. Update `_is_allowed_path()` and `_snapshot_mtimes()` to use it.

`Files to change:`

- `silverquillm/agent_session.py` — `_IGNORED_DIRS`, `_is_allowed_path()`, `_snapshot_mtimes()`
---

## Issue #18: Model thinking/tool calls not visible (streaming broken)

`Status:` 🔴 Open

`Root cause:` Both `BlindStrategy` and `ImplTestStrategy` wrap the adapter call in `ThreadPoolExecutor.submit()`, moving the adapter's `run()` to a worker thread. Before PR #11, the adapter ran directly in the main thread and `sys.stderr.write()` calls streamed to the terminal in real time. The `ThreadPoolExecutor` effectively swallows this streaming.

`Symptoms:`

- No model thinking output visible during benchmark runs
- No tool call output visible
- No ANSI-colored streaming output
- All output that was visible before PR #11 is gone
`Fix:` Replace `ThreadPoolExecutor` with direct `adapter.run_with_retries()` call (already exists in `base.py` with timeout+kill support).

`Files to change:`

- `silverquillm/strategies.py` — both strategy classes
---

## Issue #19: `card_name` vs `card_dir_name` creates duplicate card directories

`Status:` 🔴 Open

`Root cause:` `save_card_result()` uses `card_dir_name` (collector number, e.g. `"42"`) for the results directory, but `_get_postmortem_path()` and `_generate_agent_thoughts()` use `card_name` (display name, e.g. `"Ajani's Response"`). This creates two separate directories for the same card.

`Symptoms:`

- `Cards run: 2` in run summary when only 1 card was actually run
- Postmortem in `cards/Ajani's Response/` but result.json in `cards/42/`
- Post-eval can't correlate postmortem with result
`Fix:` Add `card_id` field to `AgentSession`, use it consistently for all path construction.

`Files to change:`

- `silverquillm/agent_session.py` — add `card_id` field, update path functions
- `silverquillm/cli.py` — pass `card_dir_name` as `card_id`
---

## Issue #20: `agent_thoughts.md` nearly empty

`Status:` 🔴 Open

`Root cause:` The strategy layer calls `adapter.run()` and discards the return value. `run_card()` logs a placeholder to the postmortem: `prompt="(strategy-level)"`, `response="status=no_output"`. The `_generate_agent_thoughts()` function reads from the postmortem, so it generates a nearly empty file from this single placeholder entry.

`Symptoms:`

- `agent_thoughts.md` contains only a status string, not the agent's actual reasoning
- Postmortem has one entry with no useful content
- Unable to debug agent behavior from run artifacts
`Fix:` Add `agent_output` and `prompt_used` fields to `CardRunResult`. Capture adapter output in strategies, pass through to postmortem logging.

`Files to change:`

- `silverquillm/strategies.py` — add fields, capture output
- `silverquillm/agent_session.py` — use real output in postmortem
---

## Issue #21: Preflight `_check_card_specs_dir()` flat glob misses card specs

`Status:` 🔴 Open

`Root cause:` `_check_card_specs_dir()` in `preflight.py` uses `path.glob("*.json")` but card specs are in subdirectories (`cards/1/card_spec.json`). The flat glob finds nothing.

`Symptoms:`

- `Pre-flight checks failed: card_specs_dir contains no card spec files: benchmarks/sos/cards`
- Benchmark run aborted before any LLM calls
`Fix:` Change glob to `path.glob("*/card_spec.json")`.

`Files to change:`

- `silverquillm/preflight.py` — `_check_card_specs_dir()`
---

## Issue #22: Opencode orphan process on benchmark interrupt

`Status:` 🔴 Open (partially fixed — `teardown()` now calls `kill()`, but no signal handler)

`Root cause:` `OpenCodeAdapter` spawns opencode with `start_new_session=True` (separate process group). When the benchmark is Ctrl+C'd, SIGINT goes to the benchmark's process group but NOT to opencode's. `teardown()` was originally a no-op. Even after fixing `teardown()` to call `kill()`, there's no signal handler to ensure `kill()` is called immediately on interrupt — Python's `KeyboardInterrupt` propagation may be blocked in I/O.

`Symptoms:`

- After Ctrl+C, opencode continues running in the background
- `ps aux | grep opencode` shows orphaned processes
- Subsequent runs may conflict with the orphaned process
`Fix:` Add `SIGINT`/`SIGTERM` handler in `cli.py` that calls `_active_session._adapter.kill()` before re-raising.

`Files to change:`

- `silverquillm/cli.py` — signal handler and `_active_session` tracking
