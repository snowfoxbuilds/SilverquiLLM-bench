# TODO

## Phase 10: Runner Polish, Output Channels & FDN Migration

Scope: (1) Add card subset filter to CLI. (2) Separate agent output channels for observability. (3) Rework FDN card migration to spec-first approach matching SOS structure.

Reference: [AGENT-CONTAINERS.md](http://agent-containers.md/) for container architecture, [BENCHMARK-RUNNER.md](http://benchmark-runner.md/) for runner spec, [CONTEXT.md](http://context.md/) for vocabulary.

Prerequisite: Phase 9 PR #12 must be merged first (or these items applied on top of that branch).

---

- [x] **Add ****`--cards`**** filter to ****`silverquillm run`**
  Detail: Optional flag to stage only a subset of SOS cards for development and debugging. FDN cards are always staged in full (they're reference examples, not benchmark targets).

  CLI signature:

  ```javascript
silverquillm run --image <img> --cards 001,042,105 --timeout 3600
  ```

  - `--cards` accepts a comma-separated list of collector numbers. If omitted, all SOS cards are staged (current behavior).
  - Only affects which `cards/sos/{num}/` directories are copied into the workspace. FDN cards, engine, prompt, and reference docs are unaffected.
  - `workspace.py`'s `stage_workspace()` gains an optional `card_filter: list[str] | None` parameter. When set, only matching SOS collector numbers are staged.
  - `prompt.md` is adjusted to reference the subset: "Implement the following SOS cards..." with the list, instead of "Implement all SOS cards."
  - Evaluation still runs against only the staged cards (the evaluator already skips cards with status `no_output`).
  - `run_summary.json` records `card_filter: ["001", "042", "105"]` (or `null` for full set) in `run_metadata`.
  - Also add to `smoke`: `silverquillm smoke --image <img>` is unchanged (smoke doesn't use real cards).
  - Default values for `--cards-dir` and `--engine-dir`: `./cards` and `./engine` respectively (repo-relative). Add these defaults to both `run` and `smoke`.
  Files: `silverquillm/cli.py`, `silverquillm/workspace.py`.

  Testability: Stage workspace with `card_filter=["001", "042"]` → verify only those two SOS dirs exist in workspace. Full set when `card_filter=None`. Run summary includes filter metadata.

- [x] **Implement multi-channel output capture from agent containers**
  Detail: Currently the entrypoint captures two streams: `stdout` → `/output/stdout.log`, `stderr` → `/output/stderr.log`. This conflates agent reasoning, agent tool output, system messages, and entrypoint orchestration into two undifferentiated logs. We need structured separation for post-run analysis and live monitoring.

  **Available Docker channels:**

  - `stdout` / `stderr` — the two standard streams. Docker captures both via `docker logs`. The entrypoint already tees them to files.
  - `/output/` volume — mounted read-write. The entrypoint and agent can write arbitrary files here. This is the primary mechanism for structured output beyond stdout/stderr.
  - `progress.jsonl` — already defined as a structured event stream in `/output/`.
  - Named pipes / FIFOs — could create `/output/agent_thinking.pipe` but adds complexity and agents would need to know about it. Not recommended.
  - Docker logging drivers — can route stdout/stderr to syslog, fluentd, etc. Overkill for our use case.
  **Recommended approach — file-based channel separation in ****`/output/`****:**

  The entrypoint splits output into named log files:

  ```javascript
/output/
  progress.jsonl          — structured events (started, card_started, completed, etc.)
  system.log              — entrypoint orchestration messages (engine copy, prompt build, trap)
  agent_stdout.log        — agent process stdout (tool calls, file writes, shell output)
  agent_stderr.log        — agent process stderr (typically agent thinking/reasoning)
  exit_code               — numeric exit code
  ```

  Entrypoint changes:

  ```bash
# System messages go to system.log (not mixed into agent streams)
log() { echo "[$(date -u +%H:%M:%S)] $*" >> /output/system.log; }
log "Copying engine to engine_work/"
cp -r /workspace/engine /workspace/engine_work
log "Engine copied"
log "Building prompt"
# ... prompt construction ...
log "Launching agent"

# Agent streams captured separately (Pi example — default agent)
pi -p "${PROMPT}" \
  > >(tee /output/agent_stdout.log) \
  2> >(tee /output/agent_stderr.log >&2) &
  ```

  Agent-specific channel behavior (document per-agent):

  - **Pi (****`-p`**** mode)**: stdout = final response (card implementations). stderr = thinking/reasoning tokens. Clean separation.
  - **OpenCode**: stdout = tool call results, file diffs. stderr = status messages, errors. Less clean — reasoning mixed into stdout.
  - **Claude Code**: TBD — investigate `--output-format json` for structured output.
  The runner's harvest step copies all `/output/*.log` files to `results/{run_name}/`. The live monitoring story: `tail -f /output/agent_stderr.log` to watch agent thinking in real-time.

  **Post-run colorized viewer (stretch):**

  A `silverquillm logs --run <run_name>` command that interleaves the log files chronologically with ANSI colors:

  - Blue = system.log (entrypoint)
  - Gray = agent thinking (agent_stderr.log)
  - White = agent output (agent_stdout.log)
  - Green = progress events (progress.jsonl)
  Files: `docker/*/entrypoint.sh`, `silverquillm/cli.py` (harvest + optional `logs` command).

  Testability: Run entrypoint with mock agent → verify system.log has entrypoint messages, agent_stdout.log has agent output, no cross-contamination. Verify harvest copies all log files.

- [x] **Generate FDN card specs and templates via script (spec-first migration)**
  Detail: Instead of migrating implementations directly, use the same spec-first pipeline we used for SOS: generate `card_spec.json` + empty `card_impl.py` templates first, then fill them.

  Step 1 — Script `scripts/generate_fdn_specs.py`:

  - Read `cards/registry.py` to enumerate all registered FDN cards (name, class name, collector number, metadata).
  - For each card, create `cards/fdn/{collector_number}/card_spec.json` from registry metadata (name, mana_cost, type_line, oracle_text, collector_number, complexity_tier). Same schema as SOS card specs.
  - For each card, create `cards/fdn/{collector_number}/card_impl.py` as an empty template (class skeleton subclassing CardImpl, with `pass` methods). Same template format as SOS.
  - SPG cards → `cards/fdn/spg_{collector_number}/` per KEY_DECISIONS.
  - Collision suffixes (`105b`, `61b`) per KEY_DECISIONS.
  - Output: `cards/fdn/` directory tree with 260+ subdirectories, each containing `card_spec.json` + empty `card_impl.py`.
  Step 2 — Verify specs match existing implementations:

  - `pytest tests/audited/fdn/ -x --limit=5` still passes (audited tests should be unaffected since they import from `card_impl`, not from registry paths).
  - Spot-check: compare generated `card_spec.json` fields against Scryfall data for 10 random cards.
  Files: `scripts/generate_fdn_specs.py`, output in `cards/fdn/`.

  Testability: Script runs without errors. `cards/fdn/` has one subdirectory per registered FDN card. Each has `card_spec.json` (valid JSON, required fields present) + `card_impl.py` (empty template, correct class name).

- [x] **Migrate FDN card implementations into per-card templates**
  Detail: Assumes the `cards/fdn/{num}/card_spec.json` files and empty `card_impl.py` templates have already been generated before this TODO is run. Fill those per-card templates with implementations, using `cards/foundations/*.py` only as source material.

  **Important migration rule:**

  - `cards/fdn/{num}/card_spec.json` is the source of truth. Existing `cards/foundations/*.py` code is source material, not authoritative.
  - If class names, collector numbers, oracle text, or behavior disagree, prefer the new `cards/fdn` spec and port only the reusable parts that match.
  - If no trustworthy old implementation exists for the spec, implement the card from scratch.
  - A large number of broken tests is expected while registry/test mappings are corrected.
  This is an agent task (not a script) because each monolithic file contains multiple card classes with shared imports, helper functions, and cross-references. The agent needs to:

  1. For each FDN card in `cards/fdn/{num}/card_impl.py` (currently an empty template):
    - Find the existing implementation in `cards/foundations/*.py` (match by class name from `card_spec.json`).
    - Copy the class definition + its required imports into the template.
    - Resolve shared helpers: if the class uses a helper function defined in the same monolithic file, inline it or move it to a shared utils module (`cards/fdn/utils.py`).
  2. Update `cards/registry.py` to import from `cards/fdn/{num}/card_impl.py` instead of `cards/foundations/*.py`.
  3. Verify each migrated card: `python -c "from cards.fdn.{num}.card_impl import {ClassName}"` succeeds.
  4. Run full test suite: `pytest --ignore=tests/audited/sos/ -x` passes.
  Do NOT delete `cards/foundations/` yet — that's the next item.

  Files: `cards/fdn/*/card_impl.py`, `cards/registry.py`, optionally `cards/fdn/utils.py`.

  Testability: All 260+ `card_impl.py` files are non-empty (not templates). Registry imports resolve. All non-SOS tests pass. No references to `cards.foundations` in `registry.py`.

- [x] **Fix container timeout: explicit ****`docker stop`**** on timeout**
  Detail: The current spec assumes `subprocess.run(timeout=N)` and Docker's `--stop-timeout` will kill the container. Neither works:

  - `subprocess.run(timeout=N)` kills the local `docker run` CLI process but leaves the container running headless in the background.
  - `--stop-timeout` only controls the SIGTERM→SIGKILL grace period when you explicitly call `docker stop`. It does not auto-stop after N seconds.
  Fix: Use `Popen` + `wait(timeout)` + explicit `docker stop` on timeout:

  ```python
container_name = f"sqm-{run_name}"
proc = subprocess.Popen(
    ["docker", "run", "--rm", "--name", container_name,
     "-v", f"{workspace}:/workspace", "-v", f"{output}:/output",
     *env_args, image],
)
try:
    proc.wait(timeout=timeout)
except subprocess.TimeoutExpired:
    subprocess.run(["docker", "stop", "-t", "10", container_name],
                   capture_output=True)
    proc.wait(timeout=30)
  ```

  Key points:

  - `--name` gives the runner a handle to the container for `docker stop`.
  - `docker stop -t 10` sends SIGTERM (entrypoint trap fires, writes `timed_out` to progress.jsonl), waits 10s, then SIGKILL.
  - `--rm` ensures container is cleaned up after stop.
  - `Popen` + `wait(timeout)` instead of `subprocess.run(timeout)` gives control to stop the container before the CLI process dies.
  - Also handle `KeyboardInterrupt` (Ctrl+C) the same way — stop the container gracefully.
  Update [BENCHMARK-RUNNER.md](http://benchmark-runner.md/) spec to document the correct timeout mechanism.

  Files: `silverquillm/cli.py`, docs/specs/[BENCHMARK-RUNNER.md](http://benchmark-runner.md/).

  Testability: Mock `subprocess.Popen` → simulate timeout → verify `docker stop` is called with correct container name. Verify progress.jsonl harvest still works after stop.

- [x] **Add real smoke test to test suite (integration test with local model)**
  Detail: The current `silverquillm smoke` command is a manual CLI tool. Add an automated integration test that runs the full smoke test pipeline against the local llama.cpp model server.

  The local model server is always available at `192.168.86.22` (home server running llama.cpp with OpenAI-compatible API).

  Test: `tests/test_smoke_integration.py`:

  ```python
import pytest
import subprocess

@pytest.mark.integration
@pytest.mark.timeout(300)  # 5 min max
def test_smoke_pi_blind(tmp_path):
    """Full smoke test: build Pi blind image, run against local model."""
    image = "silverquillm-pi-blind:test"
    # Build image
    result = subprocess.run(
        ["docker", "build", "-t", image, "docker/pi-blind/"],
        capture_output=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr.decode()
    # Run smoke
    result = subprocess.run(
        ["silverquillm", "smoke", "--image", image],
        capture_output=True, timeout=180,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert "PASS" in result.stdout.decode()
  ```

  Model server config:

  - Host: `192.168.86.22` (always on, home server)
  - Port: `8080` (llama.cpp default)
  - API: OpenAI-compatible (`/v1/chat/completions`)
  - Provider in Pi's models.json: `"api": "openai-completions"`, `"baseUrl": "http://192.168.86.22:8080/v1"`
  - Docker networking: `--network=host` not needed since we're using LAN IP (not [localhost](http://localhost/))
  Pytest markers:

  - `@pytest.mark.integration` — skip in normal `pytest` runs, only run with `pytest -m integration`
  - Add to `pyproject.toml`: `markers = ["integration: requires Docker + local model server"]`
  - CI note: integration tests only run on self-hosted runner with model server access. Not in GitHub Actions.
  Also add a lighter `test_smoke_container_lifecycle` that uses a minimal `alpine` image with a bash script (no real agent) to verify the runner's staging → launch → harvest → timeout pipeline without needing a model server.

  Files: `tests/test_smoke_integration.py`, `pyproject.toml` (markers).

  Testability: `pytest -m integration tests/test_smoke_integration.py` passes on a machine with Docker and model server at 192.168.86.22. The lightweight lifecycle test passes anywhere with Docker.

- [ ] **Delete ****`cards/foundations/`****, remove FDN compat shims, fix tests**
  Detail: Final cleanup after migration is verified.

  Steps:

  1. Delete `cards/foundations/` entirely (the 21 monolithic files + `__init__.py` + `DIRECTORY_SUMMARY.md`).
  2. Delete any backward-compat shims (e.g., `cards/foundations/{module}/__init__.py` re-exports created by PR #12).
  3. `grep -rn "cards.foundations" --include="*.py"` → update or delete every remaining reference.
  4. Update `tests/conftest.py` and any test fixtures that import from `cards.foundations`.
  5. Update `cards/__init__.py` if it re-exports from `foundations`.
  6. Run `pytest --ignore=tests/audited/sos/ -x` → must pass with zero import errors.
  7. Run `pytest tests/audited/fdn/ -x --limit=10` → spot-check audited tests work with new paths.
  8. Update `PROJECT_MAP.md` to show `cards/fdn/` instead of `cards/foundations/`.
  Files: delete `cards/foundations/`, update `tests/`, `cards/__init__.py`, `PROJECT_MAP.md`.

  Testability: `cards/foundations/` does not exist. `grep -rn "cards.foundations"` finds zero hits. Full non-SOS test suite passes. FDN audited tests pass.
