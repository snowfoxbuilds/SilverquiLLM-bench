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
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
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

from silverquillm._bootstrap import ensure_workspace_on_path

# Bootstrap workspace dir on sys.path so `engine` / `cards` / `test_utils`
# resolve in the CLI process and in subprocesses that inherit our env.
ensure_workspace_on_path()

from theozolith_worker import api

from silverquillm.card_loader import load_all_card_specs
from silverquillm.card_names import build_card_name_map
from silverquillm.replay.cli import validate as _replay_validate
from silverquillm.runner import ContainerLifecycle
from silverquillm.token_report import render as render_token_report
from silverquillm.workspace import (
    build_resume_preamble,
    stage_workspace,
    stage_workspace_from_prior_run,
)

__all__ = ["main"]

# TUI display singleton (None until a display layer is wired; patchable for tests)
_display = None


# ---------------------------------------------------------------------------
# Runner log helper
# ---------------------------------------------------------------------------

# Module-level path set by `run`/`smoke` commands so _runner_log can append.
_runner_log_dir: Path | None = None


def _runner_log(msg: str, *, err: bool = False) -> None:
    """Echo *msg* to terminal and append (with ISO-8601 prefix) to runner log files.

    Parameters
    ----------
    msg:
        Message to echo.
    err:
        If True, also write to stderr and to ``runner_errors.log``.
    """
    click.echo(msg, err=err)

    log_dir = _runner_log_dir
    if log_dir is None or not log_dir.exists():
        return

    ts = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    line = f"{ts} {msg}\n"

    with open(log_dir / "runner.log", "a", encoding="utf-8") as f:
        f.write(line)

    if err:
        with open(log_dir / "runner_errors.log", "a", encoding="utf-8") as f:
            f.write(line)


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
    "CLAUDE_CODE_OAUTH_TOKEN",
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


def _rewrite_diff_headers(diff_text: str, old_a: str, old_b: str) -> str:
    """Rewrite absolute paths in unified-diff headers to ``a/<file>`` / ``b/<file>``.

    ``diff -ruN /abs/A /abs/B`` emits headers that embed the absolute
    arg paths, which makes the patch unappliable elsewhere. Rewrite the
    ``diff -ruN``, ``---``, and ``+++`` lines so the resulting patch can
    be applied with ``git apply --directory <target> -p1`` against any
    engine copy.
    """
    old_a = old_a.rstrip("/")
    old_b = old_b.rstrip("/")
    out_lines: list[str] = []
    for line in diff_text.splitlines(keepends=True):
        if line.startswith("diff -ruN "):
            line = line.replace(old_a + "/", "a/").replace(old_b + "/", "b/")
        elif line.startswith("--- ") or line.startswith("+++ "):
            prefix = line[:4]
            rest = line[4:]
            rest = rest.replace(old_a + "/", "a/", 1).replace(old_b + "/", "b/", 1)
            line = prefix + rest
        out_lines.append(line)
    return "".join(out_lines)


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
        _runner_log(f"Timeout reason: {timeout_reason}")

    # Per-card artifacts
    sos_dir = workspace / "cards" / "sos"
    cards_out = run_dir / "cards"
    cards_out.mkdir(parents=True, exist_ok=True)

    cards_dir = _REPO_ROOT / "benchmarks" / "sos" / "workspace" / "cards"
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

    # Engine diff — compare repo engine against workspace engine.
    # Rewrite absolute paths to a/<file> and b/<file> so the patch is portable
    # and can be applied with ``git apply --directory <target> -p1``.
    engine_repo = _REPO_ROOT / "benchmarks" / "sos" / "workspace" / "engine"
    engine_ws = workspace / "engine"
    if engine_repo.exists() and engine_ws.exists():
        try:
            diff_result = subprocess.run(
                ["diff", "-ruN", str(engine_repo), str(engine_ws)],
                capture_output=True,
                text=True,
            )
            if diff_result.stdout.strip():
                patch_text = _rewrite_diff_headers(
                    diff_result.stdout, str(engine_repo), str(engine_ws)
                )
                (run_dir / "engine_diff.patch").write_text(
                    patch_text, encoding="utf-8"
                )
        except FileNotFoundError:
            pass  # diff not available

    # Output files — copy docker_stdout.log, docker_stderr.log, and any *.log / *.jsonl
    # NOTE: docker_stdout.log and docker_stderr.log may already be streamed directly
    # to run_dir by _drain_pipe (see KEY_DECISIONS.md). Skip them if already present.
    _DIRECT_STREAM_FILES = {"docker_stdout.log", "docker_stderr.log"}
    for src in output.iterdir():
        if src.is_file() and (src.suffix in (".log", ".jsonl")):
            if src.name in _DIRECT_STREAM_FILES and (run_dir / src.name).exists():
                continue
            if src.name == "progress.jsonl":
                continue  # progress.jsonl is deprecated; skip it
            dest = run_dir / src.name
            shutil.copy2(src, dest)

    # Per-card status
    _write_card_statuses(workspace, run_dir, timed_out, card_filter=filter_set)

    # Materialize workspace_final/ snapshot. ``benchmarks/`` is excluded as a
    # belt-and-braces guard: a prior crash class was a recursive absolute
    # symlink at ``workspace/benchmarks/sos/workspace`` that an agent created
    # to satisfy the old ``benchmarks.sos.workspace.*`` import prefix. The
    # flat-import refactor removes the motivation, but ignoring the path here
    # makes the harvest robust if the symlink ever reappears for other reasons.
    workspace_final = run_dir / "workspace_final"
    if workspace.exists():
        shutil.copytree(
            workspace,
            workspace_final,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "benchmarks"),
            dirs_exist_ok=True,
        )

    # Run manifest — copy from workspace_final (snapshot) to results dir
    manifest_src = workspace_final / "run_manifest.json" if workspace_final.exists() else workspace / "run_manifest.json"
    if manifest_src.exists():
        shutil.copy2(manifest_src, run_dir / "run_manifest.json")

    return run_dir


def _emit_token_report(run_dir: Path) -> None:
    """Print token usage table to runner log and save it to ``run_dir/tokens.md``.

    Silently skips for agents whose log isn't Claude Code stream-json (Copilot, etc.).
    """
    log_path = run_dir / "agent_stdout.log"
    report = render_token_report(log_path)
    if report is None:
        return
    _runner_log("Token usage:\n" + report)
    try:
        (run_dir / "tokens.md").write_text(report + "\n", encoding="utf-8")
    except OSError as exc:
        _runner_log(f"Failed to write tokens.md: {exc}", err=True)


