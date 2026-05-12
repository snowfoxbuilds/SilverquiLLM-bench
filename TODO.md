# TODO

## Phase 7: Harness Architecture Refactor & Robustness

Scope: Refactor the benchmark runner from the current harness-orchestrated multi-round model to a clean mode-based architecture where the agent is a black box (prompt in → files out). Fix known issues #11, #12, #14, #15. Add robustness infrastructure (smoke tests, pre-flight validation, allowlist contamination checker). Add post-run aggregation.

This phase implements the architectural decisions settled in the 2026-05-11 grill session. See [BENCHMARK-RUNNER.md](http://benchmark-runner.md/) Decisions section (entries tagged `[SETTLED, 2026-05-11 grill]`) and [CONTEXT.md](http://context.md/) Relationships for the canonical design.

Key architectural changes:

- Two benchmark modes: `blind` (impl only) and `impl_test` (impl + tests, agent self-iterates)
- Single prompt per card, single `timeout_per_card` — harness does NOT orchestrate test rounds
- All evaluation is post-run (no per-card eval during the run)
- Filesystem checks are the source of truth for agent output (not exit codes or stdout)
- Engine snapshot/rollback on timeout
- `CardStrategy` pattern for per-card orchestration (mode-agnostic outer loop)
Reference files in current codebase:

- `silverquillm/config.py` — `BenchmarkConfig` + `AgentConfig` dataclasses
- `silverquillm/agent_session.py` — 51KB, contains `_run_pytest`, multi-round orchestration, `harvest_results`, violation checking
- `silverquillm/evaluator.py` — `run_tests()`, `run_self_eval()`, `run_self_eval_flat()`, `EvalResult` with blind/tested split
- `silverquillm/cli.py` — `benchmark run` and `benchmark eval` commands, per-card eval loop
- `silverquillm/prompts.py` — Step 1 (blind) and Step 2 (test-informed) prompt templates
- `silverquillm/results.py` — result recording with blind/tested fields
- `silverquillm/regression.py` — per-card regression runner
- `silverquillm/adapters/base.py` — `AgentAdapter` ABC with `run()` method
---

- [x] **Add ****`mode`**** to config and create ****`CardStrategy`**** ABC**
  Detail: Add `mode: str` field to `BenchmarkConfig` in `silverquillm/config.py`. Valid values: `"blind"` and `"impl_test"`. Remove `max_test_rounds` from `AgentConfig` (no longer used — agent self-manages iteration). Create `silverquillm/strategies.py` with:

  - `CardStrategy` ABC with abstract method `run_card(self, card_spec, workspace, adapter, timeout) -> CardRunResult`
  - `CardRunResult` dataclass: `status` (enum: `completed`, `timeout`, `no_output`), `files_written` (list of Path), `runtime_ms` (int), `engine_modified` (bool)
  - Factory function `get_strategy(mode: str) -> CardStrategy` that returns `BlindStrategy` or `ImplTestStrategy`
  Update `load_config()` to parse `mode` from YAML (default `"impl_test"` for backward compat). Update `config.example.yaml` with the new `mode` field.

  Reference `KEY_DECISIONS.md` entry "Nested AgentConfig convention" — follow the same pattern for the new field.

  Testability: Unit test that `load_config()` parses `mode` correctly, rejects invalid values, defaults to `"impl_test"`. Unit test that `get_strategy()` returns correct strategy class.

- [x] **Implement ****`BlindStrategy`**
  Detail: In `silverquillm/strategies.py`, implement `BlindStrategy(CardStrategy)`. This strategy:

  1. Sends a single prompt to the agent: "Implement this card, write to `card_impl.py`. Do not write tests."
  2. After agent finishes (or timeout), checks filesystem for `card_impl.py`
  3. Returns `CardRunResult` with `status=completed` if file exists, `no_output` if not, `timeout` if timed out
  The prompt template should be derived from the existing blind prompt in `silverquillm/prompts.py` but updated to reference `card_impl.py` instead of `blind_impl.py`. The workspace must NOT include `test_utils.md` or `test_utils.py` (mode-dependent workspace contents per [BENCHMARK-RUNNER.md](http://benchmark-runner.md/)).

  Files to change:

  - `silverquillm/strategies.py` — add `BlindStrategy` class
  - `silverquillm/prompts.py` — add `blind_mode_prompt()` that references `card_impl.py` and omits test-related instructions
  Testability: Unit test with a mock adapter that writes `card_impl.py` → strategy returns `completed`. Mock adapter that writes nothing → `no_output`.

- [x] **Implement ****`ImplTestStrategy`**
  Detail: In `silverquillm/strategies.py`, implement `ImplTestStrategy(CardStrategy)`. This strategy:

  1. Sends a single prompt: "Implement this card and write tests. Write implementation to `card_impl.py`, tests to `tests.py`. You can run tests yourself to iterate."
  2. After agent finishes (or timeout), checks filesystem for `card_impl.py` and optionally `tests.py`
  3. Returns `CardRunResult` with appropriate status
  The prompt template should combine elements from the existing blind + test-informed prompts in `silverquillm/prompts.py`, updated for unified `card_impl.py` naming. The workspace includes `test_utils.md` and `test_utils.py`. No `max_test_rounds` — agent self-manages iteration.

  Files to change:

  - `silverquillm/strategies.py` — add `ImplTestStrategy` class
  - `silverquillm/prompts.py` — add `impl_test_mode_prompt()` combining impl + test instructions
  Testability: Unit test with mock adapter that writes both files → `completed`. Mock adapter that writes only `card_impl.py` (no tests) → `completed` (partial is still completed, eval will just skip self-eval).

- [x] **Refactor ****`agent_session.py`****: remove harness-managed iteration**
  Detail: The current `agent_session.py` (51KB) contains `_run_pytest`, multi-round orchestration logic, and round counting. Remove all of this:

  - Delete `_run_pytest()` method entirely — the harness does NOT run pytest during agent implementation rounds
  - Remove round-counting logic and `max_test_rounds` references
  - Remove the iteration loop that feeds test results back to the agent
  - Keep: workspace setup (`_setup_workspace()`), `harvest_results()`, engine management (`init_run_engine()`, `commit_engine_changes()`), postmortem logging, violation checking
  The goal is that `agent_session.py` becomes a thin wrapper: set up workspace → delegate to `CardStrategy.run_card()` → harvest files → log postmortem. The strategy handles the prompt and agent invocation.

  Refactor `harvest_results()` to look for `card_impl.py` instead of `blind_impl.py`/`tested_impl.py`.

  Files to change:

  - `silverquillm/agent_session.py` — major refactor (remove ~40% of the file)
  Testability: Existing integration tests should still pass after refactor. New unit test: workspace setup creates correct files for each mode (blind mode has no test_utils, impl_test mode has test_utils).

- [x] **Decouple ****`harvest_results()`**** from violation status (fixes Issue #15)**
  Detail: Currently, `harvest_results()` in `agent_session.py` is skipped or partial when a violation is detected. Ral Zarek (#97) got a violation and its implementation files were never captured. Fix: `harvest_results()` must run unconditionally — always copy `card_impl.py` and `tests.py` from the workspace regardless of violation status. Violations annotate `result.json` but don't prevent file capture.

  Files to change:

  - `silverquillm/agent_session.py` — ensure `harvest_results()` is called before violation status affects control flow
  Testability: Unit test: mock adapter writes `card_impl.py` + triggers a violation → both violation is recorded AND `card_impl.py` is harvested.

- [x] **Engine snapshot and rollback on timeout**
  Detail: Before each card starts, snapshot the run-level engine directory (e.g., `shutil.copytree(run_engine_dir, run_engine_dir.with_suffix('.snapshot'))`). If the agent times out, restore the snapshot — this prevents corrupted partial engine modifications from poisoning subsequent cards. On successful completion, delete the snapshot and commit engine changes as normal.

  The snapshot/restore logic should live in `agent_session.py` alongside the existing `init_run_engine()` and `commit_engine_changes()` functions. Add `snapshot_engine(run_engine_dir) -> Path` and `restore_engine_snapshot(run_engine_dir, snapshot_dir)` functions.

  Files to change:

  - `silverquillm/agent_session.py` — add snapshot/restore functions, call them in the per-card flow
  Testability: Unit test: mock adapter that times out → engine dir is restored to pre-card state. Mock adapter that succeeds → snapshot is cleaned up.

- [x] **Enforce ****`timeout_per_card`**** (fixes Issue #14)**
  Detail: Config specifies `timeout_per_card: 300` but it's never enforced — Qwen's Plains (trivial) took 28 minutes. Wrap the adapter's `run()` call with a hard timeout. On expiry: kill the subprocess, record `status: timeout` in `CardRunResult`, zero all scores for this card, trigger engine rollback (previous item).

  Implementation: In the `CardStrategy.run_card()` base method (or a shared utility), use `subprocess` timeout or `signal.alarm()` as a fallback. The adapter's own `run_with_retries()` in `silverquillm/adapters/base.py` already has a deadline concept — ensure it's actually enforced at the process level, not just as a soft limit.

  Files to change:

  - `silverquillm/strategies.py` — timeout enforcement in `run_card()` base method
  - `silverquillm/adapters/base.py` — verify `run_with_retries` kills subprocess on deadline
  - `silverquillm/adapters/opencode.py` — ensure `Popen` subprocess is killed on timeout
  Testability: Unit test: mock adapter that sleeps forever → times out at `timeout_per_card`, status is `timeout`.

- [x] **Move all evaluation to post-run**
  Detail: Currently `cli.py` runs self-eval per card inside the run loop. Refactor so the run loop ONLY does: workspace setup → [strategy.run](http://strategy.run/)_card() → harvest → postmortem → next card. After ALL cards complete, a separate evaluation phase runs all tests against the final engine state.

  Create `silverquillm/post_eval.py` with:

  - `run_post_eval(run_dir: Path, mode: str, audited_dir: Path | None) -> list[CardEvalResult]`
  - For each card in `run_dir/cards/`, run `evaluator.run_tests()` with the card's `card_impl.py` against:
    - Agent's `tests.py` (self-eval, impl_test mode only)
    - Audited tests from `tests/audited/{set_code}/{collector_number}/tests.py` (if `audited_dir` provided)
  - All tests run against the final engine state (the run-level engine dir as it exists after the last card)
  - Write results to each card's `result.json`
  Update `cli.py` to call `run_post_eval()` after the card loop instead of per-card eval.

  Files to change:

  - `silverquillm/post_eval.py` — new module
  - `silverquillm/cli.py` — refactor `benchmark run` to separate card loop from eval
  - `silverquillm/evaluator.py` — update `run_tests()` to accept `engine_dir` param for PYTHONPATH
  Testability: Integration test: run 2 mock cards → post_eval runs all tests against final engine → results written to both cards' result.json.

- [x] **Refactor ****`EvalResult`**** and ****`result.json`**** to v2 schema**
  Detail: The current `EvalResult` in `evaluator.py` has `blind_passed`/`blind_failed`/`tested_passed`/`tested_failed` fields reflecting the old blind/tested split. Refactor to v2 schema:

  ```python
@dataclass
class EvalResult:
    card_id: str
    mode: str  # "blind" | "impl_test"
    model_name: str
    adapter: str
    status: str  # "completed" | "timeout" | "no_output"
    complexity_tier: str
    implementation: dict  # {tokens: {input, output, total}, runtime_ms, peak_context}
    self_eval: dict | None  # {passed, failed, total} — None for blind mode
    audited_eval: dict | None  # {passed, failed, total}
    engine_diff_summary: str  # human-readable summary of engine changes
    errors: list[str]
  ```

  Update `silverquillm/results.py` to write v2 `result.json`. Update `silverquillm/scorer.py` to read v2 format. Keep backward-compat reading of v1 format for existing results (Gemma/Qwen runs).

  Files to change:

  - `silverquillm/evaluator.py` — refactor `EvalResult` dataclass
  - `silverquillm/results.py` — update `save_card_result()` and `load_card_result()`
  - `silverquillm/scorer.py` — update scoring to use v2 fields
  Testability: Unit test: v2 result.json round-trips correctly. Unit test: v1 result.json from existing runs still loads.

- [x] **Automatic ****`run_summary.json`**** aggregation**
  Detail: After post-run evaluation completes, automatically aggregate all per-card `result.json` files into a `run_summary.json` at the run level. Create `silverquillm/aggregator.py` with:

  - `aggregate_run(run_dir: Path) -> RunSummary` — pure function, reads all `cards/*/result.json`, produces summary
  - `RunSummary` dataclass with:
    - **Run metadata:** run_id, model_name, adapter, mode, timestamp, config snapshot
    - **Scorecard:** total_cards, cards_completed, cards_timeout, cards_no_output
    - **Per-tier breakdown:** for each complexity_tier: card_count, completed_count, avg_audited_pass_rate
    - **Aggregate stats:** total_tokens, total_runtime_ms, avg_tokens_per_card, avg_runtime_per_card
    - **Per-card summary:** list of {card_id, status, self_eval_pass_rate, audited_eval_pass_rate}
  Wire into `cli.py` as the final step of `benchmark run`. Also expose as `benchmark aggregate <run_dir>` for manual re-runs.

  Files to change:

  - `silverquillm/aggregator.py` — new module
  - `silverquillm/cli.py` — call aggregator at end of run, add `benchmark aggregate` subcommand
  Testability: Unit test: create mock `result.json` files → `aggregate_run()` produces correct summary. Test idempotency: running twice on same dir produces identical output.

- [x] **Allowlist-based contamination checker**
  Detail: Replace the current fragile blocklist approach in `agent_session.py`'s `_check_violations()` with an allowlist. The agent may only create/modify files within its workspace directory. Only flag modifications to explicitly protected files (card specs of other cards, audited tests, other agents' implementations). This eliminates the entire class of false-positive violations from `__pycache__`, log files, `.pyc` files, etc.

  Current `_check_violations()` maintains a `_PROTECTED_DIRS` set and checks if ANY file outside the workspace was modified. Replace with:

  1. After agent finishes, diff the workspace against its initial state
  2. Any NEW files in workspace → allowed (agent output)
  3. Any MODIFIED files in workspace → allowed (agent modified engine, etc.)
  4. Any changes OUTSIDE workspace → violation
  5. Exception: `engine/` modifications are allowed (agents extend the engine)
  Files to change:

  - `silverquillm/agent_session.py` — rewrite `_check_violations()` with allowlist logic
  Testability: Unit test: agent writes `card_impl.py` in workspace → no violation. Agent modifies `engine/ward.py` → no violation. Agent modifies `tests/audited/sos/001/tests.py` → violation detected.

- [x] **Fix `test_utils.md`**** import path (fixes Issue #11)**
  Detail: Agent-facing `test_utils.md` documentation says `from tests.test_utils import ...` but workspace has flat `test_utils.py` at the root. Agents waste a correction iteration discovering this. Update all import examples to `from test_utils import create_game, set_board_state, cast_spell, ...`.

  Files to change:

  - `docs/test_utils.md` (or `tests/test_utils.md` — check which path the workspace copies from) — update all import examples
  Testability: Grep the updated file for `from tests.test_utils` — should find zero matches. Grep for `from test_utils import` — should find all examples.

- [ ] **Add ****`GameState`**** to template imports (fixes Issue #12)**
  Detail: Nearly every card implementation needs `from engine.game_state import GameState` for type hints. Agents waste time adding this import. Add it to the template that `silverquillm/template_gen.py` generates.

  Files to change:

  - `silverquillm/template_gen.py` — add `from engine.game_state import GameState` to the generated template's import block
  Testability: Generate a template for any card → verify `GameState` is in the imports.

- [ ] **Simplify postmortem schema**
  Detail: The current `postmortem.jsonl` events use `round` and `phase` fields from the old multi-round model. Update to the simplified schema:

  - Remove `round` and `phase` fields from all events
  - Change `file_diff` event to `file_written` with `path` and `size_bytes` (harness only knows which files exist, not diffs)
  - Add `eval_result` event type for post-run eval results: `{"event": "eval_result", "eval_type": "self"|"audited", "passed": N, "failed": N}`
  - Add `regression_check` event type (future use)
  Update the postmortem writer in `agent_session.py` and the `agent_thoughts.md` extractor.

  Files to change:

  - `silverquillm/agent_session.py` — update postmortem event emission
  Testability: Run mock adapter → postmortem.jsonl has no `round` or `phase` fields. Has `file_written` events for each file the agent created.

- [ ] **Pre-flight validation at run start**
  Detail: Before any LLM calls, verify the environment is correct. Add a `preflight_check(config, run_dir)` function that validates:

  - `template.py` imports resolve (can import `engine.game_state`, `engine.card`, etc.)
  - `test_utils.py` is importable with the flat import path (`from test_utils import create_game`)
  - Workspace directory can be created and cleaned
  - Engine test suite passes on clean engine copy (`pytest tests/ -x -q --ignore=tests/audited`)
  - Config is valid: `timeout_per_card > 0`, adapter exists in registry, mode is valid
  - `card_specs_dir` exists and contains at least one card spec
  If any check fails, abort with a clear error message before spending LLM budget.

  Files to change:

  - `silverquillm/preflight.py` — new module with `preflight_check()` function
  - `silverquillm/cli.py` — call `preflight_check()` before entering the card loop
  Testability: Unit test: missing card_specs_dir → preflight fails with clear message. Unit test: invalid adapter name → preflight fails.

- [ ] **Smoke tests with mock adapter (****`tests/test_harness.py`****)**
  Detail: Comprehensive deterministic pytest tests (zero LLM calls) using a `MockAdapter` that writes pre-baked implementations from `cards/foundations/`. These test the full harness pipeline end-to-end.

  Create `silverquillm/adapters/mock.py` with a `MockAdapter` that:

  - Reads a known-good implementation from `cards/foundations/{card_name}.py`
  - Writes it to `card_impl.py` in the workspace
  - Optionally writes pre-baked `tests.py` (for impl_test mode)
  Test cases in `tests/test_harness.py`:

  1. **Blind mode happy path**: MockAdapter writes `card_impl.py` → harvest succeeds → post-eval with audited tests passes
  2. **Impl+test mode happy path**: MockAdapter writes `card_impl.py` + `tests.py` → harvest succeeds → self-eval + audited eval both pass
  3. **Timeout handling**: MockAdapter sleeps forever → timeout fires → status is `timeout` → engine rolled back → scores zeroed
  4. **No output**: MockAdapter writes nothing → status is `no_output` → scores zeroed
  5. **Violation detection**: MockAdapter writes to protected path → violation recorded → files still harvested (Issue #15 regression)
  6. **Aggregation**: Run 3 mock cards → `run_summary.json` produced with correct aggregate stats
  7. **Mode-dependent workspace**: Blind mode workspace has no `test_utils.md`/`test_utils.py`; impl_test mode has them
  Also wire `--dry-run` flag in `cli.py` to use MockAdapter for quick environment validation.

  Files to change:

  - `silverquillm/adapters/mock.py` — new MockAdapter
  - `tests/test_harness.py` — new test file with all above test cases
  - `silverquillm/cli.py` — `--dry-run` flag uses MockAdapter
  Testability: All tests are deterministic, zero LLM calls. Should run in < 30 seconds. Run in CI on every commit.
