"""Operator commands for Karn candidates and local data collection.

``COMMANDS`` lists every command ``silverquillm.cli`` registers at top level.
"""

from __future__ import annotations

import contextlib
import getpass
import json
from pathlib import Path

import click

from silverquillm.host_config import LOCATIONS, location_option

from .definition import KarnError, load_candidate
from .exclusions import REASONS as REASON_CODES
from .grader import DEFAULT_GRADING_TIMEOUT, GRADER_BASES
from .host import DockerHost
from .interruption import terminate_as_interrupt

BATCHES_DIR_OPTION = location_option("batches_dir", help="The batch queue directory.")


BENCH_ROOT_OPTION = click.option(
    "--bench-root", type=click.Path(file_okay=False, path_type=Path), default=Path.cwd
)
RESULTS_DIR_OPTION = location_option("runs_dir", help="The run directory.")
RESULTS_REPO_OPTION = location_option("results_repo", help="The results repo clone.")
STATE_ROOT_OPTION = location_option("state_root")
GRADING_TIMEOUT_OPTION = click.option(
    "--grading-timeout",
    type=click.IntRange(min=1),
    default=DEFAULT_GRADING_TIMEOUT,
    show_default=True,
    help="Seconds before the grading container is killed.",
)


ALLOW_DIRTY_OPTION = click.option(
    "--allow-dirty",
    is_flag=True,
    help=(
        "Run even though the candidate's recipe or the bench checkout has uncommitted "
        "changes; the record keeps what was overridden."
    ),
)


