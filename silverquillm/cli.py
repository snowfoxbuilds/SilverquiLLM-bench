"""CLI entry point for the SilverquiLLM benchmark runner.

Provides two commands:
- ``benchmark run`` — launch a full benchmark run in a Docker container
- ``benchmark smoke`` — quick smoke test to verify a Docker image works

Entry point registered in pyproject.toml: ``benchmark = "silverquillm.cli:main"``
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Load .env from repo root into os.environ (values already in the environment take precedence)
_ENV_FILE = Path(__file__).parent.parent / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

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
    "COPILOT_GITHUB_TOKEN",
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


def _make_run_name(
    set_code: str,
    image: str = "default",
    results_dir: Path = _REPO_ROOT / "docker" / "default" / "results",
) -> str:
    """Generate a run name from set + image + ISO timestamp.

    Format: ``<set_code>-<image_dir>-<YYYY-MM-DDThh-mm>``.
    If that directory already exists under *results_dir*, a short hex
    nonce is appended to disambiguate (``-<4 hex chars>``).
    """
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H-%M")
    base = f"{set_code}-{_image_dir(image)}-{ts}"

    candidate = base
    while (results_dir / candidate).exists():
        candidate = f"{base}-{secrets.token_hex(2)}"
    return candidate


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
    card_filter: list[str] | None = None,
) -> Path:
    """Copy artifacts from workspace/output into docker/<image_dir>/results/<run_name>/.

    Parameters
    ----------
    card_filter:
        When set, only harvest cards whose collector numbers (normalized via
        ``str(int(x))``) are in this list. When ``None``, harvest all cards.

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

    # Normalize filter for comparison
    filter_set: set[str] | None = None
    if card_filter is not None:
        filter_set = {str(int(c)) if c.isdigit() else c for c in card_filter}

    for spec in specs:
        cn = spec["collector_number"]  # directory name
        json_cn = spec.get("json_collector_number", cn)
        normalized_cn = str(int(json_cn)) if json_cn.isdigit() else json_cn

        # Skip cards not in the filter (match on json collector_number or dir_name)
        if filter_set is not None and normalized_cn not in filter_set and cn not in filter_set:
            continue

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
    _write_card_statuses(workspace, run_dir, timed_out, card_filter=filter_set)

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
    card_filter: set[str] | None = None,
) -> None:
    """Determine per-card status and write status.json.

    Parameters
    ----------
    card_filter:
        When set, only include cards whose normalized collector numbers are in
        this set. When ``None``, include all cards from the set.
    """
    cards_dir = _REPO_ROOT / "cards"
    specs = load_all_card_specs(cards_dir, "sos")
    statuses: dict[str, str] = {}

    for spec in specs:
        cn = spec["collector_number"]  # directory name
        json_cn = spec.get("json_collector_number", cn)
        normalized_cn = str(int(json_cn)) if json_cn.isdigit() else json_cn

        # Skip cards not in the filter (match on json collector_number or dir_name)
        if card_filter is not None:
            matched_by_dir = cn in card_filter
            matched_by_cn = normalized_cn in card_filter
            if not matched_by_dir and not matched_by_cn:
                continue
            # When matched only by numeric collector_number (not dir name),
            # skip if workspace dir doesn't exist (avoids duplicates)
            if not matched_by_dir and matched_by_cn:
                workspace_card_dir = workspace / "cards" / "sos" / cn
                if not workspace_card_dir.exists():
                    continue

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


