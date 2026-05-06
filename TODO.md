Phase 2.5: CLI Wiring, Contamination Controls & Integration Test

Scope: Wire the existing benchmark modules into a working end-to-end CLI pipeline, implement proper contamination detection, and validate with prototype SOS cards. All modules exist and are individually tested; the gap is orchestration and integration.

---

- [x] **Expand ****`_check_violations`**** to cover all protected directories and return structured violations**
  Detail: In `benchmark/agent_session.py`, the current `_check_violations` function only snapshots `engine/` mtimes via `_snapshot_mtimes` and only detects modifications to existing files within `engine/`. It misses new files created outside the workspace and ignores other protected directories.

  Changes to `benchmark/agent_session.py`:

  - Add a module-level constant `_PROTECTED_DIRS` listing all protected relative paths: `("engine", "cards", "tests", "benchmark", "benchmarks", "docs")`.
  - Create `_snapshot_all_protected(repo_root: Path) -> dict[Path, float]` that calls `_snapshot_mtimes` on each dir in `_PROTECTED_DIRS` (if it exists) and merges results into a single dict.
  - Change `_check_violations` signature to: `_check_violations(workspace: Path, before: dict[Path, float] | None = None) -> list[str]`.
    - Return type changes from `bool` to `list[str]` (list of violation description strings). Empty list = no violations.
    - After the run, call `_snapshot_all_protected(_REPO_ROOT)` to get the "after" snapshot.
    - Compare against `before`: flag any file whose mtime increased (modified) OR any file in "after" that doesn't exist in "before" (newly created).
    - Each violation entry should describe the path and whether it was "modified" or "created".
    - Note: files *inside* the workspace directory are expected to change — only flag files outside it.
    - Continue to use `logger.warning` for each violation found.
  - Keep `_snapshot_mtimes` unchanged (still used internally).
  - Testability: Unit test with a temp directory — create a "before" snapshot, add a new file to a protected dir and modify an existing one, verify `_check_violations` returns two violation strings. Verify empty list when nothing changed. Verify workspace-internal changes are NOT flagged.
- [x] **Wire enhanced violation checks into both agent run methods**
  Detail: In `benchmark/agent_session.py`, update `run_blind_implementation` and `run_test_informed` to use the expanded `_check_violations`.

  Changes to `run_blind_implementation`:

  - Replace `engine_snapshot = _snapshot_mtimes(_REPO_ROOT / "engine")` with `protected_snapshot = _snapshot_all_protected(_REPO_ROOT)`.
  - Replace `if _check_violations(workspace, before=engine_snapshot):` with `violations = _check_violations(workspace, before=protected_snapshot)` and `if violations:`.
  - Log the full violations list via `logger.warning`.
  - The `BlindResult` with `status="violation"` stays the same.
  Changes to `run_test_informed`:

  - Currently has NO violation checking. Add a `_snapshot_all_protected(_REPO_ROOT)` call before each `_run_opencode` invocation within the iteration loop.
  - After each `_run_opencode` call, check violations. If violations found, log and return `TestInformedResult` with `status="violation"`.
  - Place the snapshot+check around each agent invocation, not the whole loop, so per-round violations are detected.
  Testability: Mock `_run_opencode` to create a file in a protected dir (e.g., `engine/hack.py`). Verify `run_blind_implementation` returns `status="violation"`. Verify `run_test_informed` returns `status="violation"` when a protected file is created during a round.

- [ ] **Add card-spec loading and filtering utility**
  Detail: Create `benchmark/card_loader.py` with functions to load card specs and filter them for CLI use.

  File: `benchmark/card_loader.py`

  - Function: `load_card_specs(specs_dir: str) -> list[dict]` — walk `specs_dir` (e.g., `benchmarks/sos/cards/`), for each subdirectory containing `card_spec.json`, parse and return the spec dict. Return list sorted by `collector_number`.
  - Function: `load_prototype_cards(prototype_path: str) -> list[dict]` — load `prototype_cards.json`, extract collector numbers, and return them.
  - Function: `filter_by_collectors(specs: list[dict], collector_numbers: list[str]) -> list[dict]` — filter specs list to only those whose `collector_number` is in the given list. Raise `ValueError` if any requested collector number is not found.
  - Function: `filter_by_prototype(specs: list[dict], prototype_path: str) -> list[dict]` — load prototype card collector numbers and filter specs. Important: use the full specs from `benchmarks/sos/cards/`, NOT the prototype JSON directly (which lacks fields like `keywords`, `colors`, `rarity`).
  These are pure utilities with no side effects. The CLI will compose them.

  Testability: Create a temp directory with two `card_spec.json` files. `load_card_specs` finds both. `filter_by_collectors` with one number returns one card. `filter_by_collectors` with unknown number raises `ValueError`.

