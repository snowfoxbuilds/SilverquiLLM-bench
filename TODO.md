# TODO

## Phase 11: Runner Polish, Output Channels

Scope: (1) Add card subset filter to CLI. (2) Runner container lifecycle — pipe-readers + poll-loop architecture, multi-channel output, dual timeouts (hard + hang). (3) Smoke test automation.

Reference: [AGENT-CONTAINERS.md](http://agent-containers.md/) for container architecture, [BENCHMARK-RUNNER.md](http://benchmark-runner.md/) for runner spec, [CONTEXT.md](http://context.md/) for vocabulary.

Prerequisite: Phase 9 PR #12 must be merged first (or these items applied on top of that branch).

Canonical implementation constraints for this TODO:

- Current specs and ADRs override stale code patterns in the repository. Do not copy old `engine_work/`, adapter, per-card harness, or `config.yaml` behavior forward.
- Agents edit `/workspace/engine/` in place. There is no `/workspace/engine_work/`.
- The runner writes `/workspace/run_manifest.json` immediately before `docker run` with only `timeout_seconds` and `deadline_utc`.
- The official evaluated output is `results/{run_name}/workspace_final/`, containing the full selected Workspace.
- `/output/` is telemetry-only. It may contain optional `progress.jsonl`, `system.log`, `agent_stdout.log`, `agent_stderr.log`, and `exit_code`, but evaluation must not depend on any `/output/` file.
- The runner captures Docker stdout/stderr at the host level, streams them live, and saves them as `docker_stdout.log` and `docker_stderr.log`.
---

- [ ] **Remove ****`--cards-dir`**** and ****`--engine-dir`**** CLI flags; hardcode repo-relative paths**
  Detail: These flags are unnecessary — cards and engine directories are static repo-relative paths. The settled decision ([BENCHMARK-RUNNER.md](http://benchmark-runner.md/)) states: "Cards and engine source directories are repo-relative constants (`./cards`, `./engine`); they are not configurable via CLI flags."

  Current state:

  - `cli.py` `run` command has `--cards-dir` (default `./cards`) and `--engine-dir` (default `./engine`) Click options. Both are passed to `stage_workspace(cards_dir, engine_dir, ...)`.
  - `workspace.py` `stage_workspace()` takes `cards_dir: Path` and `engine_dir: Path` as parameters.
  Changes:

  1. In `silverquillm/cli.py`:
    - Remove `--cards-dir` and `--engine-dir` Click options from the `run` command.
    - Remove the `cards_dir` and `engine_dir` parameters from `run()`.
    - Pass `_REPO_ROOT / "cards"` and `_REPO_ROOT / "engine"` directly to `stage_workspace()`.
    - Update `_harvest_results()` to use `_REPO_ROOT / "cards"` instead of the `cards_dir` parameter. Remove the `cards_dir` parameter from `_harvest_results()` and `_write_card_statuses()`.
  2. In `silverquillm/workspace.py`:
    - Add a module-level `_REPO_ROOT` constant (same pattern as `cli.py`: `Path(__file__).resolve().parent.parent`).
    - Replace `cards_dir` and `engine_dir` parameters with hardcoded `_REPO_ROOT / "cards"` and `_REPO_ROOT / "engine"`.
    - Update `stage_workspace()` signature to `stage_workspace(output_dir: Path, *, card_filter: list[str] | None = None)` — the `card_filter` parameter is a no-op stub in this item (implemented in the next item).
    - Update internal helpers (`_copy_engine`, `_copy_reference_docs`, `_stage_cards`) to use the hardcoded paths.
  Files: `silverquillm/cli.py`, `silverquillm/workspace.py`.

  Testability: Existing `tests/test_workspace.py` tests should be updated to match the new `stage_workspace()` signature. Verify staging still produces the correct workspace structure with hardcoded paths.

- [ ] **Add ****`--cards`**** filter to ****`silverquillm run`**
  Detail: Optional flag to stage only a subset of SOS cards for development and debugging. FDN cards are always staged in full (they're reference examples, not benchmark targets). The settled decision ([BENCHMARK-RUNNER.md](http://benchmark-runner.md/)) states: "Filtered runs are not leaderboard-valid."

  CLI signature:

  ```bash
silverquillm run --image <img> --cards 001,042,105 --timeout 3600
  ```

  Changes:

  1. In `silverquillm/cli.py`:
    - Add `--cards` Click option: `@click.option("--cards", default=None, help="Comma-separated SOS collector numbers to stage (default: all)")`. Parse into `list[str] | None` by splitting on commas and stripping whitespace.
    - Pass `card_filter` to `stage_workspace()`.
  2. In `silverquillm/workspace.py`:
    - Implement the `card_filter` parameter in `stage_workspace()` (stubbed in previous item).
    - In `_stage_cards()`, when staging the `sos` tier: if `card_filter` is not `None`, skip card directories whose collector number is not in the filter list. FDN staging is unaffected.
    - Adjust `_PROMPT_TEXT` when `card_filter` is set: replace "Implement all SOS cards" with "Implement the following SOS cards: {comma-separated list}". When `card_filter` is `None`, use the existing full-set prompt.
  3. Metadata recording: `card_filter` will be recorded in `run_summary.json` in a later phase. For now, print the filter to stdout during staging: `click.echo(f"Card filter: {card_filter or 'all'}")`.
  Files: `silverquillm/cli.py`, `silverquillm/workspace.py`.

  Testability: Unit test `stage_workspace()` with `card_filter=["001", "042"]` → verify only those two SOS dirs exist in `workspace/cards/sos/`. Full set when `card_filter=None` → all SOS dirs present. FDN dirs always present regardless of filter. Verify prompt text changes when filter is set.

- [ ] **Write ****`run_manifest.json`**** during workspace staging**
  Detail: The runner writes `/workspace/run_manifest.json` immediately before `docker run` with advisory timeout facts. Per [BENCHMARK-RUNNER.md](http://benchmark-runner.md/): "The Run Manifest is advisory. It is not agent configuration."

  The manifest contains exactly two fields:

  ```json
{
  "timeout_seconds": 7200,
  "deadline_utc": "2026-05-13T22:22:00Z"
}
  ```

  Changes:

  1. In `silverquillm/cli.py` in the `run()` function, after `stage_workspace()` returns and immediately before the `docker run` call:
    - Compute `deadline_utc` as `datetime.now(tz=timezone.utc) + timedelta(seconds=timeout)`.
    - Write `run_manifest.json` to the workspace directory:
    ```python
import json
from datetime import timedelta

manifest = {
    "timeout_seconds": timeout,
    "deadline_utc": (datetime.now(tz=timezone.utc) + timedelta(seconds=timeout)).isoformat(timespec="seconds").replace("+00:00", "Z"),
}
(workspace / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    ```

  2. In `_harvest_results()`, copy `run_manifest.json` from the workspace to the run results directory (alongside other artifacts).
  Files: `silverquillm/cli.py`.

  Testability: After `stage_workspace()` + manifest write, verify `workspace/run_manifest.json` exists and contains valid JSON with `timeout_seconds` (int) and `deadline_utc` (ISO-8601 string). Verify the file is copied to the results directory during harvest.

- [ ] **Update Docker entrypoints: remove ****`engine_work`**** copy, add file-based channel separation**
  Detail: Current entrypoints (`docker/homelab-pi-blind/entrypoint.mjs` and `docker/local-pi-blind/entrypoint.mjs`) copy engine to `/workspace/engine_work` — this is a stale pattern. Per the spec, agents edit `/workspace/engine/` in place. There is no `engine_work`.

  Additionally, entrypoints should separate output into named log files in `/output/` for the runner's multi-channel monitoring. Current entrypoints write only `progress.jsonl` and `exit_code` to `/output/`.

  **Important**: Current Pi entrypoints are JavaScript (`entrypoint.mjs`), not bash. Both JavaScript and bash entrypoints are valid — future agent images may use either language. The channel separation pattern must work in both.

  Changes to both `docker/homelab-pi-blind/entrypoint.mjs` and `docker/local-pi-blind/entrypoint.mjs`:

  1. **Remove ****`engine_work`**** copy**: Delete the `cpSync("/workspace/engine", "/workspace/engine_work", { recursive: true })` line. Update `createAgentSession()` to use `cwd: "/workspace"` (already correct — the agent will edit `/workspace/engine/` in place).
  2. **Add system log**: System/orchestration messages ("Starting entrypoint", "Model found", "Session created", etc.) should be written to `/output/system.log` instead of `console.log()`. Create a helper:
    ```javascript
import { appendFileSync, mkdirSync } from "fs";
mkdirSync("/output", { recursive: true });
function log(msg) {
  const ts = new Date().toISOString().substring(11, 19);
  appendFileSync("/output/system.log", `[${ts}] ${msg}\n`);
}
    ```

  3. **Capture agent stdout/stderr to files**: Pi's `session.subscribe()` already captures text deltas to `process.stdout`. Additionally tee agent output to `/output/agent_stdout.log`. For stderr (thinking/reasoning), subscribe to thinking events if available, or note that Pi in `-p` mode sends thinking to stderr naturally — the runner's pipe readers will capture Docker-level stderr regardless. At minimum, write agent text output to `/output/agent_stdout.log`:
    ```javascript
import { createWriteStream } from "fs";
const agentStdout = createWriteStream("/output/agent_stdout.log", { flags: "a" });
session.subscribe((event) => {
  if (event.type === "message_update" && event.assistantMessageEvent.type === "text_delta") {
    const delta = event.assistantMessageEvent.delta;
    process.stdout.write(delta);
    agentStdout.write(delta);
  }
  // ... progress.jsonl logging unchanged
});
    ```

  4. **SIGTERM trap**: Add a signal handler so `docker stop -t 10` triggers graceful shutdown:
    ```javascript
process.on("SIGTERM", () => {
  log("Received SIGTERM, shutting down");
  appendFileSync("/output/progress.jsonl",
    JSON.stringify({ ts: new Date().toISOString(), status: "timed_out" }) + "\n"
  );
  process.exit(0);
});
    ```

  Reference pattern for future bash entrypoints (e.g., OpenCode, Claude Code):

  ```bash
#!/bin/bash
set -euo pipefail
mkdir -p /output
log() { echo "[$(date -u +%H:%M:%S)] $*" >> /output/system.log; }
trap 'log "SIGTERM received"; echo "{\"ts\":\"$(date -u +%FT%TZ)\",\"status\":\"timed_out\"}" >> /output/progress.jsonl; exit 0' TERM
log "Building prompt"
PROMPT="$(cat /workspace/prompt.md)"
log "Launching agent"
agent_command -p "${PROMPT}" \
  > >(tee /output/agent_stdout.log) \
  2> >(tee /output/agent_stderr.log >&2) &
wait $!
echo $? > /output/exit_code
  ```

  Files: `docker/homelab-pi-blind/entrypoint.mjs`, `docker/local-pi-blind/entrypoint.mjs`.

  Testability: Build the updated image, run smoke test, verify: (a) `/workspace/engine_work/` does NOT exist, (b) `/output/system.log` contains timestamped messages, (c) `/output/agent_stdout.log` contains agent output, (d) `progress.jsonl` still written. Manual verification — this runs against the real model server.

- [ ] **Create ****`silverquillm/runner.py`**** with pipe-readers + poll-loop architecture**
  Detail: New module implementing the `ContainerLifecycle` class — the core container launch, live streaming, dual timeout enforcement, and graceful shutdown logic. This is the settled architecture from [BENCHMARK-RUNNER.md](http://benchmark-runner.md/): "Two dedicated threads drain Docker stdout/stderr pipes to host files. The main thread polls all files on a ~1s interval."

  Create `silverquillm/runner.py` with the following:

  **`ContainerLifecycle`**** class:**

  ```python
import subprocess
import threading
import time
from pathlib import Path
from dataclasses import dataclass

@dataclass
class LifecycleResult:
    exit_code: int | None
    timed_out: bool
    timeout_reason: str | None  # "hard_timeout" | "hang_timeout" | None
    container_name: str

class ContainerLifecycle:
    def __init__(
        self,
        image: str,
        container_name: str,
        workspace: Path,
        output: Path,
        hard_timeout: int,
        hang_timeout: int = 900,
        env_args: list[str] | None = None,
        snapshot_callback: callable | None = None,
    ):
        ...

    def run(self) -> LifecycleResult:
        """Launch container, stream output, enforce timeouts, return result."""
        ...
  ```

  **Pipe readers** — two dedicated threads, trivial, just drain to disk:

  ```python
def _drain_pipe(self, pipe, path: Path) -> None:
    """Drain a subprocess pipe to a file. Runs in a dedicated thread."""
    with open(path, "wb") as f:
        while True:
            chunk = pipe.read(4096)
            if not chunk:
                break
            f.write(chunk)
            f.flush()
  ```

  The pipe readers write to temporary host files: `docker_stdout.tmp` and `docker_stderr.tmp` in the output directory. These are renamed to `docker_stdout.log` and `docker_stderr.log` during harvest.

  **Main loop** — single-threaded poll loop (~1s iterations):

  ```python
def _poll_loop(self, proc: subprocess.Popen) -> LifecycleResult:
    start = time.monotonic()
    last_activity = start
    last_snapshot = start
    file_positions: dict[Path, int] = {}  # track read position per file

    monitored_files = [
        (self._docker_stdout_tmp, "stdout"),   # white
        (self._docker_stderr_tmp, "stderr"),    # gray
        (self.output / "system.log", "system"),  # blue
        (self.output / "progress.jsonl", "progress"),  # green
    ]

    try:
        while proc.poll() is None:
            had_data = self._read_and_print_new_bytes(monitored_files, file_positions)
            if had_data:
                last_activity = time.monotonic()

            now = time.monotonic()
            # Hard Timeout check
            if now - start > self.hard_timeout:
                self._docker_stop()
                return LifecycleResult(..., timeout_reason="hard_timeout")

            # Hang Timeout check
            if now - last_activity > self.hang_timeout:
                self._docker_stop()
                return LifecycleResult(..., timeout_reason="hang_timeout")

            # Snapshot (if callback provided)
            if self.snapshot_callback and now - last_snapshot >= 60:
                self.snapshot_callback()
                last_snapshot = now

            time.sleep(1)
    except KeyboardInterrupt:
        self._docker_stop()
        return LifecycleResult(..., timeout_reason=None)
    finally:
        self._stdout_thread.join(timeout=10)
        self._stderr_thread.join(timeout=10)

    return LifecycleResult(
        exit_code=proc.returncode,
        timed_out=False,
        timeout_reason=None,
        container_name=self.container_name,
    )
  ```

  **`_read_and_print_new_bytes()`** — reads new bytes from each file since last position, prints with color labels:

  - `docker_stdout.tmp` → print in default color (agent output)
  - `docker_stderr.tmp` → print in gray (agent thinking/reasoning)
  - `/output/system.log` → print in blue (entrypoint orchestration)
  - `/output/progress.jsonl` → print in green (structured events)
  Use ANSI escape codes for color. Return `True` if any file had new data.

  **`_docker_stop()`** — calls `subprocess.run(["docker", "stop", "-t", "10", self.container_name], timeout=30, check=False)`. Sends SIGTERM, waits 10s, then SIGKILL if needed.

  **Timeout model** — clock-based via `time.monotonic()`, NOT `proc.wait(timeout)`. Per settled decision: "This decouples timeout from the Popen API and enables future pause/resume."

  **Hang Timeout activity tracking** — resets `last_activity` when ANY monitored file has new bytes. Per settled decision: "The hang clock resets on any file modification across all monitored sources." This includes Docker stdout/stderr pipe dumps AND `/output/` files.

  **Container launch** — `subprocess.Popen` with `stdout=subprocess.PIPE, stderr=subprocess.PIPE`. Container is named `sqm-{run_name}` and run with `--rm`. Example:

  ```python
proc = subprocess.Popen(
    ["docker", "run", "--rm", "--name", self.container_name,
     "--runtime", "runc", "--network=host",
     "-v", f"{self.workspace}:/workspace",
     "-v", f"{self.output}:/output",
     *self.env_args,
     self.image],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
  ```

  Do NOT use `--stop-timeout` (the runner owns the timeout, not Docker). Do NOT use `subprocess.run()` (cannot stream or enforce hang timeout).

  Files: `silverquillm/runner.py` (new file).

  Testability: Unit tests with mock `Popen`:

  - Normal exit: mock process exits with code 0 after writing some data → verify `LifecycleResult.exit_code == 0`, `timed_out == False`.
  - Hard timeout: mock process never exits → verify `docker stop` called, `timeout_reason == "hard_timeout"`.
  - Hang timeout: mock process writes data, then goes silent → verify `docker stop` called, `timeout_reason == "hang_timeout"`.
  - KeyboardInterrupt: raise during poll loop → verify `docker stop` called, threads joined.
  - Verify pipe reader threads are started and joined.
- [ ] **Integrate ****`ContainerLifecycle`**** into CLI ****`run`**** and ****`smoke`**** commands; update harvest and add ****`--hang-timeout`**
  Detail: Replace the current `subprocess.run()` + `--stop-timeout` pattern in both `run` and `smoke` commands with the new `ContainerLifecycle` from `runner.py`. Also fix stale harvest logic.

  **`run`**** command changes in ****`silverquillm/cli.py`****:**

  1. Add `--hang-timeout` Click option: `@click.option("--hang-timeout", default=900, type=int, help="Hang timeout in seconds (default: 900)")`. Pass to `ContainerLifecycle`.
  2. Replace the `subprocess.run()` call + `TimeoutExpired` handling with:
    ```python
from silverquillm.runner import ContainerLifecycle

container_name = f"sqm-{run_name}"
lifecycle = ContainerLifecycle(
    image=image,
    container_name=container_name,
    workspace=workspace,
    output=output,
    hard_timeout=timeout,
    hang_timeout=hang_timeout,
    env_args=_api_key_env_args(),
)
result = lifecycle.run()

if result.timeout_reason:
    click.echo(f"Container stopped: {result.timeout_reason}", err=True)
elif result.exit_code != 0:
    click.echo(f"Container exited with code {result.exit_code}", err=True)
    ```

  3. Remove the `--stop-timeout` Docker flag usage.
  4. Remove the backup `timeout=timeout + 60` pattern.
  **Harvest changes in ****`_harvest_results()`****:**

  1. **Remove ****`engine_work`**** reference**: The current code diffs `engine_orig` vs `engine_work`. Replace with diffing `_REPO_ROOT / "engine"` (host baseline) vs `workspace / "engine"` (container-modified). The agent edits `/workspace/engine/` in place.
  2. **Update log file names**: Replace copying `stdout.log`/`stderr.log` with copying `docker_stdout.log`/`docker_stderr.log` (from the pipe reader output files in the output directory). Also copy any `/output/*.log` and `/output/*.jsonl` files.
  3. **Materialize ****`workspace_final/`**: After harvest, copy the entire workspace to `results/{run_name}/workspace_final/`. This is the official evaluation Workspace per spec. Use `shutil.copytree()` with `ignore=shutil.ignore_patterns("__pycache__", "*.pyc")`.
  4. **Copy ****`run_manifest.json`**: Copy from `workspace_final/run_manifest.json` to `results/{run_name}/run_manifest.json`.
  5. **Record ****`timeout_reason`**: Accept `timeout_reason: str | None` parameter. Will be included in `run_summary.json` in a future phase. For now, print it.
  6. **Remove ****`cards_dir`**** parameter** (already done in item 1, but verify consistency).
  **`smoke`**** command changes:**

  1. Replace `subprocess.run()` with `ContainerLifecycle` using a short hard timeout (120s) and hang timeout (60s).
  2. Remove `--stop-timeout` Docker flag.
  3. Use consistent container naming: `sqm-smoke-{pid}`.
  Files: `silverquillm/cli.py`.

  Testability: Existing `tests/test_cli_docker.py` tests should be updated to reflect the new `ContainerLifecycle` integration. Mock `ContainerLifecycle.run()` to return various `LifecycleResult` values and verify CLI behavior (exit codes, error messages). Test harvest produces `workspace_final/`, `docker_stdout.log`, `docker_stderr.log`, and `run_manifest.json` in the results directory.

- [ ] **Add pytest ****`integration`**** marker, ****`pytest-timeout`****, and alpine smoke pipeline test**
  Detail: Set up test infrastructure for Docker-dependent integration tests, then add a `test_smoke_container_lifecycle` that validates the smoke pipeline end-to-end using a minimal alpine image.

  **Infrastructure changes:**

  1. In `pyproject.toml`:
    - Add `pytest-timeout` to `[project.optional-dependencies] dev`: `"pytest-timeout"`.
    - Add markers to `[tool.pytest.ini_options]`: `markers = ["integration: requires Docker daemon"]`.
    - Add default timeout: `timeout = 300` (5 minutes, prevents hung tests).
  2. Default `pytest` runs skip integration tests. Run integration tests explicitly: `pytest -m integration`.
  **Alpine smoke pipeline test:**

  Create `tests/test_smoke_lifecycle.py`:

  ```python
import pytest
import subprocess
from pathlib import Path

@pytest.mark.integration
@pytest.mark.timeout(120)
def test_smoke_container_lifecycle(tmp_path: Path) -> None:
    """Smoke test pipeline with minimal alpine container (no real agent).

    This is a smoke-test-for-the-smoke-test: it validates that the
    silverquillm smoke pipeline (staging → launch → harvest → exit)
    works end-to-end using a trivial Docker image. It does NOT test
    real agent images — those are validated manually via
    `silverquillm smoke --image <img>`.
    """
    # Build a trivial image that writes expected /output/ files and exits
    dockerfile = tmp_path / "Dockerfile"
    entrypoint = tmp_path / "entrypoint.sh"
    dockerfile.write_text(
        "FROM alpine:latest\n"
        "COPY entrypoint.sh /entrypoint.sh\n"
        "RUN chmod +x /entrypoint.sh\n"
        'ENTRYPOINT ["/entrypoint.sh"]\n'
    )
    entrypoint.write_text(
        '#!/bin/sh\n'
        'echo "[00:00:01] Starting" >> /output/system.log\n'
        'echo "hello from agent" > /workspace/hello.py\n'
        'echo 0 > /output/exit_code\n'
    )
    image = "silverquillm-smoke-test:lifecycle"
    build = subprocess.run(
        ["docker", "build", "-t", image, str(tmp_path)],
        capture_output=True, timeout=60,
    )
    assert build.returncode == 0, build.stderr.decode()

    # Run smoke via CLI
    result = subprocess.run(
        ["silverquillm", "smoke", "--image", image],
        capture_output=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert "PASS" in result.stdout.decode()
  ```

  This test:

  - Builds a disposable alpine image with a trivial entrypoint
  - Runs the actual `silverquillm smoke` CLI command against it
  - Verifies the pipeline completes successfully
  - Runs anywhere with Docker installed — no model server needed
  - Skipped in normal `pytest` runs (needs `-m integration`)
  Real agent image smoke testing (e.g., Pi against the local model server at `192.168.86.22:8080`) remains a manual `silverquillm smoke --image <img>` workflow and is NOT part of the test suite.

  Files: `tests/test_smoke_lifecycle.py` (new), `pyproject.toml`.

  Testability: `pytest -m integration tests/test_smoke_lifecycle.py` passes on any machine with Docker installed.