def _make_snapshot_callback(workspace: Path, run_dir: Path) -> Callable[[], None]:
    """Build the per-snapshot telemetry callback for a container run.

    On each call the callback counts agent-touched files (workspace
    ``card_impl.py`` + ``engine/`` files that differ from the staged baseline,
    via ``git status --porcelain``), appends a telemetry record to
    ``run_dir/snapshot_telemetry.jsonl``, and notifies the TUI ``_display`` if
    one is wired. Shared by the ``run`` and ``resume`` commands.
    """
    state: dict = {"index": 0, "start": time.monotonic()}
    telemetry_path = run_dir / "snapshot_telemetry.jsonl"

    def _snapshot_callback() -> None:
        state["index"] += 1
        idx = state["index"]
        elapsed = time.monotonic() - state["start"]
        # files_changed = workspace card_impl.py + engine/ files differing
        # from the staged baseline. stage_workspace() git-inits + commits
        # the workspace, so `git status --porcelain` reports anything the
        # agent touched (modified-tracked + new untracked). We filter to
        # the two file groups that meaningfully represent agent work.
        try:
            # --untracked-files=all expands untracked directories so each
            # contained file is reported individually (needed to catch a
            # new card_impl.py in a brand-new card dir).
            status = subprocess.run(
                ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=5,
            )
            paths = (
                [p for p in status.stdout.split("\0") if p]
                if status.returncode == 0
                else []
            )
            # Porcelain v1 prefixes each entry with a two-char status + space.
            files_changed = sum(
                1
                for entry in paths
                for path in [entry[3:] if len(entry) > 3 else entry]
                if path.endswith("/card_impl.py") or path.startswith("engine/")
            )
        except (OSError, subprocess.SubprocessError):
            files_changed = 0
        record = {
            "ts": datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds"),
            "snapshot_index": idx,
            "files_changed": files_changed,
            "elapsed_s": round(elapsed, 3),
        }
        with open(telemetry_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        # Notify TUI display if available
        if _display is not None:
            _display.emit_snapshot(idx)

    return _snapshot_callback


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
    cards_dir = _REPO_ROOT / "benchmarks" / "sos" / "workspace" / "cards"
    specs = load_all_card_specs(cards_dir, "sos")
    name_map = build_card_name_map(cards_dir, "sos")
    statuses: dict[str, dict] = {}

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
            status = "timeout" if timed_out else "no_output"
        elif original.exists() and workspace_impl.read_text() == original.read_text():
            status = "timeout" if timed_out else "no_output"
        else:
            status = "completed"

        card_name = name_map.get(cn, spec.get("name", ""))
        statuses[cn] = {"status": status, "card_name": card_name}

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
    from silverquillm.evaluator import evaluate

    cards_dir = _REPO_ROOT / "benchmarks" / "sos" / "workspace" / "cards"
    engine_dir = _REPO_ROOT / "benchmarks" / "sos" / "workspace" / "engine"
    name_map = build_card_name_map(cards_dir, "sos")

    try:
        full_result = evaluate(run_dir, cards_dir, engine_dir)
    except Exception as exc:
        _runner_log(f"Evaluation failed: {exc}", err=True)
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
            "card_id": cn,
            "card_name": name_map.get(cn, ""),
            "tests_passed": card_result.tests_passed,
            "tests_failed": card_result.tests_failed,
            "tests_total": card_result.tests_total,
            "pass_rate": card_result.pass_rate,
            "errors": card_result.errors,
            "skipped": card_result.skipped,
        }
        # Emit the modern per-node schema only when the card actually executed
        # tests. Skipped / pre-pytest-error cards have no nodes; omitting
        # test_nodes routes them through the harvester's legacy path, which
        # still yields a visible rollup (plus a <collection-error> row derived
        # from `errors`). Always-writing an empty test_nodes would instead make
        # the harvester's modern path emit ZERO rows — the card would silently
        # vanish from the harvest.
        if card_result.test_nodes:
            result_data["test_nodes"] = card_result.test_nodes
            result_data["tests_hash"] = card_result.tests_hash
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

    _runner_log(f"Evaluation complete: {len(full_result.sos_results)} SOS cards scored")


