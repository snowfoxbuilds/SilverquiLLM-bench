# TODO

## Phase 12: Result Path Migration & Run Name Format

Scope: Migrate all result directory paths from legacy conventions (`results/{run_name}/` and `benchmarks/<set>/results/`) to the new convention (`docker/<image_dir>/results/<run_name>/`). Change run name format from `{image_short}_{timestamp}` to `<set_code>-<timestamp>`. Add test artifact cleanup.

Reference: [Prompt: Migrate Result Paths & Run Name Format](prompt-page) for the full file audit. [CONTEXT.md](http://context.md/) for vocabulary.

Canonical implementation constraints for this TODO:

- `<image_dir>` is derived from `--image` by stripping the `silverquillm-` prefix and `:tag` suffix. E.g. `silverquillm-local-pi-blind:latest` → `local-pi-blind`.
- `<run_name>` format: `<set_code>-<timestamp>`. For v1, set code is always `sos`. E.g. `sos-2026-05-16T19-49`.
- Respect KEY_[DECISIONS.md](http://decisions.md/) `_REPO_ROOT convention`: both `cli.py` and `workspace.py` use `_REPO_ROOT = Path(__file__).resolve().parent.parent`.
- Respect KEY_[DECISIONS.md](http://decisions.md/) `Docker log file naming`: [runner.py](http://runner.py/) copies `.tmp` → `.log` after pipe threads join.
- Respect KEY_[DECISIONS.md](http://decisions.md/) `Integration test CLI invocation pattern`: use `[sys.executable, "-m", "silverquillm.cli", ...]` in subprocess calls.
- Use [CONTEXT.md](http://context.md/) vocabulary throughout: Agent Container, Workspace, Hard Timeout, Hang Timeout, Output Snapshot, Run Manifest, User Prompt.
---

- [ ] **Update ****`_make_run_name()`****, add ****`_image_dir()`**** and ****`_image_results_dir()`****, wire into ****`run()`**** default**
  Detail: Three related changes in `silverquillm/cli.py` that form one logical unit:

  1. **`_image_dir(image: str) -> str`** — New helper. Strips `silverquillm-` prefix and `:tag` suffix from a Docker image name. Implementation: `short = image.rsplit("/", 1)[-1].split(":")[0]`, then `if short.startswith("silverquillm-"): short = short[len("silverquillm-"):]`. E.g. `silverquillm-local-pi-blind:latest` → `local-pi-blind`, `ghcr.io/user/silverquillm-pi-blind:latest` → `pi-blind`, `my-custom-image:v2` → `my-custom-image`.
  2. **`_image_results_dir(image: str) -> Path`** — New helper. Returns `_REPO_ROOT / "docker" / _image_dir(image) / "results"`. This replaces the old default `_REPO_ROOT / "results"`.
  3. **`_make_run_name(set_code: str = "sos") -> str`** — Change signature from `_make_run_name(image: str)` to `_make_run_name(set_code: str = "sos")`. Change return format from `f"{short}_{ts}"` to `f"{set_code}-{ts}"`. Remove the image-name parsing logic (moved to `_image_dir`).
  4. **Wire into ****`run()`** — Change `results_dir` default from `_REPO_ROOT / "results"` to `_image_results_dir(image)`. Change `_make_run_name(image)` call to `_make_run_name()` (uses default `"sos"`). The `container_name = f"sqm-{run_name}"` line stays as-is — it will naturally produce `sqm-sos-2026-05-16T19-49`.
  Files: `silverquillm/cli.py`.

  Testability: Update `TestRunName` in `tests/test_cli_docker.py` — replace old tests with: `test_default_set_code()` calling `_make_run_name()` and asserting `sos-` prefix + timestamp pattern; `test_custom_set_code()` calling `_make_run_name("fdn")` and asserting `fdn-` prefix. Add new `TestImageResultsDir` class testing `_image_results_dir()` with inputs: `"silverquillm-local-pi-blind:latest"` → ends with `docker/local-pi-blind/results`, `"my-custom-image:v2"` → `docker/my-custom-image/results`, `"ghcr.io/user/silverquillm-pi-blind:latest"` → `docker/pi-blind/results`. Verify `TestRunDefaults.test_default_timeout_3600` still passes (it doesn't check results_dir).

- [ ] **Update ****`.gitignore`**** for new results path convention**
  Detail: In `.gitignore`, find the `results/` line at the bottom and replace it with `docker/*/results/`. This ignores result artifacts under the new `docker/<image_dir>/results/` tree. Keep `benchmarks/*` as-is (it serves other purposes). No other `.gitignore` entries reference `results/`.

  Files: `.gitignore`.

  Testability: Create a dummy file at `docker/test-img/results/dummy.txt`, run `git status`, confirm it doesn't appear. Remove the dummy file.

- [ ] **Update ****`README.md`**** — all legacy results path references**
  Detail: `README.md` has 5+ locations referencing `results/{run_name}/...` or the old run name format. Every instance must be updated:

  1. **"Harvest Final Workspace" section** (~line 76): `results/{run_name}/workspace_final/` → `docker/<image_dir>/results/<run_name>/workspace_final/`.
  2. **"Runner Artifacts" section** — single-run tree: replace `results/{run_name}/` root with `docker/<image_dir>/results/<run_name>/`.
  3. **"Runner Artifacts" section** — cross-run tree: replace `results/` + `pi-blind_2026-05-13T01-30/` with per-image layout showing `docker/local-pi-blind/results/sos-2026-05-13T01-30/` etc.
  4. **"Logs and Telemetry" section**: `results/{run_name}/docker_stdout.log` → `docker/<image_dir>/results/<run_name>/docker_stdout.log` (and stderr).
  5. **"Snapshot fallback" section**: `results/{run_name}/workspace_final/` → update.
  Also add a brief note explaining `<image_dir>` derivation at first occurrence.

  Files: `README.md`.

  Testability: `grep -n 'results/{run_name}' README.md` should return zero matches after the change. Visual review of tree diagrams.

- [ ] **Update ****`PROJECT_MAP.md`**** — results path references**
  Detail: Three locations in `PROJECT_MAP.md`:

  1. **Overview paragraph**: `materializes the official evaluation state as \`results/{run_name}/workspace_final/`` → `docker/<image_dir>/results/<run_name>/workspace_final/`.
  2. **Architecture diagram**: the box showing `results/{run_name}/` with children → replace with `docker/<image_dir>/results/<run_name>/`.
  3. **Key Runtime Patterns** section: any references to the old path → update.
  Files: `PROJECT_MAP.md`.

  Testability: `grep -n 'results/{run_name}' PROJECT_MAP.md` should return zero matches.

- [ ] **Update runner specs: **[**BENCHMARK-RUNNER.md**](http://benchmark-runner.md/)**, **[**RUN-ARTIFACTS-AND-TELEMETRY.md**](http://run-artifacts-and-telemetry.md/)**, **[**WORKSPACE-CONTRACT.md**](http://workspace-contract.md/)**, **[**AGENT-CONTAINERS.md**](http://agent-containers.md/)
  Detail: Four spec files with the same find-and-replace pattern. All `results/{run_name}/` → `docker/<image_dir>/results/<run_name>/`. Specific locations per file:

  **`docs/specs/BENCHMARK-RUNNER.md`** (6+ locations):

  - Result Harvesting section prose.
  - Output Artifacts section: full tree diagram, run name description (change `{image_name}_{ISO-timestamp}` to `<set_code>-<timestamp>` with example `sos-2026-05-13T01-30`), cross-run tree (update to per-image layout).
  - Decisions section: "Preserve official evaluation Workspace" bullet, "Evaluation reads from workspace_final/" bullet (2 refs).
  **`docs/specs/RUN-ARTIFACTS-AND-TELEMETRY.md`** (4+ locations):

  - Official evaluation Workspace: `workspace_final/` path.
  - Snapshot repo: `snapshots/` path.
  - Snapshot telemetry: `snapshot_telemetry.jsonl` path.
  - Docker logs: `docker_stdout.log` and `docker_stderr.log` paths.
  **`docs/specs/WORKSPACE-CONTRACT.md`** (2 locations):

  - Opening paragraph.
  - Decisions section: "Workspace is evaluatable state" bullet.
  **`docs/specs/AGENT-CONTAINERS.md`** (3+ locations):

  - Runner-Owned Snapshots section (2 refs).
  - Legacy per-card artifacts ref: `results/{run_name}/cards/{card_id}/` → update.
  - Container Lifecycle implementation sketch: update path comment.
  Files: `docs/specs/BENCHMARK-RUNNER.md`, `docs/specs/RUN-ARTIFACTS-AND-TELEMETRY.md`, `docs/specs/WORKSPACE-CONTRACT.md`, `docs/specs/AGENT-CONTAINERS.md`.

  Testability: `grep -rn 'results/{run_name}' docs/specs/BENCHMARK-RUNNER.md docs/specs/RUN-ARTIFACTS-AND-TELEMETRY.md docs/specs/WORKSPACE-CONTRACT.md docs/specs/AGENT-CONTAINERS.md` should return zero matches.

- [ ] **Update ****`docs/specs/TEST-SUITE.md`**** — results path and stale ****`engine_work/`**** reference**
  Detail: Two fixes:

  1. **Artifacts Per Card section**: `results/{run_name}/cards/{card_id}/` → `docker/<image_dir>/results/<run_name>/cards/{card_id}/`.
  2. **Evaluation Phase section**: the line referencing `agent's \`engine_work/`` is stale — agents edit `/workspace/engine/` in place (no `engine_work/`). Replace with `workspace_final/engine/` or similar per the current spec.
  Files: `docs/specs/TEST-SUITE.md`.

  Testability: `grep -n 'results/{run_name}\|engine_work' docs/specs/TEST-SUITE.md` should return zero matches.

- [ ] **Update ****`docs/adrs/ADR-005*.md`****, ****`docs/HELP.md`****, and ****`docs/specs/KNOWN-ISSUES.md`**
  Detail: Three small doc files:

  1. **`docs/adrs/ADR-005*.md`** — Decision section: `materialized as \`results/{run_name}/workspace_final/`` → `docker/<image_dir>/results/<run_name>/workspace_final/`.
  2. **`docs/HELP.md`** — Upload results example: `git add -f benchmarks/sos/results/gemma4_2026-05-12T01-59/` → `git add -f docker/local-pi-blind/results/sos-2026-05-12T01-59/`.
  3. **`docs/specs/KNOWN-ISSUES.md`** — Issue #3 references `benchmarks/sos/results/` and `benchmarks/sos/results/gemma4_2026-05-12/`. These are historical. Add a parenthetical note: "(Legacy path; results now stored under `docker/<image_dir>/results/`)".
  Files: The ADR-005 file (check exact filename via `ls docs/adrs/`), `docs/HELP.md`, `docs/specs/KNOWN-ISSUES.md`.

  Testability: Verify no unqualified `results/{run_name}` or `benchmarks/sos/results/` references remain in these files.

- [ ] **Update ****`benchmarks/`**** directory summaries**
  Detail: Two files:

  1. **`benchmarks/DIRECTORY_SUMMARY.md`**: The convention paragraph lists `results/ (benchmark outputs)`. Remove `results/` from the convention and add a note that results are now stored under `docker/<image_dir>/results/`.
  2. **`benchmarks/sos/DIRECTORY_SUMMARY.md`**: The subdirectories table has a `results/` row. Remove this row or mark it as deprecated with a note pointing to the new location.
  Files: `benchmarks/DIRECTORY_SUMMARY.md`, `benchmarks/sos/DIRECTORY_SUMMARY.md`.

  Testability: Visual review — no `results/` subdirectory should be listed as active convention.

- [ ] **Add test artifact cleanup and update **[**TESTING-CONVENTIONS.md**](http://testing-conventions.md/)
  Detail: Two changes to ensure tests leave no persistent artifacts:

  1. **`tests/test_smoke_lifecycle.py`**: The `test_smoke_container_lifecycle` test builds `silverquillm-smoke-test:lifecycle` but does not clean it up. Refactor to use a PID-tagged image name (`f"silverquillm-smoke-test:{os.getpid()}"`) to avoid parallel collisions, and wrap in a `try/finally` that runs `subprocess.run(["docker", "rmi", "-f", image_tag], capture_output=True, timeout=30)` in the `finally` block. Alternatively, create a pytest fixture:
    ```python
@pytest.fixture()
def smoke_image(tmp_path):
    image_tag = f"silverquillm-smoke-test:{os.getpid()}"
    # ... build logic ...
    yield image_tag
    subprocess.run(["docker", "rmi", "-f", image_tag], capture_output=True, timeout=30)
    ```

  2. **`docs/specs/TESTING-CONVENTIONS.md`**: Add a new rule (Rule 8 or append to existing rules): "Tests must not leave persistent artifacts (result directories, Docker images, temp files outside `tmp_path`). Integration tests that build Docker images must clean up those images in a `finally` block or fixture teardown." Also add to the Checklist: `- [ ] No Docker images left after test (integration tests clean up via fixture/finally)`.
  3. **Verify existing harvest tests**: Confirm `TestHarvest` and `TestCardStatus` in `tests/test_cli_docker.py` still use `tmp_path` for results dirs after the path changes — they must never use the real `_image_results_dir()` default. Inspect and fix if needed.
  Files: `tests/test_smoke_lifecycle.py`, `docs/specs/TESTING-CONVENTIONS.md`, `tests/test_cli_docker.py` (verification only).

  Testability: Run `docker images | grep silverquillm-smoke-test` before and after `pytest -m integration tests/test_smoke_lifecycle.py` — image should not persist after test.

- [ ] **Remove stale ****`results/`**** and ****`benchmarks/*/results/`**** directories**
  Detail: Final cleanup step. If the repo-root `results/` directory exists (even if gitignored), remove it. If any `benchmarks/<set_code>/results/` directories exist, remove them. Then verify no stale references remain:

  ```bash
# Check for stale path references in code and docs
grep -rn 'results/{run_name}' --include='*.py' --include='*.md' .
grep -rn 'benchmarks/.*/results/' --include='*.py' --include='*.md' .
# Both should return zero matches (except KNOWN-ISSUES.md historical note)
  ```

  If either grep finds unexpected matches, fix them before committing.

  Files: Filesystem cleanup + verification grep.

  Testability: Verify `results/` and `benchmarks/sos/results/` do not exist. Run the full test suite to confirm nothing depends on the old paths.