- [ ] **Add ****`--cards`****, ****`--prototype`****, and ****`--dry-run`**** flags to ****`benchmark run`**
  Detail: In `benchmark/cli.py`, extend the `run` command with filtering and validation flags.

  Changes to `benchmark/cli.py`:

  - Add imports from `benchmark.card_loader`.
  - Add Click options to `run`:
    - `--cards` (`card_ids`): comma-separated collector numbers string. Optional.
    - `--prototype` (`use_prototype`): boolean flag, default False.
    - `--dry-run` (`dry_run`): boolean flag, default False.
    - `--cards` and `--prototype` are mutually exclusive — add a manual check at the top of the function that raises `click.UsageError` if both are set.
  - In the `run` function body (after loading config):
    1. Load all card specs via `load_card_specs(cfg.card_specs_dir)`. If no specs found, error and exit.
    2. If `--cards` provided: split on comma, call `filter_by_collectors`.
    3. If `--prototype` provided: call `filter_by_prototype` using `benchmarks/{set_code}/prototype_cards.json`.
    4. Print card count and list card names with tiers.
    5. If `--dry-run`: print "Dry run complete. {N} cards selected." and return.
    6. Otherwise, fall through to the orchestration loop (wired in next item).
  - Remove the existing classified-data loading logic from `run` (card_loader replaces it).
  Testability: `benchmark run --config ... --dry-run` exits 0 and prints card count. `benchmark run --config ... --cards 011 --dry-run` lists only Eager Glyphmage. `--cards` and `--prototype` together produces an error.

- [ ] **Wire ****`benchmark run`**** orchestration loop**
  Detail: In `benchmark/cli.py`, implement the main benchmark execution loop inside the `run` command after card selection (when `--dry-run` is not set).

  The loop must:

  1. Call `init_results_dir(cfg)` from `benchmark.results` to create the run directory.
  2. For each card spec:
    a. Resolve `card_dir` = `{card_specs_dir}/{collector_number}/`.

    b. Create `AgentSession(config=cfg, card_spec=spec, card_dir=card_dir)`.

    c. Call `session.setup_workspace()`.

    d. Call `session.run_blind_implementation(workspace)`.

    e. If blind result has `impl_path` and status is "ok" or "syntax_error": call `session.run_test_informed(workspace, blind_impl_path)`.

    f. **Before calling ****`session.cleanup()`**: read source code from result file paths into dicts (workspace is deleted on cleanup).

    g. Call `session.cleanup()`.

    h. Build result dicts for `save_card_result`:

    i. Call `save_card_result(run_dir, collector_number, blind_result_dict, test_result_dict)`.

    j. Print per-card progress: `"[{i}/{total}] {card_name}: blind={status}, tested={status}"`.

  3. After the loop, proceed to post-loop eval+summary (next item).
  Extract a helper `_session_results_to_dicts(blind: BlindResult, tested: TestInformedResult, spec: dict, config: BenchmarkConfig) -> tuple[dict, dict]` in `cli.py` (or a new `benchmark/run_utils.py`) to handle the dataclass-to-dict conversion and file reading. This keeps the loop body clean.

  Testability: Mock `AgentSession._run_opencode` to produce a stub `blind_impl.py` in the workspace. Run `benchmark run --config ... --cards 011`. Verify `run_dir/cards/011/result.json` exists with expected structure. Verify `blind_impl.py` file exists in results.