def _generate_run_summary(
    run_dir: Path,
    image_name: str,
    card_filter: list[str] | None = None,
    *,
    resumed_from: str | None = None,
    resumed_image_changed: bool | None = None,
    run_status: str | None = None,
    wall_clock_seconds: float | None = None,
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
    resumed_from:
        For Resume Legs, the ``run_name`` of the immediate prior leg.
    resumed_image_changed:
        For Resume Legs, ``True`` if ``--image`` differs from the prior
        leg's ``docker_image``.
    run_status:
        Optional run-level status string (e.g. ``"completed"``,
        ``"hard_timeout"``, ``"hang_timeout"``). Read by resume staging to
        refuse non-viable prior runs.
    wall_clock_seconds:
        Optional wall-clock duration of the run, used by resume's
        ``--timeout`` hint.
    """
    from silverquillm.results import generate_run_summary

    summary = generate_run_summary(
        run_dir,
        image_name,
        resumed_from=resumed_from,
        resumed_image_changed=resumed_image_changed,
        run_status=run_status,
        wall_clock_seconds=wall_clock_seconds,
    )

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

    _runner_log(f"Run summary written to: {summary_path}")


# ---------------------------------------------------------------------------
# Click CLI
# ---------------------------------------------------------------------------


@click.group()
def main() -> None:
    """SilverquiLLM Benchmark Runner."""


# Replay validation lives in its own module; expose it as `benchmark validate`.
main.add_command(_replay_validate)


@main.command()
@click.option(
    "--candidate", "candidate_path", default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help=(
        "A Candidate Bundle directory (exported by `theozolith candidate export`), "
        "or a candidates/<slug>--<hash8>/ directory wrapping one under bundle/. "
        "The only input of a Contract Run: identity is recomputed and verified "
        "from the bundle, its derived image is built through the verified build."
    ),
)
@click.option(
    "--image", default=None,
    help="Legacy entrypoint lineage only (retired by #66): the Docker image to run.",
)
@click.option("--benchmark", "benchmark_id", default=None, help="Benchmark id (e.g. smoke); required with --candidate")
@click.option("--mode", "mode_name", default=None, help="Benchmark Mode (basic|planned; default basic) — --candidate only")
@click.option(
    "--timeout",
    default=3600,
    type=int,
    help="Agent budget in seconds (the harness's hard agent timeout; default: 3600)",
)
@click.option(
    "--results-dir",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Run-artifacts directory (default: runs/<candidate-dir>/ with --candidate, docker/<image_dir>/results/ with --image)",
)
@click.option(
    "--results-repo", default=None, type=click.Path(file_okay=False, path_type=Path),
    help="Results repo to write the RunRecord and vendored candidate into (or $SILVERQUILLM_RESULTS_REPO) — --candidate only",
)
@click.option(
    "--container-user", default=None,
    help="uid:gid to run the container as (default: the image's user) — --candidate only",
)
@click.option(
    "--cards",
    default=None,
    help="Legacy lineage only: comma-separated SOS collector numbers to stage (default: all)",
)
@click.option(
    "--hang-timeout",
    default=None,
    type=int,
    help="Legacy lineage only: hang timeout in seconds (default: 900)",
)
def run(
    candidate_path: Path | None,
    image: str | None,
    benchmark_id: str | None,
    mode_name: str | None,
    timeout: int,
    results_dir: Path | None,
    results_repo: Path | None,
    container_user: str | None,
    cards: str | None,
    hang_timeout: int | None,
) -> None:
    """Run a benchmark: a Candidate Bundle through TheOzolith's Run Contract
    (--candidate), or a legacy image through the entrypoint lineage (--image).

    With --candidate: the bundle is verified and its identity recomputed
    (never trusted from a recorded value), its derived image is built through
    the verified standalone build and launched by image ID with the in-image
    harness as PID 1, the production gate runs over the jobs channel, the
    Output Proposal is applied post-exit, the checkout is graded by the
    Audited Eval, and the run is recorded under the verified identity. Exits 1
    when the run carries a classified failure; the evidence is in the run
    dir's contract_run.json either way.
    """
    if (candidate_path is None) == (image is None):
        raise click.UsageError(
            "pass exactly one of --candidate <bundle> (a Contract Run) or --image "
            "<name> (the legacy entrypoint lineage)"
        )
    if candidate_path is not None:
        for flag, value in (("--cards", cards), ("--hang-timeout", hang_timeout)):
            if value is not None:
                raise click.UsageError(f"{flag} belongs to the legacy --image lineage, not --candidate")
        _run_candidate(
            candidate_path,
            benchmark_id=benchmark_id,
            mode_name=mode_name or "basic",
            timeout=timeout,
            results_dir=results_dir,
            results_repo=results_repo,
            container_user=container_user,
        )
        return
    for flag, value in (
        ("--benchmark", benchmark_id),
        ("--mode", mode_name),
        ("--results-repo", results_repo),
        ("--container-user", container_user),
    ):
        if value is not None:
            raise click.UsageError(f"{flag} belongs to --candidate (the Contract Run), not the legacy --image lineage")
    if hang_timeout is None:
        hang_timeout = 900
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

    # Set up runner log directory early so all messages are captured
    global _runner_log_dir
    _runner_log_dir = results_dir / run_name
    _runner_log_dir.mkdir(parents=True, exist_ok=True)

    _runner_log(f"Starting run: {run_name}")
    _runner_log(f"Image: {image}")
    _runner_log(f"Timeout: {timeout}s")

    # Stage workspace with all cards
    staging_dir = Path(tempfile.mkdtemp(prefix="silverquillm_run_"))
    try:
        workspace, output = stage_workspace(output_dir=staging_dir, card_filter=card_filter)
        _runner_log(f"Workspace staged at: {workspace}")

        # Write run manifest (advisory timeout facts + audit-trail fields).
        # ``docker_image`` is recorded so resume staging can default
        # ``--image`` to the prior leg's value without rereading the
        # post-hoc run_summary.json (see ADR-009).
        manifest = {
            "timeout_seconds": timeout,
            "deadline_utc": (datetime.now(tz=timezone.utc) + timedelta(seconds=timeout)).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "docker_image": image,
            "card_filter": card_filter,
            "benchmark_set": "sos",
        }
        (workspace / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        # Build card name map for terminal display
        card_name_map = build_card_name_map(_REPO_ROOT / "benchmarks" / "sos" / "workspace" / "cards", "sos")

        # Run container via ContainerLifecycle
        container_name = f"sqm-{run_name}"
        run_dir = results_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        # TUI display object — reads module-level _display (None until wired)
        pass  # _display is read from module-level silverquillm.cli._display

        # Build snapshot callback closure
        _snapshot_callback = _make_snapshot_callback(workspace, run_dir)

        lifecycle = ContainerLifecycle(
            image=image,
            container_name=container_name,
            workspace=workspace,
            output=output,
            hard_timeout=timeout,
            hang_timeout=hang_timeout,
            env_args=_api_key_env_args(),
            run_dir=run_dir,
            card_name_map=card_name_map,
            snapshot_callback=_snapshot_callback,
        )

        _runner_log(f"Running container: {container_name}")
        _wall_start = time.monotonic()
        result = lifecycle.run()
        wall_clock_seconds = time.monotonic() - _wall_start

        if result.timeout_reason:
            _runner_log(f"Container timed out ({result.timeout_reason})", err=True)
        elif result.exit_code != 0:
            _runner_log(
                f"Container exited with code {result.exit_code}", err=True
            )

        # Harvest results
        _runner_log("Harvesting results...")
        run_dir = _harvest_results(
            workspace, output, results_dir, run_name,
            timed_out=result.timed_out,
            timeout_reason=result.timeout_reason,
            card_filter=card_filter,
        )
        _runner_log(f"Results saved to: {run_dir}")

        _emit_token_report(run_dir)

        # Evaluate and summarize
        _evaluate_results(run_dir, card_filter=card_filter)
        run_status = result.timeout_reason if result.timed_out else "completed"
        _generate_run_summary(
            run_dir,
            image_name=image,
            card_filter=card_filter,
            run_status=run_status,
            wall_clock_seconds=wall_clock_seconds,
        )

        _runner_log(f"Run complete: {run_name}")

    finally:
        # Clean up staging directory
        shutil.rmtree(staging_dir, ignore_errors=True)
        _runner_log_dir = None  # noqa: F841


@main.command()
@click.option("--image", required=True, help="Docker image name")
def smoke(image: str) -> None:
    """Quick smoke test to verify a Docker image works."""
    global _runner_log_dir
    staging_dir = Path(tempfile.mkdtemp(prefix="silverquillm_smoke_"))
    _runner_log_dir = staging_dir
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

        _runner_log(f"Smoke test: {image}")
        result = lifecycle.run()

        if result.timeout_reason:
            _runner_log("FAIL: Container timed out", err=True)
            raise SystemExit(1)

        exit_zero = result.exit_code == 0

        # Check results
        hello_exists = (workspace / "hello.py").exists()

        token_report = render_token_report(output / "agent_stdout.log")
        if token_report is not None:
            _runner_log("Token usage:\n" + token_report)

        if exit_zero and hello_exists:
            _runner_log("PASS")
        else:
            reasons = []
            if not exit_zero:
                reasons.append(f"exit code {result.exit_code}")
            if not hello_exists:
                reasons.append("hello.py not found")
            _runner_log(f"FAIL: {', '.join(reasons)}", err=True)
            raise SystemExit(1)

    finally:
        _runner_log_dir = None
        shutil.rmtree(staging_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# `run --candidate` (Contract Run driver)
# ---------------------------------------------------------------------------


def _report_contract_run(result) -> None:
    """Echo a Contract Run's outcome (every classified failure included)."""
    for warning in result.warnings:
        _runner_log(warning, err=True)
    if result.bundle is not None:
        bundle = result.bundle
        _runner_log(
            f"Candidate: {bundle.worker_type} ({bundle.adapter}) hash {bundle.candidate_hash}"
            f" [{bundle.hash8}]  base {bundle.base_digest[:19]}…"
            f"  instruction {bundle.instruction_hash[:12]}…"
        )
        if result.vendored is not None:
            state = "written" if result.vendored.written else "already present, re-verified"
            _runner_log(f"Vendored candidate copy: {result.vendored.path} ({state})")
    if result.image is not None:
        _runner_log(f"Image: {result.image.tag} = {result.image.image_id}")
    agent = result.agent_outcome.describe() if result.agent_outcome is not None else "n/a"
    harness = (result.harness_status or {}).get("phase", "n/a")
    gate = " -> ".join(result.gate.steps_run) or "not run"
    if not result.gate.clean:
        gate += " (findings)"
    _runner_log(f"Agent: {agent}  Harness: {harness}  Gate: {gate}")
    _runner_log(f"Proposal status: {result.proposal_status}")
    if result.eval_result is not None:
        _runner_log(
            "Scores — "
            f"card_correctness={result.eval_result.sos_pass_rate:.3f} "
            f"fdn_regression={result.eval_result.fdn_pass_rate:.3f} "
            f"engine_regression={result.eval_result.engine_pass_rate:.3f}"
        )
    else:
        _runner_log("Scores — not evaluated", err=True)
    if result.record_dir is not None:
        _runner_log(f"RunRecord written: {result.record_dir}")
    elif result.record_error:
        _runner_log(f"RunRecord NOT written: {result.record_error}", err=True)
    _runner_log(f"Evidence: {result.run_dir / 'contract_run.json'}")
    for failure in result.failures:
        _runner_log(
            f"FAILED [{failure.failure_class}] at {failure.phase}: {failure.reason}", err=True
        )
    _runner_log(f"Contract run {'complete' if result.ok else 'FAILED'}: {result.run_id}")


def _run_candidate(
    candidate_path: Path,
    *,
    benchmark_id: str | None,
    mode_name: str,
    timeout: int,
    results_dir: Path | None,
    results_repo: Path | None,
    container_user: str | None,
) -> None:
    """Drive a Candidate Bundle through TheOzolith's implementer Run Contract
    (the body of ``silverquillm run --candidate``)."""
    from silverquillm.contract import (
        RUNS_DIRNAME,
        candidate_label,
        drive_contract_run,
        new_run_name,
    )
    from silverquillm.jobdir import BenchmarkNotRunnableError, load_benchmark
    from silverquillm.modes import UnknownModeError, get_mode
    from silverquillm.results_repo import resolve_results_repo

    global _runner_log_dir
    if benchmark_id is None:
        raise click.UsageError("--benchmark is required with --candidate (e.g. --benchmark smoke)")
    try:
        benchmark = load_benchmark(benchmark_id)
        mode = get_mode(mode_name)
    except (BenchmarkNotRunnableError, UnknownModeError) as exc:
        raise click.ClickException(str(exc)) from exc

    label = candidate_label(candidate_path)
    if results_dir is None:
        results_dir = _REPO_ROOT / RUNS_DIRNAME / label
    run_name = new_run_name(benchmark.id, label, results_dir)
    run_dir = results_dir / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    _runner_log_dir = run_dir

    repo = resolve_results_repo(results_repo)

    _runner_log(f"Starting contract run: {run_name}")
    _runner_log(
        f"Candidate: {candidate_path}  Benchmark: {benchmark.id}  Mode: {mode.name}"
        f"  Timeout: {timeout}s"
    )
    try:
        result = drive_contract_run(
            run_dir=run_dir,
            run_id=run_name,
            benchmark=benchmark,
            mode=mode,
            budget_seconds=timeout,
            candidate=candidate_path,
            session_factory=api.container_session_factory(api.DockerEngine()),
            results_repo=repo,
            container_user=container_user,
        )
        _report_contract_run(result)
    finally:
        _runner_log_dir = None
    if not result.ok:
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# logs command
# ---------------------------------------------------------------------------


def _find_run_dir(run_name: str) -> Path | None:
    """Find a run directory by name under docker/*/results/."""
    docker_dir = _REPO_ROOT / "docker"
    if not docker_dir.exists():
        return None
    for image_dir in docker_dir.iterdir():
        if not image_dir.is_dir():
            continue
        results_dir = image_dir / "results"
        if results_dir.exists():
            candidate = results_dir / run_name
            if candidate.is_dir():
                return candidate
    return None


# ---------------------------------------------------------------------------
# Resume helpers
# ---------------------------------------------------------------------------


def _resolve_prior_run(arg: str) -> Path:
    """Resolve a `resume`/`chain` positional arg to a prior run directory.

    Accepts either a full filesystem path or a bare `run-id`.

    - If *arg* contains ``/`` or resolves as an existing directory, it is
      used directly.
    - Otherwise globs ``docker/*/results/<arg>/`` and requires a unique
      match. Zero matches and 2+ matches both raise loud errors (the
      latter hints at passing a full path to disambiguate).
    """
    p = Path(arg)
    if "/" in arg or p.is_absolute():
        if not p.is_dir():
            raise click.ClickException(f"Prior run directory not found: {p}")
        return p.resolve()

    if p.exists() and p.is_dir():
        return p.resolve()

    docker_dir = _REPO_ROOT / "docker"
    matches: list[Path] = []
    if docker_dir.exists():
        for image_dir in docker_dir.iterdir():
            if not image_dir.is_dir():
                continue
            candidate = image_dir / "results" / arg
            if candidate.is_dir():
                matches.append(candidate.resolve())

    if not matches:
        raise click.ClickException(
            f"No prior run found matching '{arg}' under docker/*/results/"
        )
    if len(matches) > 1:
        joined = "\n  ".join(str(m) for m in matches)
        raise click.ClickException(
            f"Ambiguous prior run id '{arg}' matched {len(matches)} "
            f"directories — pass a full path to disambiguate:\n  {joined}"
        )
    return matches[0]


def _read_prior_manifest(prior_run_dir: Path) -> dict:
    """Read and parse the prior run's ``run_manifest.json``.

    A missing manifest means the entire run dir is treated as corrupted
    (per BENCHMARK-RUNNER.md → Resume / ADR-009).
    """
    manifest_path = prior_run_dir / "run_manifest.json"
    if not manifest_path.is_file():
        raise click.ClickException(
            f"Prior run is corrupted: missing run_manifest.json at "
            f"{manifest_path}. Resume cannot proceed."
        )
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise click.ClickException(
            f"Prior run is corrupted: cannot read {manifest_path}: {exc}"
        ) from None


def _read_prior_summary(prior_run_dir: Path) -> dict | None:
    """Read prior ``run_summary.json``; return None if missing/unreadable."""
    path = prior_run_dir / "run_summary.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _detect_prior_snapshot_fallback(
    prior_run_dir: Path,
) -> tuple[bool, str | None]:
    """Detect whether the prior run used snapshot fallback by inspecting
    the snapshot ledger, NOT ``run_summary.json``.

    The ledger is written during the run and survives harvester failure,
    so it is the canonical source per ADR-009. Returns
    ``(used_fallback, snapshot_utc_or_None)``.

    Detection heuristic (forward-compatible with the snapshot fallback
    feature, which is not yet implemented in the runner): look for a
    sentinel file ``snapshots/fallback_selected.json`` that the snapshot
    fallback code is expected to write when it selects a fallback. The
    sentinel records ``{"snapshot_commit": ..., "snapshot_utc": ...}``.

    If no ledger exists at all, the prior run did not use snapshot
    fallback (since the ledger would have been written by the snapshot
    system if any snapshots ran). Return ``(False, None)``.
    """
    ledger_dir = prior_run_dir / "snapshots"
    if not ledger_dir.is_dir():
        return False, None
    sentinel = ledger_dir / "fallback_selected.json"
    if not sentinel.is_file():
        return False, None
    try:
        data = json.loads(sentinel.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True, None
    snapshot_utc = data.get("snapshot_utc") if isinstance(data, dict) else None
    return True, snapshot_utc


def _resolve_resume_image(
    prior_run_dir: Path,
    prior_manifest: dict,
    prior_summary: dict | None,
    explicit_image: str | None,
) -> tuple[str, bool]:
    """Pick the image for the new leg and cross-check across sources.

    Read order per ADR-009: ``run_manifest.json.docker_image`` →
    resolved path's ``<image-dir>`` → ``run_summary.json.docker_image``.
    All available sources are cross-checked; mismatch aborts (signals a
    corrupted or hand-edited run dir).

    Returns ``(image, image_changed)``.
    """
    manifest_image = prior_manifest.get("docker_image")
    summary_image = (
        prior_summary.get("docker_image") if isinstance(prior_summary, dict) else None
    )
    # The path component is `<image-dir>` — derived from the original
    # `--image` by stripping `silverquillm-` prefix and `:tag` suffix.
    # Compare against the same derivation of every known image.
    path_image_dir = prior_run_dir.parent.parent.name  # docker/<image-dir>/results/<run>

    def _matches(candidate: str | None) -> bool:
        return candidate is None or _image_dir(candidate) == path_image_dir

    if manifest_image is not None and not _matches(manifest_image):
        raise click.ClickException(
            f"Prior run is corrupted: run_manifest.json docker_image "
            f"'{manifest_image}' (→ '{_image_dir(manifest_image)}') does "
            f"not match results-path image-dir '{path_image_dir}'."
        )
    if summary_image is not None and not _matches(summary_image):
        raise click.ClickException(
            f"Prior run is corrupted: run_summary.json docker_image "
            f"'{summary_image}' (→ '{_image_dir(summary_image)}') does "
            f"not match results-path image-dir '{path_image_dir}'."
        )
    if (
        manifest_image is not None
        and summary_image is not None
        and manifest_image != summary_image
    ):
        raise click.ClickException(
            f"Prior run is corrupted: docker_image disagrees between "
            f"run_manifest.json ('{manifest_image}') and run_summary.json "
            f"('{summary_image}')."
        )

    prior_image = manifest_image or summary_image
    if prior_image is None:
        # Older runs may not record docker_image anywhere; require explicit
        # --image in that case.
        if explicit_image is None:
            raise click.ClickException(
                "Prior run does not record docker_image in run_manifest.json "
                "or run_summary.json. Pass --image explicitly."
            )
        return explicit_image, False

    if explicit_image is None or explicit_image == prior_image:
        return prior_image, False
    return explicit_image, True


def _format_timeout_hint(prior_manifest: dict, prior_summary: dict | None) -> str:
    """Format the --timeout error hint with prior leg's timeout and wall-clock."""
    prior_timeout = prior_manifest.get("timeout_seconds")
    parts: list[str] = []
    if prior_timeout is not None:
        parts.append(f"prior leg's --timeout was {prior_timeout}s")
    if isinstance(prior_summary, dict):
        wc = prior_summary.get("wall_clock_seconds")
        if wc is not None:
            parts.append(f"wall-clock-used was {round(float(wc))}s")
    if not parts:
        return ""
    return " (" + "; ".join(parts) + ")"


def _is_run_active(run_dir: Path) -> bool:
    """Heuristic: a run is active if no run_summary.json exists yet."""
    return not (run_dir / "run_summary.json").exists()


@main.command()
@click.option("--run", "run_name", required=True, help="Run name (e.g. sos-2026-05-23T07-13)")
@click.option("--live", "force_live", is_flag=True, default=False, help="Force live tailing mode")
@click.option("--archived", "force_archived", is_flag=True, default=False, help="Force archived (static) mode")
def logs(run_name: str, force_live: bool, force_archived: bool) -> None:
    """Open tabbed log viewer for a run's per-channel log files."""
    from silverquillm.logs_viewer import run_viewer

    run_dir = _find_run_dir(run_name)
    if run_dir is None:
        # Try as a direct path
        candidate = Path(run_name)
        if candidate.is_dir():
            run_dir = candidate
        else:
            click.echo(f"Run not found: {run_name}", err=True)
            raise SystemExit(1)

    if force_live and force_archived:
        click.echo("Cannot specify both --live and --archived", err=True)
        raise SystemExit(1)

    if force_live:
        live = True
    elif force_archived:
        live = False
    else:
        # Auto-detect
        live = _is_run_active(run_dir)

    run_viewer(run_dir, live=live)


# ---------------------------------------------------------------------------
# resume command
# ---------------------------------------------------------------------------


@main.command()
@click.argument("prior_run_id")
@click.option(
    "--timeout",
    required=False,  # validated manually so we can show the rich hint
    default=None,
    type=int,
    help="Hard Timeout in seconds for the Resume Leg (required).",
)
@click.option(
    "--image",
    default=None,
    help="Docker image; defaults to prior run's docker_image.",
)
@click.option(
    "--cards",
    default=None,
    help="Comma-separated SOS collector numbers (per-leg; no inheritance).",
)
@click.option(
    "--hang-timeout",
    default=900,
    type=int,
    help="Hang timeout in seconds (default: 900).",
)
@click.option(
    "--force-missing-summary",
    is_flag=True,
    default=False,
    help="Allow resume when prior run_summary.json is missing or unreadable.",
)
@click.option(
    "--results-dir",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Override results directory (default: docker/<image_dir>/results/).",
)
def resume(
    prior_run_id: str,
    timeout: int | None,
    image: str | None,
    cards: str | None,
    hang_timeout: int,
    force_missing_summary: bool,
    results_dir: Path | None,
) -> None:
    """Start a Resume Leg from a prior Benchmark Run's workspace_final/.

    Per ADR-008, each Resume Leg is an independent Benchmark Run with its
    own results directory; the prior run dir is never mutated.
    """
    # ---- Resolve prior run + read manifests (per ADR-009 read order) ----
    prior_run_dir = _resolve_prior_run(prior_run_id)
    prior_run_name = prior_run_dir.name
    prior_manifest = _read_prior_manifest(prior_run_dir)
    prior_summary = _read_prior_summary(prior_run_dir)

    if prior_summary is None and not force_missing_summary:
        raise click.ClickException(
            f"Prior run_summary.json is missing or unreadable at "
            f"{prior_run_dir / 'run_summary.json'}. Pass "
            f"--force-missing-summary to resume anyway (the "
            f"no_viable_output_produced refusal check will be skipped)."
        )

    # ---- Validate --timeout, with hint sourced from prior manifest/summary ----
    if timeout is None:
        hint = _format_timeout_hint(prior_manifest, prior_summary)
        raise click.ClickException(
            f"--timeout is required on resume; no inheritance from the prior "
            f"leg{hint}."
        )

    # ---- Refuse-conditions: workspace_final/ missing or no_viable_output_produced ----
    workspace_final = prior_run_dir / "workspace_final"
    if not workspace_final.is_dir():
        raise click.ClickException(
            f"Prior run is unresumable: workspace_final/ missing at "
            f"{workspace_final}."
        )
    if isinstance(prior_summary, dict):
        prior_status = prior_summary.get("run_status")
        if prior_status == "no_viable_output_produced":
            raise click.ClickException(
                "Prior run is unresumable: run_status is "
                "'no_viable_output_produced'. A future --from-snapshots "
                "opt-in may allow recovery via the latest viable snapshot."
            )

    # ---- Resolve image (with cross-check) ----
    chosen_image, image_changed = _resolve_resume_image(
        prior_run_dir, prior_manifest, prior_summary, image
    )

    # ---- Parse --cards into per-leg filter (no inheritance) ----
    card_filter: list[str] | None = None
    if cards is not None:
        card_filter = [
            str(int(c)) if c.isdigit() else c.strip()
            for c in (tok.strip() for tok in cards.split(","))
            if c
        ]
    prior_card_filter = prior_manifest.get("card_filter")
    if not isinstance(prior_card_filter, list):
        prior_card_filter = None
    filter_mismatch = card_filter != prior_card_filter

    # ---- Snapshot fallback disclosure (read from ledger per ADR-009) ----
    used_fallback, snapshot_utc = _detect_prior_snapshot_fallback(prior_run_dir)

    # ---- Resolve target results dir (under new image's <image-dir>) ----
    if results_dir is None:
        results_dir = _image_results_dir(chosen_image)
    run_name = _make_run_name(set_code="sos", image=chosen_image, results_dir=results_dir)

    global _runner_log_dir
    _runner_log_dir = results_dir / run_name
    _runner_log_dir.mkdir(parents=True, exist_ok=True)

    _runner_log(f"Starting Resume Leg: {run_name}")
    _runner_log(f"Resuming from:       {prior_run_name}")
    _runner_log(f"Image:               {chosen_image}")
    if image_changed:
        prior_image_str = (
            prior_manifest.get("docker_image")
            or (prior_summary.get("docker_image") if isinstance(prior_summary, dict) else None)
        )
        prior_status = (
            prior_summary.get("run_status")
            if isinstance(prior_summary, dict)
            else None
        )
        prior_wc = (
            prior_summary.get("wall_clock_seconds")
            if isinstance(prior_summary, dict)
            else None
        )
        breadcrumbs = (
            f"prior_image={prior_image_str!r} "
            f"prior_run_status={prior_status!r} "
            f"prior_wall_clock={prior_wc!r}"
        )
        _runner_log(
            f"WARNING: cross-image resume — prior leg used a different image "
            f"({prior_image_str} → {chosen_image}). {breadcrumbs}",
            err=True,
        )
    _runner_log(f"Timeout:             {timeout}s")

    # ---- Stage workspace from prior run's workspace_final ----
    staging_dir = Path(tempfile.mkdtemp(prefix="silverquillm_resume_"))
    try:
        # Build the new prompt: Resume Preamble + canonical User Prompt body.
        # The User Prompt body is read from the prior run's prompt.md so that
        # filter-mismatch disclosures, etc., are based on the same prompt the
        # prior agent saw (resilient to changes in the canonical workspace
        # template between legs).
        prior_prompt = (workspace_final / "prompt.md").read_text(encoding="utf-8")
        # Strip any prior Resume Preamble (legs of legs) so the new preamble
        # is the only one and points at the immediate prior leg.
        body = _strip_resume_preamble(prior_prompt)

        preamble = build_resume_preamble(
            prior_run_id=prior_run_name,
            snapshot_fallback_used=used_fallback,
            snapshot_utc=snapshot_utc,
            image_changed=image_changed,
            prior_image=(
                prior_manifest.get("docker_image")
                or (prior_summary.get("docker_image") if isinstance(prior_summary, dict) else None)
            ),
            new_image=chosen_image,
            filter_mismatch=filter_mismatch,
            prior_card_filter=prior_card_filter,
            new_card_filter=card_filter,
            missing_summary=(prior_summary is None),
        )
        prompt_text = preamble + "\n---\n\n" + body.lstrip()

        manifest = {
            "timeout_seconds": timeout,
            "deadline_utc": (
                datetime.now(tz=timezone.utc) + timedelta(seconds=timeout)
            ).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "docker_image": chosen_image,
            "card_filter": card_filter,
            "benchmark_set": "sos",
            "resumed_from": prior_run_name,
        }

        workspace, output = stage_workspace_from_prior_run(
            output_dir=staging_dir,
            prior_run_dir=prior_run_dir,
            prompt_text=prompt_text,
            run_manifest=manifest,
        )
        _runner_log(f"Workspace staged at: {workspace}")

        card_name_map = build_card_name_map(
            _REPO_ROOT / "benchmarks" / "sos" / "workspace" / "cards", "sos"
        )

        container_name = f"sqm-{run_name}"
        run_dir = results_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        _snapshot_callback = _make_snapshot_callback(workspace, run_dir)

        lifecycle = ContainerLifecycle(
            image=chosen_image,
            container_name=container_name,
            workspace=workspace,
            output=output,
            hard_timeout=timeout,
            hang_timeout=hang_timeout,
            env_args=_api_key_env_args(),
            run_dir=run_dir,
            card_name_map=card_name_map,
            snapshot_callback=_snapshot_callback,
        )

        _runner_log(f"Running container: {container_name}")
        _wall_start = time.monotonic()
        result = lifecycle.run()
        wall_clock_seconds = time.monotonic() - _wall_start

        if result.timeout_reason:
            _runner_log(
                f"Container timed out ({result.timeout_reason})", err=True
            )
        elif result.exit_code != 0:
            _runner_log(
                f"Container exited with code {result.exit_code}", err=True
            )

        _runner_log("Harvesting results...")
        run_dir = _harvest_results(
            workspace,
            output,
            results_dir,
            run_name,
            timed_out=result.timed_out,
            timeout_reason=result.timeout_reason,
            card_filter=card_filter,
        )
        _runner_log(f"Results saved to: {run_dir}")

        _emit_token_report(run_dir)

        _evaluate_results(run_dir, card_filter=card_filter)
        run_status = result.timeout_reason if result.timed_out else "completed"
        _generate_run_summary(
            run_dir,
            image_name=chosen_image,
            card_filter=card_filter,
            resumed_from=prior_run_name,
            resumed_image_changed=image_changed,
            run_status=run_status,
            wall_clock_seconds=wall_clock_seconds,
        )

        _runner_log(f"Resume Leg complete: {run_name}")

    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)
        _runner_log_dir = None  # noqa: F841


