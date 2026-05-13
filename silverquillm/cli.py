"""CLI entry point for the SilverquiLLM benchmark runner.

Provides commands:
- ``benchmark run`` — launch a full benchmark run in a Docker container
- ``benchmark smoke`` — quick smoke test to verify a Docker image works
- ``benchmark logs`` — colorized interleaved log viewer for completed runs

Entry point registered in pyproject.toml: ``benchmark = "silverquillm.cli:main"``
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import re as _re

import click

from silverquillm.card_loader import is_template, load_all_card_specs
from silverquillm.workspace import stage_workspace

__all__ = ["main"]


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------


def _redact_cmd(cmd: list[str]) -> str:
    """Join *cmd* into a string, masking values of ``-e KEY=…`` arguments."""
    parts: list[str] = []
    redact_next = False
    for token in cmd:
        if redact_next:
            # token is "KEY=value" – keep KEY, mask value
            if "=" in token:
                key, _, _val = token.partition("=")
                parts.append(f"{key}=***")
            else:
                parts.append(token)
            redact_next = False
        elif token == "-e":
            parts.append(token)
            redact_next = True
        else:
            parts.append(token)
    return " ".join(parts)

# ---------------------------------------------------------------------------
# Repo root detection
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# API key passthrough
# ---------------------------------------------------------------------------

_API_KEY_ENV_VARS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENROUTER_API_KEY",
)


def _api_key_env_args() -> list[str]:
    """Return ``-e KEY=VALUE`` docker args for any set API keys."""
    args: list[str] = []
    for key in _API_KEY_ENV_VARS:
        value = os.environ.get(key)
        if value:
            args.extend(["-e", f"{key}={value}"])
    return args


# ---------------------------------------------------------------------------
# Run-name generation
# ---------------------------------------------------------------------------


def _make_run_name(image: str) -> str:
    """Generate a run name from image short name + ISO timestamp."""
    # Extract short name: last component, strip tag
    short = image.rsplit("/", 1)[-1].split(":")[0]
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H-%M")
    return f"{short}_{ts}"


# ---------------------------------------------------------------------------
# Harvest helpers
# ---------------------------------------------------------------------------


def _harvest_results(
    workspace: Path,
    output: Path,
    results_dir: Path,
    run_name: str,
    cards_dir: Path,
    timed_out: bool = False,
) -> Path:
    """Copy artifacts from workspace/output into results/{run_name}/.

    Returns the run results directory path.
    """
    run_dir = results_dir / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    # Per-card artifacts
    sos_dir = workspace / "cards" / "sos"
    cards_out = run_dir / "cards"
    cards_out.mkdir(parents=True, exist_ok=True)

    specs = load_all_card_specs(cards_dir, "sos")

    for spec in specs:
        cn = spec["collector_number"]
        card_workspace_dir = sos_dir / cn

        if not card_workspace_dir.exists():
            continue

        card_results = cards_out / cn
        card_results.mkdir(parents=True, exist_ok=True)

        # card_impl.py
        impl_src = card_workspace_dir / "card_impl.py"
        if impl_src.exists():
            shutil.copy2(impl_src, card_results / "card_impl.py")

        # tests.py (optional)
        tests_src = card_workspace_dir / "tests.py"
        if tests_src.exists():
            shutil.copy2(tests_src, card_results / "tests.py")

    # Engine diff
    engine_orig = workspace / "engine"
    engine_work = workspace / "engine_work"
    if engine_work.exists() and engine_orig.exists():
        try:
            diff_result = subprocess.run(
                ["diff", "-ruN", str(engine_orig), str(engine_work)],
                capture_output=True,
                text=True,
            )
            if diff_result.stdout.strip():
                (run_dir / "engine_diff.patch").write_text(
                    diff_result.stdout, encoding="utf-8"
                )
        except FileNotFoundError:
            pass  # diff not available

    # Output files — copy all .log files and known structured files
    for src in sorted(output.iterdir()):
        if src.is_file() and (
            src.suffix == ".log"
            or src.name in ("progress.jsonl", "exit_code")
        ):
            shutil.copy2(src, run_dir / src.name)

    # Per-card status
    _write_card_statuses(cards_dir, workspace, run_dir, timed_out)

    return run_dir


def _write_card_statuses(
    cards_dir: Path,
    workspace: Path,
    run_dir: Path,
    timed_out: bool,
) -> None:
    """Determine per-card status and write status.json."""
    import json

    specs = load_all_card_specs(cards_dir, "sos")
    statuses: dict[str, str] = {}

    for spec in specs:
        cn = spec["collector_number"]
        # Compare workspace card_impl.py against the original template
        original = cards_dir / "sos" / cn / "card_impl.py"
        workspace_impl = workspace / "cards" / "sos" / cn / "card_impl.py"

        if not workspace_impl.exists():
            statuses[cn] = "timeout" if timed_out else "no_output"
        elif original.exists() and workspace_impl.read_text() == original.read_text():
            statuses[cn] = "timeout" if timed_out else "no_output"
        else:
            statuses[cn] = "completed"

    (run_dir / "status.json").write_text(
        json.dumps(statuses, indent=2) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Stub functions for modules that don't exist yet
# ---------------------------------------------------------------------------


def _evaluate_results(run_dir: Path) -> None:
    """Stub for silverquillm.evaluator.evaluate() — TODO Item 8."""
    click.echo("TODO: evaluate results (Item 8)")


def _generate_run_summary(
    run_dir: Path,
    *,
    card_filter: list[str] | None = None,
) -> None:
    """Write (or update) run_summary.json with run metadata.

    Currently records ``card_filter``; further fields added by TODO Item 9.
    """
    import json

    summary_path = run_dir / "run_summary.json"

    # Load existing summary if present (future items may pre-populate)
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        summary = {}

    meta = summary.setdefault("run_metadata", {})
    meta["card_filter"] = card_filter

    summary_path.write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Container lifecycle helpers
# ---------------------------------------------------------------------------


def _stop_container(container_name: str) -> None:
    """Send ``docker stop -t 10`` to gracefully stop a running container.

    ``-t 10`` gives the entrypoint 10 seconds after SIGTERM to flush
    progress events before Docker escalates to SIGKILL.
    Errors are swallowed — the container may already have exited.
    """
    try:
        subprocess.run(
            ["docker", "stop", "-t", "10", container_name],
            capture_output=True,
            timeout=30,
        )
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Click CLI
# ---------------------------------------------------------------------------


@click.group()
def main() -> None:
    """SilverquiLLM Benchmark Runner."""


@main.command()
@click.option("--image", required=True, help="Docker image name")
@click.option(
    "--cards-dir",
    default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Cards directory (default: cards/ relative to repo root)",
)
@click.option(
    "--engine-dir",
    default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Engine directory (default: engine/ relative to repo root)",
)
@click.option(
    "--timeout",
    default=3600,
    type=int,
    help="Timeout in seconds for Docker container (default: 3600)",
)
@click.option(
    "--results-dir",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Results output directory (default: results/ relative to repo root)",
)
@click.option(
    "--cards",
    "card_numbers",
    default=None,
    type=str,
    help="Comma-separated SOS collector numbers to stage (default: all)",
)
def run(
    image: str,
    cards_dir: Path | None,
    engine_dir: Path | None,
    timeout: int,
    results_dir: Path | None,
    card_numbers: str | None,
) -> None:
    """Run the full benchmark workload in a Docker container."""
    # Resolve defaults relative to repo root
    if cards_dir is None:
        cards_dir = _REPO_ROOT / "cards"
    if engine_dir is None:
        engine_dir = _REPO_ROOT / "engine"
    if results_dir is None:
        results_dir = _REPO_ROOT / "results"

    # Parse --cards filter
    card_filter: list[str] | None = None
    if card_numbers is not None:
        card_filter = [c.strip() for c in card_numbers.split(",") if c.strip()]

    run_name = _make_run_name(image)
    click.echo(f"Starting run: {run_name}")
    click.echo(f"Image: {image}")
    click.echo(f"Timeout: {timeout}s")
    if card_filter is not None:
        click.echo(f"Card filter: {', '.join(card_filter)}")

    # Stage workspace with all cards
    staging_dir = Path(tempfile.mkdtemp(prefix="silverquillm_run_"))
    try:
        workspace, output = stage_workspace(
            cards_dir, engine_dir, staging_dir, card_filter=card_filter,
        )
        click.echo(f"Workspace staged at: {workspace}")

        # Build docker command
        container_name = f"silverquillm-{run_name}"
        cmd = [
            "docker", "run", "--rm",
            "--runtime", "runc",
            "--name", container_name,
            "--network=host", # allow access to localhost APIs
            "-v", f"{workspace}:/workspace",
            "-v", f"{output}:/output",
        ]
        cmd.extend(_api_key_env_args())
        cmd.extend(["--stop-timeout", str(timeout)])
        cmd.append(image)

        click.echo(f"Running: {_redact_cmd(cmd)}")

        # Run container, block until exit.
        # On timeout or Ctrl+C we explicitly ``docker stop -t 10`` so the
        # entrypoint SIGTERM trap fires (writes ``timed_out`` to
        # progress.jsonl), Docker waits 10 s, then SIGKILL's the container.
        # ``--rm`` ensures the container is cleaned up after stop.
        timed_out = False
        proc = subprocess.Popen(cmd)
        try:
            proc.wait(timeout=timeout)
            if proc.returncode != 0:
                click.echo(
                    f"Container exited with code {proc.returncode}", err=True
                )
        except subprocess.TimeoutExpired:
            click.echo("Container timed out — stopping container", err=True)
            timed_out = True
            _stop_container(container_name)
            proc.wait(timeout=30)
        except KeyboardInterrupt:
            click.echo("\nInterrupted — stopping container gracefully", err=True)
            _stop_container(container_name)
            raise SystemExit(130)

        # Harvest results
        click.echo("Harvesting results...")
        run_dir = _harvest_results(
            workspace, output, results_dir, run_name, cards_dir, timed_out
        )
        click.echo(f"Results saved to: {run_dir}")

        # Evaluate and summarize (stubs)
        _evaluate_results(run_dir)
        _generate_run_summary(run_dir, card_filter=card_filter)

        click.echo(f"Run complete: {run_name}")

    finally:
        # Clean up staging directory
        shutil.rmtree(staging_dir, ignore_errors=True)


@main.command()
@click.option("--image", required=True, help="Docker image name")
@click.option(
    "--cards-dir",
    default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Cards directory (default: cards/ relative to repo root)",
)
@click.option(
    "--engine-dir",
    default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Engine directory (default: engine/ relative to repo root)",
)
def smoke(image: str, cards_dir: Path | None, engine_dir: Path | None) -> None:
    """Quick smoke test to verify a Docker image works."""
    if cards_dir is None:
        cards_dir = _REPO_ROOT / "cards"
    if engine_dir is None:
        engine_dir = _REPO_ROOT / "engine"
    staging_dir = Path(tempfile.mkdtemp(prefix="silverquillm_smoke_"))
    try:
        workspace = staging_dir / "workspace"
        output = staging_dir / "output"
        workspace.mkdir()
        output.mkdir()

        # Write a simple prompt
        (workspace / "prompt.md").write_text(
            "Create hello.py that prints Hello World\n", encoding="utf-8"
        )

        # Create empty engine dir expected by Docker entrypoints
        (workspace / "engine").mkdir()

        # Build docker command
        container_name = f"silverquillm-smoke-{os.getpid()}"
        cmd = [
            "docker", "run", "--rm",
            "--runtime", "runc",
            "--name", container_name,
            "--network=host", # allow access to localhost APIs
            "-v", f"{workspace}:/workspace",
            "-v", f"{output}:/output",
        ]
        cmd.extend(_api_key_env_args())
        cmd.extend(["--stop-timeout", "120"])
        cmd.append(image)

        click.echo(f"Smoke test: {image}")

        # Run with 120s timeout
        proc = subprocess.Popen(cmd)
        try:
            proc.wait(timeout=120)
            exit_zero = proc.returncode == 0
        except subprocess.TimeoutExpired:
            click.echo("FAIL: Container timed out")
            _stop_container(container_name)
            proc.wait(timeout=30)
            raise SystemExit(1)
        except KeyboardInterrupt:
            click.echo("\nInterrupted — stopping container")
            _stop_container(container_name)
            raise SystemExit(1)

        # Check results
        hello_exists = (workspace / "hello.py").exists()

        if exit_zero and hello_exists:
            click.echo("PASS")
        else:
            reasons = []
            if not exit_zero:
                reasons.append(f"exit code {result.returncode}")
            if not hello_exists:
                reasons.append("hello.py not found")
            click.echo(f"FAIL: {', '.join(reasons)}")
            raise SystemExit(1)

    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Log viewer
# ---------------------------------------------------------------------------

# ANSI color codes for log channels
_LOG_COLORS: dict[str, str] = {
    "system": "\033[34m",      # blue
    "agent_stderr": "\033[90m", # gray
    "agent_stdout": "\033[37m", # white
    "progress": "\033[32m",     # green
}
_RESET = "\033[0m"

# Map of log file basenames → channel names
_LOG_CHANNELS: dict[str, str] = {
    "system.log": "system",
    "agent_stderr.log": "agent_stderr",
    "agent_stdout.log": "agent_stdout",
    "progress.jsonl": "progress",
}


def _parse_log_lines(
    run_dir: Path,
) -> list[tuple[str, str, str]]:
    """Parse log files and return sorted (sortkey, channel, line) tuples.

    Lines with ``[HH:MM:SS]`` timestamps sort chronologically.
    Lines without timestamps sort after any timestamped line from the same file,
    preserving file order.
    """
    import json as _json

    entries: list[tuple[str, str, str]] = []

    for fname, channel in _LOG_CHANNELS.items():
        fpath = run_dir / fname
        if not fpath.exists():
            continue

        lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
        last_ts = ""
        for idx, line in enumerate(lines):
            # Try to extract [HH:MM:SS] timestamp
            ts_match = _re.match(r"\[(\d{2}:\d{2}:\d{2})\]", line)
            if ts_match:
                last_ts = ts_match.group(1)
            elif channel == "progress":
                # progress.jsonl lines have "ts" field
                try:
                    obj = _json.loads(line)
                    iso_ts = obj.get("ts", "")
                    if len(iso_ts) >= 19:
                        last_ts = iso_ts[11:19]
                except (ValueError, KeyError):
                    pass

            # Sort key: timestamp then channel priority then line index
            priority = list(_LOG_CHANNELS.values()).index(channel)
            sort_key = f"{last_ts}|{priority:02d}|{idx:08d}"
            entries.append((sort_key, channel, line))

    entries.sort(key=lambda e: e[0])
    return entries


def format_log_lines(
    run_dir: Path,
    *,
    color: bool = True,
) -> list[str]:
    """Return formatted log lines for a run directory.

    Each line is prefixed with a channel tag and optionally ANSI-colored.
    """
    entries = _parse_log_lines(run_dir)
    result: list[str] = []
    for _sort_key, channel, line in entries:
        tag = f"[{channel}]"
        if color:
            c = _LOG_COLORS.get(channel, "")
            result.append(f"{c}{tag} {line}{_RESET}")
        else:
            result.append(f"{tag} {line}")
    return result


@main.command()
@click.option(
    "--run",
    "run_name",
    required=True,
    help="Run name (directory under results/)",
)
@click.option(
    "--results-dir",
    default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Results directory (default: results/ relative to repo root)",
)
@click.option(
    "--no-color",
    is_flag=True,
    default=False,
    help="Disable ANSI colors",
)
def logs(
    run_name: str,
    results_dir: Path | None,
    no_color: bool,
) -> None:
    """View interleaved, colorized logs for a completed run."""
    if results_dir is None:
        results_dir = _REPO_ROOT / "results"

    run_dir = results_dir / run_name
    if not run_dir.is_dir():
        click.echo(f"Run directory not found: {run_dir}", err=True)
        raise SystemExit(1)

    use_color = not no_color
    lines = format_log_lines(run_dir, color=use_color)
    if not lines:
        click.echo("No log files found in run directory.", err=True)
        raise SystemExit(1)

    for line in lines:
        click.echo(line)
