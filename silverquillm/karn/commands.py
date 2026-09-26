"""Operator commands for Karn candidates and local data collection.

``COMMANDS`` lists every command ``silverquillm.cli`` registers at top level.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from .definition import KarnError, load_candidate
from .host import DockerHost


BATCHES_DIR_OPTION = click.option(
    "--batches-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("batches"),
    show_default=True,
    help="The batch queue directory.",
)


def common_options(function):
    for option in reversed(
        [
            click.option(
                "--bench-root", type=click.Path(file_okay=False, path_type=Path), default=Path.cwd
            ),
            click.option(
                "--results-dir",
                type=click.Path(file_okay=False, path_type=Path),
                default=Path("runs/karn"),
            ),
            click.option(
                "--results-repo",
                type=click.Path(file_okay=False, path_type=Path),
                default=Path("results"),
                envvar="SILVERQUILLM_RESULTS_REPO",
            ),
            click.option(
                "--state-root",
                type=click.Path(file_okay=False, path_type=Path),
                default=lambda: Path.home() / ".local/state/silverquillm",
            ),
            click.option(
                "--collector-host",
                default=None,
                help="Host address reachable by Docker's telemetry relay; normally detected.",
            ),
        ]
    ):
        function = option(function)
    return function


@click.command()
@click.option(
    "--build-output", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--construct", required=True)
@click.option("--benchmark", "benchmark_id", required=True)
@click.option("--login", default=None, help="Named local subscription login profile.")
@click.option("--budget-seconds", type=click.IntRange(min=1), default=86400, show_default=True)
@click.option("--snapshot-seconds", type=click.FloatRange(min=0.1), default=60, show_default=True)
@common_options
def run(**options):
    """Execute a fixed definition and image, grade available work, and retain a record."""
    from .execution import run_benchmark

    try:
        record = run_benchmark(**options)
    except (KarnError, OSError, ValueError) as error:
        raise click.ClickException(str(error)) from None
    execution = record.run_metadata["execution"]
    click.echo(
        json.dumps(
            {
                "run_id": record.run_id,
                "benchmark": record.benchmark,
                "execution": execution["status"],
                "scores": record.scores,
                "measurements": record.run_metadata["measurements"],
            },
            sort_keys=True,
        )
    )
    if execution["status"] != "completed":
        raise click.exceptions.Exit(130 if execution["status"] == "interrupted" else 1)


@click.command("login")
@click.argument("profile")
@click.option(
    "--build-output", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--construct", required=True)
@click.option(
    "--state-root",
    type=click.Path(file_okay=False, path_type=Path),
    default=lambda: Path.home() / ".local/state/silverquillm",
)
def enroll(profile, build_output, construct, state_root):
    """Enroll subscription authentication through the selected Karn login plugin."""
    from .execution import login_profile

    try:
        candidate = load_candidate(build_output, construct)
        artifacts = [
            artifact for artifact in candidate.plugins if artifact.row["id"] == "karn-codex-login"
        ]
        if len(artifacts) != 1:
            raise KarnError("candidate_requires_codex_login_plugin")
        status = DockerHost(plugin_cache=state_root / "plugins").enroll_login(
            login_profile(state_root, profile), artifacts[0]
        )
    except (KarnError, OSError, ValueError) as error:
        raise click.ClickException(str(error)) from None
    raise click.exceptions.Exit(status)


@click.command()
@BATCHES_DIR_OPTION
@click.option("--once", is_flag=True)
@click.option("--poll-seconds", type=click.FloatRange(min=0.1), default=30)
@click.option("--replay-without-state", multiple=True, metavar="BATCH_ID")
@common_options
def scheduler(batches_dir, once, poll_seconds, replay_without_state, **options):
    """Execute due batches serially through the same run lifecycle."""
    from silverquillm.queue_state import SchedulerLockedError

    from .batching import KarnScheduler, queue_rows

    runner = KarnScheduler(batches_dir, replay_without_state=replay_without_state, **options)
    try:
        if once:
            click.echo(f"scheduler idle: {runner.run_until_idle()} run(s) executed")
            for row in queue_rows(batches_dir):
                if row["status"] == "missing_state":
                    click.echo(
                        f"{row['batch']}: restore state or pass --replay-without-state {row['batch']}",
                        err=True,
                    )
        else:
            runner.serve(poll_seconds)
    except (KarnError, OSError, SchedulerLockedError) as error:
        raise click.ClickException(str(error)) from None
    except KeyboardInterrupt:
        click.echo("scheduler stopped; interrupted run evidence retained", err=True)
        raise click.exceptions.Exit(130) from None


@click.group()
def queue():
    """Inspect the batch queue."""


@queue.command("ls")
@BATCHES_DIR_OPTION
@click.option("--json", "as_json", is_flag=True, help="Print the raw queue rows as JSON.")
def queue_ls(batches_dir, as_json):
    """Show every batch, including interrupted, partially observed and unsupported ones."""
    from .batching import queue_rows
    from .queue_view import render_rows

    rows = queue_rows(batches_dir)
    if as_json:
        click.echo(json.dumps(rows, sort_keys=True))
        return
    for line in render_rows(rows):
        click.echo(line)


@click.command()
@BATCHES_DIR_OPTION
@click.option("--interval", type=float, default=2.0, show_default=True, help="Refresh interval in seconds")
def top(batches_dir, interval):
    """Live, read-only view of the batch queue. q quits."""
    from .queue_view import run_top

    run_top(batches_dir, interval=interval)


COMMANDS = (run, enroll, scheduler, queue, top)