def _evaluate_results(run_dir: Path, card_filter: list[str] | None = None) -> None:
    """Run post-eval scoring on completed cards and write per-card result.json and postmortem.jsonl.

    Parameters
    ----------
    run_dir:
        Path to the run results directory.
    card_filter:
        When set, only evaluate cards in this list. When ``None``, evaluate all
        completed cards.
    """
    from silverquillm.evaluator import evaluate, CardResult
    from dataclasses import asdict

    cards_dir = _REPO_ROOT / "cards"
    engine_dir = _REPO_ROOT / "engine"

    try:
        full_result = evaluate(run_dir, cards_dir, engine_dir)
    except Exception as exc:
        click.echo(f"Evaluation failed: {exc}", err=True)
        return

    # Normalize filter for comparison
    filter_set: set[str] | None = None
    if card_filter is not None:
        filter_set = {str(int(c)) if c.isdigit() else c for c in card_filter}

    # Write per-card result.json and postmortem.jsonl
    cards_out = run_dir / "cards"
    for cn, card_result in full_result.sos_results.items():
        normalized_cn = str(int(cn)) if cn.isdigit() else cn
        if filter_set is not None and normalized_cn not in filter_set:
            continue

        card_dir = cards_out / cn
        card_dir.mkdir(parents=True, exist_ok=True)

        # Write result.json
        result_data = {
            "tests_passed": card_result.tests_passed,
            "tests_failed": card_result.tests_failed,
            "tests_total": card_result.tests_total,
            "pass_rate": card_result.pass_rate,
        }
        (card_dir / "result.json").write_text(
            json.dumps(result_data, indent=2) + "\n", encoding="utf-8"
        )

        # Write postmortem.jsonl
        postmortem_entries = []
        if card_result.errors:
            for error in card_result.errors:
                postmortem_entries.append(json.dumps({
                    "collector_number": cn,
                    "type": "error",
                    "message": error,
                }))
        else:
            postmortem_entries.append(json.dumps({
                "collector_number": cn,
                "type": "summary",
                "tests_passed": card_result.tests_passed,
                "tests_failed": card_result.tests_failed,
                "tests_total": card_result.tests_total,
            }))
        (card_dir / "postmortem.jsonl").write_text(
            "\n".join(postmortem_entries) + "\n", encoding="utf-8"
        )

    # Write eval_result.json at run level
    eval_result_data = {
        "sos_results": {
            cn: {
                "tests_passed": r.tests_passed,
                "tests_failed": r.tests_failed,
                "tests_total": r.tests_total,
            }
            for cn, r in full_result.sos_results.items()
        },
        "fdn_results": {
            cn: {
                "tests_passed": r.tests_passed,
                "tests_failed": r.tests_failed,
                "tests_total": r.tests_total,
            }
            for cn, r in full_result.fdn_results.items()
        },
        "engine_result": {
            "tests_passed": full_result.engine_result.tests_passed,
            "tests_failed": full_result.engine_result.tests_failed,
            "tests_total": full_result.engine_result.tests_total,
        },
    }
    (run_dir / "eval_result.json").write_text(
        json.dumps(eval_result_data, indent=2) + "\n", encoding="utf-8"
    )

    click.echo(f"Evaluation complete: {len(full_result.sos_results)} SOS cards scored")


def _generate_run_summary(
    run_dir: Path,
    image_name: str,
    card_filter: list[str] | None = None,
) -> None:
    """Generate run_summary.json for the completed run.

    Parameters
    ----------
    run_dir:
        Path to the run results directory.
    image_name:
        Docker image name used for the run.
    card_filter:
        When set, included in run_summary.json as the ``card_filter`` field.
    """
    from silverquillm.results import generate_run_summary

    summary = generate_run_summary(run_dir, image_name)

    # Inject card_filter field into the summary
    if card_filter is not None:
        summary["card_filter"] = card_filter
    else:
        summary["card_filter"] = None

    # Re-write the summary with card_filter included
    summary_path = run_dir / "run_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    click.echo(f"Run summary written to: {summary_path}")


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

    run_name = _make_run_name(set_code="sos", image=image, results_dir=results_dir)
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
        run_dir = results_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        lifecycle = ContainerLifecycle(
            image=image,
            container_name=container_name,
            workspace=workspace,
            output=output,
            hard_timeout=timeout,
            hang_timeout=hang_timeout,
            env_args=_api_key_env_args(),
            run_dir=run_dir,
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
            card_filter=card_filter,
        )
        click.echo(f"Results saved to: {run_dir}")

        # Evaluate and summarize
        _evaluate_results(run_dir, card_filter=card_filter)
        _generate_run_summary(run_dir, image_name=image, card_filter=card_filter)

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