def _strip_resume_preamble(prompt_text: str) -> str:
    """Strip a Resume Preamble (if present) from the top of a prior prompt.md.

    The preamble starts with ``## Resume context`` and ends at the first
    ``---`` separator line; everything after that line is the original
    User Prompt body.
    """
    lines = prompt_text.splitlines(keepends=True)
    if not lines or not lines[0].lstrip().startswith("## Resume context"):
        return prompt_text
    for i, line in enumerate(lines):
        if line.strip() == "---":
            return "".join(lines[i + 1 :])
    # Malformed preamble — return original to avoid silent data loss.
    return prompt_text


# ---------------------------------------------------------------------------
# chain command
# ---------------------------------------------------------------------------


@main.command()
@click.argument("run_id")
def chain(run_id: str) -> None:
    """Print the Resume Chain ending at <run_id>, oldest leg first.

    Walks ``resumed_from`` links via repeated lookup. Cycle detection
    aborts loudly (defensive against future bugs writing circular
    ``resumed_from``). Per BENCHMARK-RUNNER.md → Resume Chain reader,
    v1 walks ancestry only; per-leg ``git log`` rendering and
    forward-walking descendants are out of scope.
    """
    leg_dir = _resolve_prior_run(run_id)

    legs: list[dict] = []
    seen: set[str] = set()
    current: Path | None = leg_dir

    while current is not None:
        name = current.name
        if name in seen:
            raise click.ClickException(
                f"Resume Chain cycle detected at '{name}'."
            )
        seen.add(name)

        manifest = _read_prior_manifest(current)
        summary = _read_prior_summary(current)

        wall_clock = (
            summary.get("wall_clock_seconds")
            if isinstance(summary, dict)
            else None
        )
        leg_info = {
            "run_name": name,
            "docker_image": manifest.get("docker_image")
            or (summary.get("docker_image") if isinstance(summary, dict) else None),
            "timeout_seconds": manifest.get("timeout_seconds"),
            "wall_clock_seconds": wall_clock,
            "run_status": (
                summary.get("run_status") if isinstance(summary, dict) else None
            ),
            "resumed_from": (
                manifest.get("resumed_from")
                or (
                    summary.get("resumed_from")
                    if isinstance(summary, dict)
                    else None
                )
            ),
        }
        legs.append(leg_info)

        parent_name = leg_info["resumed_from"]
        if not parent_name:
            current = None
        else:
            current = _resolve_prior_run(parent_name)

    # Oldest first.
    legs.reverse()

    # ---- Render table ----
    headers = ("run_name", "docker_image", "timeout", "wall_clock", "run_status", "resumed_from")
    rows: list[tuple[str, ...]] = []
    for leg in legs:
        rows.append((
            str(leg["run_name"]),
            str(leg["docker_image"] or ""),
            f"{leg['timeout_seconds']}s" if leg["timeout_seconds"] is not None else "",
            (
                f"{round(float(leg['wall_clock_seconds']))}s"
                if leg["wall_clock_seconds"] is not None
                else ""
            ),
            str(leg["run_status"] or ""),
            str(leg["resumed_from"] or ""),
        ))

    widths = [
        max(len(headers[i]), *(len(r[i]) for r in rows)) for i in range(len(headers))
    ]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    click.echo(fmt.format(*headers))
    click.echo(fmt.format(*("-" * w for w in widths)))
    for r in rows:
        click.echo(fmt.format(*r))