def common_options(function):
    for option in reversed(
        [
            BENCH_ROOT_OPTION,
            RESULTS_DIR_OPTION,
            RESULTS_REPO_OPTION,
            STATE_ROOT_OPTION,
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
            GRADING_TIMEOUT_OPTION,
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
    type=click.Choice(["auto", "codex", "claude", "none"]),
    default="auto",
    show_default=True,
    help="Collect native journals and OTel; auto detects CODEX_HOME or CLAUDE_CONFIG_DIR.",
)
@ALLOW_DIRTY_OPTION
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


# A `--state-root` given to `login` itself carries down to its subcommands.
_LOGIN_STATE_ROOT = "silverquillm.login.state_root"


class _LoginGroup(click.Group):
    def resolve_command(self, ctx, args):
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            raise click.UsageError(
                f"unexpected extra argument ({args[0]}): a login is never named; "
                "it comes from the construct's pool (subcommands: "
                + ", ".join(sorted(self.commands))
                + ")",
                ctx,
            )
        return super().resolve_command(ctx, args)


@click.group("login", cls=_LoginGroup, invoke_without_command=True)
@click.option("--build-output", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--construct", help="Any construct using the login plugin.")
@click.option("--slot", help="Re-enroll this slot of the pool; omitted, enroll a new slot.")
@click.option(
    "--adopt",
    metavar="LEGACY",
    help="Move the per-construct login LEGACY, enrolled before pools, into the pool as a slot.",
)
@STATE_ROOT_OPTION
@click.pass_context
def enroll(ctx, build_output, construct, slot, adopt, state_root):
    """Enroll one subscription login into the pool of the construct's Karn login plugin.

    Each slot serves one run at a time, so enroll as many as runs you want concurrently.
    `login cooldown` holds slots out of new runs for a while instead.
    """
    if ctx.invoked_subcommand is not None:
        if ctx.get_parameter_source("state_root") is click.core.ParameterSource.COMMANDLINE:
            ctx.meta[_LOGIN_STATE_ROOT] = state_root
        return
    missing = [
        flag
        for flag, value in (("--build-output", build_output), ("--construct", construct))
        if value is None
    ]
    if missing:
        raise click.UsageError(f"Missing option {' and '.join(missing)}.", ctx)
    from .login import LOGIN_PLUGINS
    from .login_pool import LoginPool, adopt_legacy_login

    try:
        if slot and adopt:
            raise KarnError("login_slot_and_adopt_are_exclusive")
        candidate = load_candidate(build_output, construct)
        artifacts = [
            artifact for artifact in candidate.plugins if artifact.row["id"] in LOGIN_PLUGINS
        ]
        if len(artifacts) != 1:
            raise KarnError("candidate_requires_login_plugin")
        plugin_id = artifacts[0].row["id"]
        if adopt:
            click.echo("Adopted login slot " + adopt_legacy_login(state_root, adopt, plugin_id))
            return
        pool = LoginPool.of(state_root, plugin_id)
        profile = pool.named_slot(slot) if slot else pool.new_slot()
        click.echo(f"Enrolling login slot {pool.ref(profile)}", err=True)
        try:
            status = DockerHost(plugin_cache=state_root.resolve() / "plugins").enroll_login(
                profile, artifacts[0]
            )
        finally:
            if not slot:
                # The enrollment's own error, if any, is the one to report.
                with contextlib.suppress(OSError):
                    pool.discard_unenrolled(profile)
    except (KarnError, OSError, ValueError) as error:
        raise click.ClickException(str(error)) from None
    raise click.exceptions.Exit(status)


AGENTS = {"codex": "karn-codex-login", "claude": "karn-claude-login"}


@enroll.command("cooldown")
@click.option(
    "--agent",
    required=True,
    type=click.Choice(sorted(AGENTS)),
    help="The provider whose Login Pool holds the slots.",
)
@click.option("--slots", multiple=True, metavar="SLOT", help="A slot to hold; repeat or list.")
@click.option("--all", "every", is_flag=True, help="Every enrolled slot of the pool.")
@click.option("--duration", metavar="SPAN", help="How long, such as 30m, 5h, 2d or 1h30m.")
@click.option("--clear", is_flag=True, help="Lift the cooldown instead of setting one.")
@click.argument("more_slots", nargs=-1, metavar="[SLOT]...")
@STATE_ROOT_OPTION
@click.pass_context
def cooldown(ctx, agent, slots, every, duration, clear, more_slots, state_root):
    """Hold Login Profiles out of new runs until a duration passes (a Login Cooldown).

    A run already holding a slot is unaffected; runs and batch entries wait for a free one.
    """
    from datetime import UTC, datetime

    from .login_cooldown import clear_cooldown, parse_duration, set_cooldown
    from .login_pool import enrolled_slots, logins_root

    if ctx.get_parameter_source("state_root") is not click.core.ParameterSource.COMMANDLINE:
        state_root = ctx.meta.get(_LOGIN_STATE_ROOT, state_root)
    names = [*slots, *more_slots]
    if every and names:
        raise click.UsageError("Pass --slots or --all, not both.")
    if not every and not names:
        raise click.UsageError("Name the slots with --slots, or pass --all.")
    if clear == (duration is not None):
        raise click.UsageError("Pass exactly one of --duration or --clear.")
    plugin_id = AGENTS[agent]
    pool_root = logins_root(state_root) / plugin_id
    enrolled = enrolled_slots(pool_root, plugin_id)
    unknown = [name for name in names if name not in enrolled]
    if unknown:
        listed = ", ".join(enrolled) or "none"
        raise click.UsageError(
            f"Not enrolled in the {agent} pool: {', '.join(unknown)} (enrolled: {listed})."
        )
    chosen = enrolled if every else list(dict.fromkeys(names))
    try:
        if clear:
            for name in chosen:
                lifted = clear_cooldown(pool_root / name)
                click.echo(
                    f"{plugin_id}/{name}: " + ("cooldown lifted" if lifted else "no cooldown")
                )
            return
        now = datetime.now(UTC)
        until = now + parse_duration(duration)
        for name in chosen:
            set_cooldown(pool_root / name, until, now=now)
            stamp = until.astimezone().strftime("%a %Y-%m-%d %H:%M %Z")
            click.echo(f"{plugin_id}/{name}: cooling down until {stamp}")
    except (KarnError, OSError) as error:
        raise click.ClickException(str(error)) from None


@click.command()
@BATCHES_DIR_OPTION
@click.option("--once", is_flag=True)
@click.option("--poll-seconds", type=click.FloatRange(min=0.1), default=30)
@click.option("--replay-without-state", multiple=True, metavar="BATCH_ID")
@ALLOW_DIRTY_OPTION
@common_options
def scheduler(batches_dir, once, poll_seconds, replay_without_state, allow_dirty, **options):
    """Execute due batches serially through the same run lifecycle."""
    from silverquillm.queue_state import SchedulerLockedError

    from .batching import KarnScheduler, queue_rows
    from .grader import ContainerGrader

    runner = KarnScheduler(
        batches_dir,
        replay_without_state=replay_without_state,
        allow_dirty=allow_dirty,
        **options,
    )
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


@click.command()
@click.option("--benchmark", "benchmark_id", required=True)
@click.option(
    "--out",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory for one JSON file per run plus summary.json; never the results repo.",
)
@click.option(
    "--run", "runs", multiple=True, metavar="RUN_ID", help="Run id or prefix; repeatable."
)
@click.option(
    "--candidate",
    "candidates",
    multiple=True,
    metavar="HASH",
    help="Candidate hash or prefix; repeatable.",
)
@click.option("--workers", type=click.IntRange(min=1), default=2, show_default=True)
@click.option(
    "--force", is_flag=True, help="Re-grade runs already graded in --out on these inputs."
)
@click.option(
    "--substitute-grader",
    is_flag=True,
    help=(
        "Grade a run whose recorded grader image is absent here, e.g. one from another "
        "host, on this host's grader for the same Python; the output names both images."
    ),
)
@location_option("state_root", help="Where baseline reference grades are kept, as for run.")
@BENCH_ROOT_OPTION
@RESULTS_DIR_OPTION
@RESULTS_REPO_OPTION
@GRADING_TIMEOUT_OPTION
def regrade(**options):
    """Re-grade retained runs on the current grading inputs, e.g. after Audited Tests change.

    Each run is graded again from the workspace it was graded from, on its recorded grader
    image. The workspace comes from the local run artifacts, else from the results repo's
    workspace archive. Records stay untouched; the new scores are written under --out.
    """
    from .regrade import regrade as run_regrade

    try:
        with terminate_as_interrupt():
            summary = run_regrade(**options)
    except (KarnError, OSError) as error:
        raise click.ClickException(str(error)) from None
    except KeyboardInterrupt:
        click.echo("regrade interrupted; finished runs are kept in --out", err=True)
        raise click.exceptions.Exit(130) from None
    for line in _regrade_table(summary):
        click.echo(line)
    if summary["excluded"]:
        click.echo("excluded from the comparison:")
    for row in summary["excluded"]:
        click.echo(f"  {row['run_id'][:8]}  {row['reason']:20} {row['note']}")
    for row in summary["skipped"]:
        click.echo(f"skipped {row['run_id']}: {row['reason']}", err=True)
    for row in summary["errors"]:
        click.echo(f"error {row['run_id']}: {row['reason']}", err=True)
    if summary.get("grading_inputs_changed_during_regrade"):
        click.echo("grading inputs changed during the regrade; run it again", err=True)
    if summary["errors"] or summary.get("grading_inputs_changed_during_regrade"):
        raise click.exceptions.Exit(1)


def _regrade_table(summary):
    def percent(value):
        return "   -  " if value is None else f"{value * 100:5.1f}%"

    def graded_on(row):
        digest = row["source_grading_inputs_digest"]
        if digest is None:
            return "unknown " + row["run_id"][:8]
        return digest.removeprefix("sha256:")[:12]

    yield f"grading inputs {summary['grading_inputs_digest']}"
    yield (
        f"{'candidate':12} {'name':28} {'graded on':16} {'runs':>4}  "
        f"{'target before':>13} {'after':>6} {'pairs':>5}  {'fdn':>6}  {'engine':>6}"
    )
    for row in summary["cohorts"]:
        target, fdn, engine = (
            row[name] for name in ("card_correctness", "fdn_regression", "engine_regression")
        )
        yield (
            f"{row['candidate_hash'][:12]:12} {str(row['name'])[:28]:28} {graded_on(row):16} "
            f"{row['runs']:>4}  {percent(target['before_mean_pass_rate']):>13} "
            f"{percent(target['after_mean_pass_rate'])} {target['paired_runs']:>5}  "
            f"{percent(fdn['after_mean_pass_rate'])}  {percent(engine['after_mean_pass_rate'])}"
        )


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


def _monitor_location(key: str, help: str):
    """A location flag that, unlike the run commands', may stay unset: the monitor shows it."""
    return click.option(
        LOCATIONS[key].flag,
        key,
        type=click.Path(file_okay=False, path_type=Path),
        default=None,
        help=help + " Defaults to the environment, then the host configuration file.",
    )


@click.command()
@click.option(
    "--interval", type=float, default=2.0, show_default=True, help="Refresh interval in seconds."
)
@click.option("--no-flair", is_flag=True, help="Monochrome theme with plain glyphs.")
@click.option(
    "--no-mouse", is_flag=True, help="Leave the mouse to the terminal; every action has a key."
)
@_monitor_location("results_repo", "The results repo clone.")
@_monitor_location("batches_dir", "The batch queue directory.")
@_monitor_location("runs_dir", "The run directory.")
@_monitor_location("state_root", "The state root holding the Login Pools.")
def top(interval, no_flair, no_mouse, **locations):
    """Read-only monitor: live runs, queue, Login Profiles, history and run details.

    Every action has a key; press ? in the monitor for the list. q quits.
    """
    from silverquillm.top import launch

    raise SystemExit(launch(locations, interval=interval, no_flair=no_flair, mouse=not no_mouse))


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
@click.option(
    "--tag", default=None, help="Tag other than silverquillm-grader:pyX.Y; one --python only."
)
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


@click.group()
def results():
    """Workspace archives and exclusions kept beside the records in the results repo."""


@results.command("archive")
@click.option(
    "--run", "runs", multiple=True, metavar="RUN_ID", help="Record id or prefix; repeatable."
)
@click.option("--dry-run", is_flag=True, help="Verify each archive without writing it.")
@RESULTS_DIR_OPTION
@RESULTS_REPO_OPTION
def results_archive(runs, dry_run, results_dir, results_repo):
    """Archive the graded workspace of every record whose run artifacts this host holds.

    Runs write their own archive; this backfills records from before archives existed
    and retries any that failed. Each archive is rebuilt and verified before it is written.
    """
    from .workspace_archive import backfill

    rows = backfill(results_repo, results_dir, runs=runs, dry_run=dry_run)
    counts: dict[str, int] = {}
    size = 0
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        size += row.get("bytes", 0) if row["status"] in ("archived", "would_archive") else 0
        if row["status"] in ("skipped", "refused"):
            click.echo(f"{row['status']} {row['run_id']}: {row['reason']}", err=True)
    click.echo(
        json.dumps({"counts": counts, "patch_bytes": size, "dry_run": dry_run}, sort_keys=True)
    )
    if counts.get("refused"):
        raise click.exceptions.Exit(1)


@results.command("exclude")
@click.argument("run_id")
@click.option("--reason", required=True, type=click.Choice(sorted(REASON_CODES)))
@click.option("--note", required=True, help="Why, in a sentence a later reader can check.")
@click.option("--superseded-by", metavar="RUN_ID", help="The record replacing it (superseded).")
@click.option("--by", "excluded_by", default=getpass.getuser, show_default="current user")
@RESULTS_REPO_OPTION
def results_exclude(run_id, reason, note, superseded_by, excluded_by, results_repo):
    """Exclude a recorded run from analyses, with the reason and a note.

    Writes exclusions/<candidate-hash>/<run-id>.json once; delete the file to include the
    run again.
    """
    from .exclusions import exclude

    try:
        exclusion = exclude(
            results_repo,
            run_id,
            reason=reason,
            note=note,
            excluded_by=excluded_by,
            superseded_by=superseded_by,
        )
    except KarnError as error:
        raise click.ClickException(str(error)) from None
    click.echo(json.dumps(exclusion.to_dict(), sort_keys=True))


@results.command("check")
@click.option(
    "--write-rules", is_flag=True, help="Write the missing rule exclusions instead of listing them."
)
@RESULTS_REPO_OPTION
def results_check(write_rules, results_repo):
    """List records a rule excludes that have no exclusion, and exclusions without records."""
    from .exclusions import check

    try:
        report = check(results_repo, write_rules=write_rules)
    except KarnError as error:
        raise click.ClickException(str(error)) from None
    for row in report["written"]:
        click.echo(f"excluded {row['run_id']}: {row['reason']} ({row['note']})")
    for row in report["unexcluded_rule_matches"]:
        click.echo(f"unexcluded {row['run_id']}: rule {row['rule']}", err=True)
    for row in report["orphaned_exclusions"]:
        click.echo(f"orphaned exclusion {row['run_id']}: no such record", err=True)
    for row in report["missing_superseding_runs"]:
        click.echo(
            f"superseding run {row['superseded_by']} of {row['run_id']} not recorded", err=True
        )
    if any(report[key] for key in report if key != "written"):
        raise click.exceptions.Exit(1)


@results.command("exclusions")
@click.option("--json", "as_json", is_flag=True, help="Print the exclusion files as JSON lines.")
@RESULTS_REPO_OPTION
def results_exclusions(as_json, results_repo):
    """Every excluded run with its reason and note, for the short list under a table."""
    from .exclusions import load_exclusions

    try:
        exclusions = load_exclusions(results_repo)
    except KarnError as error:
        raise click.ClickException(str(error)) from None
    for exclusion in sorted(exclusions.values(), key=lambda e: (e.reason, e.run_id)):
        if as_json:
            click.echo(json.dumps(exclusion.to_dict(), sort_keys=True))
        else:
            click.echo(f"{exclusion.run_id[:8]}  {exclusion.reason:20} {exclusion.note}")


COMMANDS = (run, enroll, scheduler, recover, regrade, queue, top, grader, results)