- [ ] **Wire ****`benchmark run`**** post-loop: self-eval and summary**
  Detail: After the orchestration loop completes in `benchmark/cli.py`, run self-eval on all results and save the run summary.

  After the card loop:

  1. For each card directory in `run_dir/cards/`:
    - **Layout note**: `save_card_result` writes `blind_impl.py`, `tested_impl.py`, `tests.py` directly in `cards/{card_id}/` (flat layout). But `run_self_eval` in `evaluator.py` expects `{card_dir}/{agent_name}/` subdirectories.
    - **Resolution**: Add a `run_self_eval_flat(card_dir: Path, agent_name: str) -> EvalResult` function to `benchmark/evaluator.py` that works with the flat layout — uses `run_tests(card_dir / "blind_impl.py", card_dir / "tests.py")` and `run_tests(card_dir / "tested_impl.py", card_dir / "tests.py")` directly.
    - Call `run_self_eval_flat(card_dir, cfg.model_name)` for each card.
  2. Load each card's `result.json`, merge self-eval results into it, re-save.
  3. Collect all result records and call `save_run_summary(run_dir, all_results)`.
  4. Print summary: total cards run, self-eval pass rates (blind vs tested), elapsed wall-clock time.
  Testability: Create a mock run directory with `blind_impl.py`, `tested_impl.py`, and `tests.py` files. Verify `summary.json` is written with correct `card_count`. Verify self-eval results appear in each card's `result.json`.

- [ ] **Wire ****`benchmark eval`**** command**
  Detail: In `benchmark/cli.py`, implement the `eval` subcommand to run evaluation on existing results.

  Changes to `benchmark/cli.py`:

  - Add Click option: `--audited-tests` (optional path to gold-standard test file).
  - Replace the stub `eval` function body:
    1. Scan `results_dir` to find run directories (each contains `config.yaml` + `cards/`).
    2. Detect agents: read `config.yaml` from each run dir, extract `model_name`.
    3. For single-agent runs (Phase 2.5 scope): run `run_self_eval_flat` on each card. Skip cross-eval (N×(N-1) = 0 when N=1).
    4. For multi-agent runs (future): consolidate per-card artifacts into temp `{card_id}/{agent_name}/` layout and call `run_cross_eval`. Add a `# TODO: multi-agent cross-eval consolidation` comment for now.
    5. If `--audited-tests` provided: for each card, call `run_tests(blind_impl, audited_tests)` and `run_tests(tested_impl, audited_tests)`, construct `EvalResult` with `eval_type="audited"`.
    6. Save all eval results as JSON list in `results_dir/results.json` (the format `_load_eval_results` in `scorer.py` expects — list of dicts with keys matching `EvalResult` fields).
    7. Print eval summary: cards evaluated, pass rates by eval type.
  Testability: Create a mock results dir with one run containing `blind_impl.py`, `tested_impl.py`, `tests.py`. `benchmark eval --results-dir ...` exits 0, writes `results.json`. With `--audited-tests`, audited eval results appear in the JSON.

- [ ] **Wire ****`benchmark score`**** command**
  Detail: In `benchmark/cli.py`, implement the `score` subcommand.

  Changes to `benchmark/cli.py`:

  - Add Click option: `--tier-data` (optional path to tier data JSON; defaults to `benchmarks/{set_code}/data/{set_code}_classified.json`).
  - Add Click option: `--set` (`set_code`): set code for default tier data path resolution. Default `"sos"`.
  - Replace the stub `score` function body:
    1. Parse `--results-dir` path.
    2. Load tier data: read classified JSON, build `dict[str, str]` mapping each card's `collector_number` → `tier` name.
    3. Call `compute_scores(results_dir, tier_data)` from `benchmark.scorer`.
    4. Call `generate_leaderboard(scores)` to get Markdown string.
    5. Print leaderboard to stdout.
    6. Collect all run directories under `results_dir`.
    7. Call `save_aggregates(results_dir, run_dirs, scores)`.
    8. Print paths to written files: `leaderboard.md`, `summary.json`.
  Testability: Create a mock `results_dir` containing `results.json` with eval data. `benchmark score --results-dir ...` prints leaderboard. `leaderboard.md` and `summary.json` are written.

