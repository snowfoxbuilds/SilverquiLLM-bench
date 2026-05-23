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

import click

from silverquillm.card_loader import is_template, load_all_card_specs
from silverquillm.runner import ContainerLifecycle
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
# Image helpers
# ---------------------------------------------------------------------------


def _image_dir(image: str) -> str:
    """Strip ``silverquillm-`` prefix and ``:tag`` suffix from Docker image name.

    Examples:
        silverquillm-local-pi-blind:latest → local-pi-blind
        ghcr.io/user/silverquillm-pi-blind:latest → pi-blind
        my-custom-image:v2 → my-custom-image
    """
    short = image.rsplit("/", 1)[-1].split(":")[0]
    if short.startswith("silverquillm-"):
        short = short[len("silverquillm-"):]
    return short


def _image_results_dir(image: str) -> Path:
    """Return the per-image results directory under docker/."""
    return _REPO_ROOT / "docker" / _image_dir(image) / "results"


# ---------------------------------------------------------------------------
# Run-name generation
# ---------------------------------------------------------------------------


def _make_run_name(set_code: str = "sos") -> str:
    """Generate a run name from set code + ISO timestamp.

    Format: ``<set_code>-<YYYY-MM-DDThh-mm>``
    """
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H-%M")
    return f"{set_code}-{ts}"


# ---------------------------------------------------------------------------
# Harvest helpers
# ---------------------------------------------------------------------------


def _harvest_results(
    workspace: Path,
    output: Path,
    results_dir: Path,
    run_name: str,
    timed_out: bool = False,
    timeout_reason: str | None = None,
) -> Path:
    """Copy artifacts from workspace/output into docker/<image_dir>/results/<run_name>/.

    Returns the run results directory path.
    """
    run_dir = results_dir / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    if timeout_reason:
        click.echo(f"Timeout reason: {timeout_reason}")

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

    # Engine diff — compare repo engine against workspace engine
    engine_repo = _REPO_ROOT / "engine"
    engine_ws = workspace / "engine"
    if engine_repo.exists() and engine_ws.exists():
        try:
            diff_result = subprocess.run(
                ["diff", "-ruN", str(engine_repo), str(engine_ws)],
                capture_output=True,
                text=True,
            )
            if diff_result.stdout.strip():
                (run_dir / "engine_diff.patch").write_text(
                    diff_result.stdout, encoding="utf-8"
                )
        except FileNotFoundError:
            pass  # diff not available

    # Output files — copy docker_stdout.log, docker_stderr.log, and any *.log / *.jsonl
    for src in output.iterdir():
        if src.is_file() and (src.suffix in (".log", ".jsonl")):
            shutil.copy2(src, run_dir / src.name)

    # Per-card status
    _write_card_statuses(workspace, run_dir, timed_out)

    # Materialize workspace_final/ snapshot
    workspace_final = run_dir / "workspace_final"
    if workspace.exists():
        shutil.copytree(
            workspace,
            workspace_final,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            dirs_exist_ok=True,
        )

    # Run manifest — copy from workspace_final (snapshot) to results dir
    manifest_src = workspace_final / "run_manifest.json" if workspace_final.exists() else workspace / "run_manifest.json"
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
    help="Results output directory (default: docker/<image_dir>/results/)",
)
@click.option(
    "--cards",
    default=None,
    help="Comma-separated SOS collector numbers to stage (default: all)",
)
@click.option(
    "--hang-timeout",
    default=900,
    type=int,
    help="Hang timeout in seconds (default: 900)",
)
def run(
    image: str,
    timeout: int,
    results_dir: Path | None,
    cards: str | None,
    hang_timeout: int = 900,
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
        results_dir = _image_results_dir(image)

    run_name = _make_run_name()
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

        # Run container via ContainerLifecycle
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

        click.echo(f"Running container: {container_name}")
        result = lifecycle.run()

        if result.timeout_reason:
            click.echo(f"Container timed out ({result.timeout_reason})", err=True)
        elif result.exit_code != 0:
            click.echo(
                f"Container exited with code {result.exit_code}", err=True
            )

        # Harvest results
        click.echo("Harvesting results...")
        run_dir = _harvest_results(
            workspace, output, results_dir, run_name,
            timed_out=result.timed_out,
            timeout_reason=result.timeout_reason,
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

        # Run via ContainerLifecycle
        container_name = f"sqm-smoke-{os.getpid()}"
        lifecycle = ContainerLifecycle(
            image=image,
            container_name=container_name,
            workspace=workspace,
            output=output,
            hard_timeout=120,
            hang_timeout=60,
            env_args=_api_key_env_args(),
        )

        click.echo(f"Smoke test: {image}")
        result = lifecycle.run()

        if result.timeout_reason:
            click.echo("FAIL: Container timed out")
            raise SystemExit(1)

        exit_zero = result.exit_code == 0

        # Check results
        hello_exists = (workspace / "hello.py").exists()

        if exit_zero and hello_exists:
            click.echo("PASS")
        else:
            reasons = []
            if not exit_zero:
                reasons.append(f"exit code {result.exit_code}")
            if not hello_exists:
                reasons.append("hello.py not found")
            click.echo(f"FAIL: {', '.join(reasons)}")
            raise SystemExit(1)

    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)