@main.command()
@click.argument("run_id")
@click.option(
    "--cards",
    default=None,
    help="Comma-separated collector numbers to rescore (default: all completed).",
)
def rescore(run_id: str, cards: str | None) -> None:
    """Re-run audited tests against an existing run and rewrite its scores.

    RUN_ID may be a bare run name (e.g. sos-copilot-claude-opus-4.6-2026-05-25T22-52)
    or a full path to the run directory. Rewrites eval_result.json,
    per-card cards/<cn>/result.json + postmortem.jsonl, and run_summary.json
    in place. The agent's workspace_final/engine and cards/ are reused —
    nothing is re-executed inside Docker.
    """
    run_dir = _resolve_prior_run(run_id)
    if not run_dir.is_dir():
        raise click.ClickException(f"Run directory not found: {run_dir}")

    manifest = _read_prior_manifest(run_dir)
    image_name = manifest.get("docker_image", "")

    card_filter: list[str] | None = None
    if cards:
        card_filter = [c.strip() for c in cards.split(",") if c.strip()]

    prior_summary = _read_prior_summary(run_dir)
    run_status = None
    wall_clock_seconds: float | None = None
    if prior_summary:
        run_status = prior_summary.get("run_status")
        wcs = prior_summary.get("wall_clock_seconds")
        if isinstance(wcs, (int, float)):
            wall_clock_seconds = float(wcs)

    _evaluate_results(run_dir, card_filter=card_filter)
    _generate_run_summary(
        run_dir,
        image_name,
        card_filter=card_filter,
        run_status=run_status,
        wall_clock_seconds=wall_clock_seconds,
    )


