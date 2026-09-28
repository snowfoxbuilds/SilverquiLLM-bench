"""Operator commands for Karn candidates and local data collection.

``COMMANDS`` lists every command ``silverquillm.cli`` registers at top level.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from .definition import KarnError, load_candidate
from .grader import DEFAULT_GRADING_TIMEOUT, GRADER_BASES
from .host import DockerHost
from .interruption import terminate_as_interrupt

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
            click.option(
                "--grader-image",
                default=None,
                envvar="SILVERQUILLM_GRADER_IMAGE",
                help=(
                    "Local grader image to use instead of the one built for the candidate's "
                    "Python; it must still be built for that version. Never pulled or built "
                    "by a run."
                ),
            ),
            click.option(
                "--grading-timeout",
                type=click.IntRange(min=1),
                default=DEFAULT_GRADING_TIMEOUT,
                show_default=True,
                help="Seconds before the grading container is killed.",
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
@click.option("--budget-seconds", type=click.IntRange(min=1), default=86400, show_default=True)
@click.option("--snapshot-seconds", type=click.FloatRange(min=0.1), default=60, show_default=True)
@click.option(
    "--native-telemetry",
    type=click.Choice(["auto", "codex", "none"]),
    default="auto",
    show_default=True,
    help="Collect native Codex journals and OTel; auto detects a declared CODEX_HOME.",
)
@common_options
def run(**options):
    """Execute a fixed definition and image, grade available work, and retain a record."""
    from .execution import run_benchmark
    from .records import RecordWritePendingError

    try:
        with terminate_as_interrupt():
            record = run_benchmark(**options)
    except RecordWritePendingError as error:
        raise click.ClickException(
            f"{error}: retry with `silverquillm recover {error.record.run_id}`"
        ) from None
    except (KarnError, OSError, ValueError) as error:
        raise click.ClickException(str(error)) from None
    _report(record)


def _report(record, *, exit_on_status=True):
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
    if exit_on_status and execution["status"] != "completed":
        raise click.exceptions.Exit(130 if execution["status"] == "interrupted" else 1)


@click.command("login")
@click.option(
    "--build-output", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--construct", required=True)
@click.option(
    "--state-root",
    type=click.Path(file_okay=False, path_type=Path),
    default=lambda: Path.home() / ".local/state/silverquillm",
)
def enroll(build_output, construct, state_root):
    """Enroll the construct's own subscription login through its Karn login plugin."""
    from .execution import login_profile
    from .login import LOGIN_PLUGINS

    try:
        candidate = load_candidate(build_output, construct)
        artifacts = [
            artifact for artifact in candidate.plugins if artifact.row["id"] in LOGIN_PLUGINS
        ]
        if len(artifacts) != 1:
            raise KarnError("candidate_requires_login_plugin")
        status = DockerHost(plugin_cache=state_root.resolve() / "plugins").enroll_login(
            login_profile(state_root, construct), artifacts[0]
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
    from .grader import ContainerGrader

    runner = KarnScheduler(batches_dir, replay_without_state=replay_without_state, **options)
    try:
        # Without an override the grader depends on each entry's candidate, checked per run.
        if options["grader_image"] is not None:
            ContainerGrader.from_image(options["grader_image"])
        if once:
            with terminate_as_interrupt():
                executed = runner.run_until_idle()
            click.echo(f"scheduler idle: {executed} run(s) executed")
            for row in queue_rows(batches_dir):
                if row["status"] == "missing_state":
                    click.echo(
                        f"{row['batch']}: restore state or pass --replay-without-state {row['batch']}",
                        err=True,
                    )
        else:
            with terminate_as_interrupt():
                runner.serve(poll_seconds)
    except (KarnError, OSError, SchedulerLockedError) as error:
        raise click.ClickException(str(error)) from None
    except KeyboardInterrupt:
        click.echo("scheduler stopped; interrupted run evidence retained", err=True)
        raise click.exceptions.Exit(130) from None


@click.command()
@click.argument("run_id")
@click.option("--stop", is_flag=True, help="Stop the run's container if it is still running.")
@common_options
def recover(run_id, stop, **options):
    """Settle an interrupted run: stop its workload, harvest, grade, and write its record."""
    from .recovery import LoginSettlementPendingError, RunNeverLaunchedError, recover_run

    try:
        with terminate_as_interrupt():
            record = recover_run(run_id=run_id, stop=stop, **options)
    except LoginSettlementPendingError as error:
        _report(error.record, exit_on_status=False)
        raise click.ClickException(
            f"{error}: the record is final; run `silverquillm recover {run_id}` again to settle"
        ) from None
    except RunNeverLaunchedError as error:
        click.echo(json.dumps({"run_id": run_id, "execution": str(error)}, sort_keys=True))
        raise click.exceptions.Exit(1) from None
    except (KarnError, OSError, ValueError) as error:
        message = str(error)
        if message == "run_container_still_running":
            message += "; pass --stop to stop it and recover"
        raise click.ClickException(message) from None
    except KeyboardInterrupt:
        click.echo("recovery interrupted; run it again to finish", err=True)
        raise click.exceptions.Exit(130) from None
    _report(record, exit_on_status=False)


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


@click.group()
def grader():
    """Build the network-less image that grades candidate work."""


@grader.command("build")
@click.option(
    "--python",
    "versions",
    multiple=True,
    type=click.Choice(sorted(GRADER_BASES)),
    help="Python minor version to build a grader for; repeatable. Default: every version.",
)
@click.option("--tag", default=None, help="Tag other than silverquillm-grader:pyX.Y; one --python only.")
def grader_build(versions, tag):
    """Build pinned grader images and print each one's tag and image ID."""
    from .grader import build_grader_image, grader_tag

    versions = versions or tuple(sorted(GRADER_BASES))
    if tag is not None and len(versions) != 1:
        raise click.UsageError("--tag needs exactly one --python")
    try:
        for version in versions:
            image_id = build_grader_image(version, tag)
            click.echo(f"{tag or grader_tag(version)} {image_id}")
    except KarnError as error:
        raise click.ClickException(str(error)) from None


COMMANDS = (run, enroll, scheduler, recover, queue, top, grader)
