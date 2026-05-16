"""CLI entry point for the SilverquiLLM benchmark runner.

Provides two commands:
- ``benchmark run`` — launch a full benchmark run in a Docker container
- ``benchmark smoke`` — quick smoke test to verify a Docker image works

Entry point registered in pyproject.toml: ``benchmark = "silverquillm.cli:main"``
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
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

    cards_dir = _REPO_ROOT / "cards"
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

    # Output files
    for fname in ("progress.jsonl", "stdout.log", "stderr.log"):
        src = output / fname
        if src.exists():
            shutil.copy2(src, run_dir / fname)

    # Per-card status
    _write_card_statuses(workspace, run_dir, timed_out)

    # Run manifest
    manifest_src = workspace / "run_manifest.json"
    if manifest_src.exists():
        shutil.copy2(manifest_src, run_dir / "run_manifest.json")

    return run_dir


def _write_card_statuses(
    workspace: Path,
    run_dir: Path,
    timed_out: bool,
) -> None:
    """Determine per-card status and write status.json."""
    cards_dir = _REPO_ROOT / "cards"
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


def _generate_run_summary(run_dir: Path) -> None:
    """Stub for silverquillm.results.generate_run_summary() — TODO Item 9."""
    click.echo("TODO: generate run summary (Item 9)")


# ---------------------------------------------------------------------------
# Click CLI
# ---------------------------------------------------------------------------


@click.group()
def main() -> None:
    """SilverquiLLM Benchmark Runner."""


@main.command()
@click.option("--image", required=True, help="Docker image name")
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
    default=None,
    help="Comma-separated SOS collector numbers to stage (default: all)",
)
def run(
    image: str,
    timeout: int,
    results_dir: Path | None,
    cards: str | None,
) -> None:
    """Run the full benchmark workload in a Docker container."""
    # Parse --cards into a list of collector numbers
    card_filter: list[str] | None = None
    if cards is not None:
        card_filter = [
            str(int(c)) if c.isdigit() else c.strip()
            for c in (tok.strip() for tok in cards.split(","))
            if c
        ]
    # Resolve defaults relative to repo root
    if results_dir is None:
        results_dir = _REPO_ROOT / "results"

    run_name = _make_run_name(image)
    click.echo(f"Starting run: {run_name}")
    click.echo(f"Image: {image}")
    click.echo(f"Timeout: {timeout}s")

    # Stage workspace with all cards
    staging_dir = Path(tempfile.mkdtemp(prefix="silverquillm_run_"))
    try:
        workspace, output = stage_workspace(output_dir=staging_dir, card_filter=card_filter)
        click.echo(f"Workspace staged at: {workspace}")

        # Write run manifest (advisory timeout facts)
        manifest = {
            "timeout_seconds": timeout,
            "deadline_utc": (datetime.now(tz=timezone.utc) + timedelta(seconds=timeout)).isoformat(timespec="seconds").replace("+00:00", "Z"),
        }
        (workspace / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

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

        # Run container, block until exit
        timed_out = False
        try:
            result = subprocess.run(
                cmd,
                timeout=timeout + 60,  # backup timeout
            )
            if result.returncode != 0:
                click.echo(
                    f"Container exited with code {result.returncode}", err=True
                )
        except subprocess.TimeoutExpired:
            click.echo("Container timed out (backup timeout reached)", err=True)
            timed_out = True
            # Stop the container so it doesn't keep mutating workspace
            try:
                subprocess.run(
                    ["docker", "stop", container_name],
                    timeout=30,
                )
            except Exception:  # noqa: BLE001
                pass

        # Harvest results
        click.echo("Harvesting results...")
        run_dir = _harvest_results(
            workspace, output, results_dir, run_name, timed_out
        )
        click.echo(f"Results saved to: {run_dir}")

        # Evaluate and summarize (stubs)
        _evaluate_results(run_dir)
        _generate_run_summary(run_dir)

        click.echo(f"Run complete: {run_name}")

    finally:
        # Clean up staging directory
        shutil.rmtree(staging_dir, ignore_errors=True)


@main.command()
@click.option("--image", required=True, help="Docker image name")
def smoke(image: str) -> None:
    """Quick smoke test to verify a Docker image works."""
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
        try:
            result = subprocess.run(cmd, timeout=120)
            exit_zero = result.returncode == 0
        except subprocess.TimeoutExpired:
            click.echo("FAIL: Container timed out")
            try:
                subprocess.run(
                    ["docker", "stop", container_name],
                    timeout=30,
                )
            except Exception:  # noqa: BLE001
                pass
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