# ---------------------------------------------------------------------------
# Batch queue: scheduler / queue ls / top (#39 §5, #66)
# ---------------------------------------------------------------------------

_BATCHES_DIR_OPTION = click.option(
    "--batches-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="The batch queue directory (default: batches/ in this repo)",
)


def _batches_dir(value: Path | None) -> Path:
    from silverquillm.scheduler import BATCHES_DIRNAME

    return value if value is not None else _REPO_ROOT / BATCHES_DIRNAME


@main.command()
@_BATCHES_DIR_OPTION
@click.option("--once", is_flag=True, default=False, help="Run every due batch entry, then exit (instead of polling forever)")
@click.option("--poll-seconds", type=float, default=None, help="Idle poll interval (default: 30)")
@click.option(
    "--results-repo", default=None, type=click.Path(file_okay=False, path_type=Path),
    help="Results repo every run records into (or $SILVERQUILLM_RESULTS_REPO)",
)
@click.option("--container-user", default=None, help="uid:gid to run every container as (default: the image's user)")
@click.option(
    "--replay-without-state", "replay_without_state", multiple=True, metavar="BATCH_ID",
    help=(
        "Acknowledge, for this one batch, that it has no committed state and may start"
        " from entry 0 (replaying may repeat completed runs and incur costs); creates"
        " the empty batches/state/<id>.json. Repeatable; never global."
    ),
)
@click.option(
    "--acknowledge-cleanup", "acknowledge_cleanup", multiple=True, metavar="BATCH_ID",
    help=(
        "Confirm that the run this batch's committed state records as running — on"
        " another host — has had its container cleaned up; marks it failed so the"
        " batch can continue here. Repeatable; never global."
    ),
)
def scheduler(
    batches_dir: Path | None,
    once: bool,
    poll_seconds: float | None,
    results_repo: Path | None,
    container_user: str | None,
    replay_without_state: tuple[str, ...],
    acknowledge_cleanup: tuple[str, ...],
) -> None:
    """Run the single-writer batch scheduler over batches/*.toml.

    Scans batch files in name order, respects not_before, consumes run specs
    in file order (re-reading the file before every not-yet-started run),
    resolves and records each candidate's identity at run start, executes
    each run through the bundle run path (`silverquillm run --candidate`),
    and writes per-run outcomes to the committed, portable state file
    batches/state/<batch>.json — never to a batch file; you commit the state
    checkpoints. A batch with no state file is blocked (replay protection)
    until --replay-without-state names it. Runs left running by a dead
    scheduler are reconciled (container force-removed and confirmed gone)
    before anything else runs; state from another host needs
    --acknowledge-cleanup. A failed run is recorded and the batch continues.
    A second scheduler on the same directory refuses to start.
    """
    from silverquillm.results_repo import resolve_results_repo
    from silverquillm.scheduler import (
        DEFAULT_POLL_SECONDS,
        AcknowledgementError,
        DockerContainerRuntime,
        ReconciliationError,
        Scheduler,
        SchedulerLockedError,
        SchedulerStopped,
        contract_run_executor,
    )

    runner = Scheduler(
        _batches_dir(batches_dir),
        executor=contract_run_executor(container_user=container_user),
        container_runtime=DockerContainerRuntime(),
        repo_root=_REPO_ROOT,
        results_repo=resolve_results_repo(results_repo),
        poll_seconds=DEFAULT_POLL_SECONDS if poll_seconds is None else poll_seconds,
        log=lambda message: click.echo(f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {message}"),
        replay_without_state=replay_without_state,
        acknowledge_cleanup=acknowledge_cleanup,
    )
    try:
        if once:
            count = runner.run_until_idle()
            click.echo(f"scheduler idle: {count} run(s) executed")
        else:
            runner.serve()
    except SchedulerLockedError as exc:
        raise click.ClickException(str(exc)) from exc
    except (AcknowledgementError, ReconciliationError) as exc:
        raise click.ClickException(f"scheduler stopped, nothing executed: {exc}") from exc
    except KeyboardInterrupt:
        click.echo("scheduler stopped (interrupted)", err=True)
        raise SystemExit(130) from None
    except SchedulerStopped:
        click.echo("scheduler stopped (SIGTERM)", err=True)
        raise SystemExit(143) from None


@main.group()
def queue() -> None:
    """Inspect the batch queue (read-only)."""


@queue.command("ls")
@_BATCHES_DIR_OPTION
def queue_ls(batches_dir: Path | None) -> None:
    """One-shot table: every batch, its not_before, per-run specs and states, and
    whether it is blocked (missing committed state, unreadable state, a run
    left running). Read-only."""
    from silverquillm.queue_view import build_queue_view, render_queue

    for line in render_queue(build_queue_view(_batches_dir(batches_dir))):
        click.echo(line)


@main.command()
@_BATCHES_DIR_OPTION
@click.option("--interval", type=float, default=2.0, show_default=True, help="Refresh interval in seconds")
def top(batches_dir: Path | None, interval: float) -> None:
    """Live, read-only view of the queue: order, not_before, running progress. q quits."""
    from silverquillm.queue_view import run_top

    run_top(_batches_dir(batches_dir), interval=interval)


@main.command("results-init")
@click.argument("path", type=click.Path(file_okay=False, path_type=Path))
def results_init(path: Path) -> None:
    """Lay out an empty private results repo at PATH.

    Writes the schema AGENTS.md (the results repo must be self-contained for
    analysis agents), an empty results/ tree, and an empty derived index
    runs.jsonl. PATH is typically a fresh clone of the private results repo;
    the command refuses if AGENTS.md already exists there. Records are then
    written by the bench (see silverquillm.results_repo) and the legacy
    corpus is backfilled by scripts/migrate_validated_results.py.
    """
    from silverquillm.results_repo import ResultsRepoError, init_results_repo

    try:
        written = init_results_repo(path)
    except ResultsRepoError as exc:
        raise click.ClickException(str(exc)) from exc
    for file_path in written:
        click.echo(f"wrote {file_path}")


if __name__ == "__main__":
    main()