- [ ] **Create integration test helpers: mock OpenCode and test fixtures**
  Detail: Create `tests/benchmark/test_helpers.py` with reusable fixtures for the full-pipeline integration test.

  File: `tests/benchmark/test_helpers.py`

  - Function: `mock_opencode_blind(card_spec: dict) -> Callable[[str, Path], str]` — returns a function matching `_run_opencode(prompt, workspace) -> str` signature. It:
    - Writes a minimal valid Python class to `workspace/blind_impl.py` using the card's class name from `card_name_to_class_name(spec["name"])` and correct base class from `template_gen`.
    - Returns a fake stdout string (simulates OpenCode output with token info).
  - Function: `mock_opencode_test_informed(card_spec: dict) -> Callable[[str, Path], str]` — similar mock that:
    - Copies `workspace/blind_impl.py` to `workspace/tested_impl.py` (or writes a slightly modified version).
    - Writes a minimal `workspace/tests.py` with 2-3 basic test cases that `from card_impl import {ClassName}` and assert the class exists and has correct `name` attribute.
    - Returns fake stdout.
  - Function: `create_test_config(tmp_path: Path, set_code: str = "sos") -> BenchmarkConfig` — returns a BenchmarkConfig with temp paths, timeout=10, max_test_rounds=1.
  These helpers let integration tests exercise the real pipeline while mocking only the OpenCode subprocess.

  Testability: Helpers are importable. `mock_opencode_blind` produces a `.py` file that `compile()`s without `SyntaxError`.

- [ ] **Full pipeline integration test with Eager Glyphmage and Ajani's Response**
  Detail: Create `tests/benchmark/test_e2e.py` with a pytest integration test validating the full pipeline.

  Test class: `TestBenchmarkEndToEnd` (mark with `@pytest.mark.integration`)

  Test: `test_full_pipeline_two_cards`:

  1. Load card specs for Eager Glyphmage (collector_number `"11"`) and Ajani's Response (collector_number `"6"`) from `benchmarks/sos/cards/`.
  2. Create a `BenchmarkConfig` via `create_test_config(tmp_path)` pointing at a temp output directory.
  3. For each card:
    a. Create `AgentSession` with the loaded spec.

    b. Monkey-patch `session._run_opencode` — use `mock_opencode_blind` on the first call, `mock_opencode_test_informed` on subsequent calls.

    c. Call `session.setup_workspace()`.

    d. **Assert workspace contains**: `card_spec.json`, `engine_api.md`, `base_classes.py`, `template.py`, `rules_overview.md`, `foundations/` directory.

    e. Call `session.run_blind_implementation(workspace)` → assert `BlindResult.status == "ok"` and `impl_path` exists.

    f. Call `session.run_test_informed(workspace, blind_impl)` → assert `TestInformedResult` has `impl_path` and `tests_path`.

    g. Read impl/test sources from workspace before cleanup.

    h. Call `session.cleanup()` → assert workspace directory no longer exists.

  4. Call `init_results_dir`, `save_card_result` for both cards.
  5. **Assert directory structure**: `run_dir/cards/11/result.json`, `run_dir/cards/6/result.json`, `blind_impl.py`, `tested_impl.py` exist.
  6. Run `run_self_eval_flat` on each card's artifacts.
  7. Call `save_run_summary` → assert `summary.json` has `card_count: 2`.
  8. Build tier_data, call `compute_scores` → assert `Leaderboard` returned (may have zeros since single agent, no cross-eval).
  9. Call `generate_leaderboard` → assert non-empty Markdown string containing "Category 1".
  10. Call `save_aggregates` → assert `leaderboard.md` exists in results dir.
  Test: `test_workspace_contamination_detected`:

  1. Create an `AgentSession` for Eager Glyphmage.
  2. Monkey-patch `_run_opencode` to create a file in `engine/` (simulating contamination).
  3. Call `run_blind_implementation` → assert `BlindResult.status == "violation"`.
  Run with: `pytest tests/benchmark/test_e2e.py -m integration`

  Testability: Tests pass with mocked OpenCode. The full flow exercises real config loading, workspace setup, results saving, eval, and scoring.

---

**Note:** After Phase 2.5 validates the end-to-end pipeline with mocked agents, the next step is to run it for real with OpenCode against the Strixhaven prototype cards and iterate on prompts based on results.
