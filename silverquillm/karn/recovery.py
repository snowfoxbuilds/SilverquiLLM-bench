"""Recover a local interrupted run without replaying its model task."""

from __future__ import annotations

import contextlib
import dataclasses
import json
import re
import uuid
from pathlib import Path

from silverquillm.queue_state import _write_atomically

from . import provenance
from .baseline import BaselineStore, baseline_reference_grade, combined_regression
from .benchmark import load_benchmark
from .definition import KarnError, canonical, load_candidate
from .execution import (
    _scores,
    attach_to_record,
    login_profile,
    mark_observation_problems,
    observation_session,
    run_lock,
    telemetry_collector,
)
from .grader import (
    DEFAULT_GRADING_TIMEOUT,
    PYTHON_VERSION,
    ContainerGrader,
    GraderError,
    grader_for,
    legacy_grader,
)
from .grading_inputs import grading_inputs
from .host import DockerHost, HostResult
from .login import (
    NATIVE_PRESERVED,
    LoginInUseError,
    PluginProcess,
    install_plugin,
    preserve_pending_native,
    recover_login,
)
from .records import (
    KarnIdentity,
    KarnRunRecord,
    RecordWritePendingError,
    missing_scores,
    read_record,
    write_record,
)
from .snapshots import WorkspaceSnapshots, retain_git_history
from .subscription_usage import codex_usage, subscription_usage
from .subscription_usage import provider_for as usage_provider


class RunNeverLaunchedError(KarnError):
    """The runner stopped before the run input existed, so no workload was ever launched."""

    def __init__(self):
        super().__init__("interrupted_before_launch")


class LoginSettlementPendingError(KarnError):
    """The run's record is final, but its own authentication is still pending on the profile.

    The login journal is left intact, so another ``recover`` (or the profile's next run)
    settles it; ``record`` is the run's final record.
    """

    def __init__(self, reason: str, record: KarnRunRecord):
        super().__init__("login_settlement_pending:" + reason)
        self.record = record


def recover_run(
    *,
    run_id: str,
    stop: bool = False,
    bench_root: Path,
    results_dir: Path,
    results_repo: Path,
    state_root: Path,
    collector_host=None,
    grader_image: str | None = None,
    grading_timeout: int = DEFAULT_GRADING_TIMEOUT,
    grader: ContainerGrader | None = None,
) -> KarnRunRecord:
    """Recover one direct or batch run by id; a live workload is stopped only on request."""
    provenance.require_package_from(bench_root)
    if not RUN_ID.fullmatch(run_id):
        raise KarnError("invalid_run_id")
    if not (Path(results_dir).resolve() / run_id).is_dir():
        raise KarnError("run_not_found:" + run_id)
    docker = DockerHost(plugin_cache=Path(state_root).resolve() / "plugins").docker
    info = docker.inspect_container("sq-run-" + run_id)
    if info is not None and info["State"].get("Running") and not stop:
        raise KarnError("run_container_still_running")
    return recover_benchmark(
        run_id=run_id,
        spec={},
        bench_root=bench_root,
        results_dir=results_dir,
        results_repo=results_repo,
        state_root=state_root,
        collector_host=collector_host,
        grader_image=grader_image,
        grading_timeout=grading_timeout,
        grader=grader,
    )


def recover_benchmark(
    *,
    run_id: str,
    spec: dict,
    bench_root: Path,
    results_dir: Path,
    results_repo: Path,
    state_root: Path,
    collector_host=None,
    grader_image: str | None = None,
    grading_timeout: int = DEFAULT_GRADING_TIMEOUT,
    grader: ContainerGrader | None = None,
) -> KarnRunRecord:
    """Idempotent: a recovered or retained record is returned instead of recovering twice.

    Raises :class:`RunNeverLaunchedError` when the runner died before writing its input.
    A package from another checkout is refused before the run is locked or anything is
    settled, published, cleaned up or graded.
    """
    provenance.require_package_from(bench_root)
    run_dir = Path(results_dir).resolve() / run_id
    with contextlib.ExitStack() as held:
        if run_dir.is_dir():
            held.enter_context(run_lock(run_dir))
        return _recover(
            run_id=run_id,
            run_dir=run_dir,
            bench_root=bench_root,
            results_repo=results_repo,
            state_root=state_root,
            grader_image=grader_image,
            grading_timeout=grading_timeout,
            grader=grader,
        )


def _stopped(record: KarnRunRecord) -> bool:
    return bool(record.run_metadata["execution"]["workspace_stopped"])


def _read_retained(path: Path) -> KarnRunRecord:
    retained = json.loads(path.read_text())
    record = KarnRunRecord(retained["manifest"], retained["scores"])
    record.validate()
    return record


def _retain(path: Path, record: KarnRunRecord) -> None:
    _write_atomically(
        path,
        canonical({"manifest": record.manifest, "scores": record.scores}).decode() + "\n",
        prefix="." + path.stem + "-",
    )


RECOVERY_DIRECTORY = re.compile(r"recovery-[0-9]+")
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
CANDIDATE_HASH = re.compile(r"[0-9a-f]{64}")


def _retained_recoveries(run_dir: Path, run_id: str) -> list[KarnRunRecord]:
    """Stopped linked recoveries retained under the host-named ``recovery-N`` directories.

    Found by name rather than through ``recovery-record.json``, so a crash between retaining
    the record and writing its link still republishes the same record, and no path taken
    from a file is ever followed.
    """
    found = []
    for directory in sorted(run_dir.glob("recovery-*")):
        path = directory / "run-record.json"
        if (
            not RECOVERY_DIRECTORY.fullmatch(directory.name)
            or directory.is_symlink()
            or path.is_symlink()
            or not path.is_file()
        ):
            continue
        record = _read_retained(path)
        if record.run_metadata.get("recovery_of") == run_id and _stopped(record):
            found.append(record)
    return found


def _destination(results_repo: Path, record: KarnRunRecord) -> Path:
    return Path(results_repo) / "results" / record.candidate.hash / record.run_id


def _unpublished(results_repo, records) -> list[KarnRunRecord]:
    return [record for record in records if not _destination(results_repo, record).is_dir()]


def _retained_original(run_dir: Path, run_id: str) -> KarnRunRecord | None:
    """The record retained under the run's own id, whether or not its workspace was stopped.

    It is never rewritten: an unconfirmed observation stays evidence, and its reconciliation
    is a separate linked recovery.
    """
    path = run_dir / "run-record.json"
    if not path.is_file():
        return None
    original = _read_retained(path)
    if original.run_id != run_id:
        raise KarnError("recovery_run_identity_mismatch")
    return original


def _finalized_record(run_id, run_dir, results_repo) -> tuple[KarnRunRecord, list] | None:
    """This run's stopped record and, in publication order, whichever of its records are unpublished.

    A retained original precedes its linked recovery, so a published recovery never points
    at an observation that is not published yet.
    """
    link_path = run_dir / "recovery-record.json"
    if link_path.is_file():
        link = json.loads(link_path.read_text())
        # The link names a record only by id; anything else could escape the results repository.
        if RUN_ID.fullmatch(str(link.get("run_id"))) and CANDIDATE_HASH.fullmatch(
            str(link.get("candidate_hash"))
        ):
            linked = Path(results_repo) / "results" / link["candidate_hash"] / link["run_id"]
            if linked.is_dir():
                recovered = read_record(linked)
                if recovered.run_metadata.get("recovery_of") == run_id and _stopped(recovered):
                    # The original is always published before its linked recovery.
                    return recovered, []
    original = _retained_original(run_dir, run_id)
    prior = [original] if original is not None else []
    retained = _retained_recoveries(run_dir, run_id)
    if len(retained) > 1:
        raise KarnError("ambiguous_retained_recovery")
    if retained:
        [recovered] = retained
        destination = _destination(results_repo, recovered)
        final = read_record(destination) if destination.is_dir() else recovered
        return final, _unpublished(results_repo, [*prior, recovered])
    if original is not None and _stopped(original):
        destination = _destination(results_repo, original)
        if destination.is_dir():
            return read_record(destination), []
        return original, [original]
    existing = list((Path(results_repo) / "results").glob("*/" + run_id))
    if len(existing) > 1:
        raise KarnError("ambiguous_interrupted_run_record")
    if existing:
        published = read_record(existing[0])
        if _stopped(published):
            return published, []
    return None


def _publish(results_repo, records, final: KarnRunRecord, run_dir: Path) -> None:
    """Publish each record not yet published, in order; a blocked write carries the final record."""
    try:
        for record in _unpublished(results_repo, records):
            write_record(results_repo, record)
            attach_to_record(results_repo, record, run_dir)
    except RecordWritePendingError:
        raise RecordWritePendingError(final) from None


def _retained_candidate(run_dir: Path, inputs: dict, identity: KarnIdentity):
    # Recovery never runs the image, so it verifies the retained definition against the
    # recorded image identity instead of requiring the image to still be present locally.
    return load_candidate(
        run_dir / "candidate",
        inputs["construct"],
        image_inspector=lambda reference: {"Id": identity.image_id, "RepoDigests": [reference]},
    )


def _recovery_grader(inputs: dict, reference: str | None, timeout: int) -> ContainerGrader:
    """Grade on the Python version the run was launched with, never a fresh probe.

    Recovery never runs the candidate image, which may be gone; the version is a fact
    of the launch. A run launched before versions were recorded keeps the 3.13 grader
    it would have had, and its record states no candidate version.
    """
    if "candidate_python" not in inputs:
        return legacy_grader(reference, timeout=timeout)
    python = inputs["candidate_python"]
    if not isinstance(python, str) or not PYTHON_VERSION.fullmatch(python + "\n"):
        raise KarnError("interrupted_run_input_invalid:candidate_python")
    return grader_for(python, reference, timeout=timeout)


def _owns_pending_login(profile, run_id: str) -> bool:
    pending = profile.pending()
    return pending is not None and pending.get("run_id") == run_id


def _settle_own_login(run_id, profile, host, candidate) -> list[dict] | None:
    """Settle this run's pending authentication with the plugin artifact the run retained.

    Another run's pending login is never settled or harvested here: its container may still
    be live, and its native state belongs to that run's own evidence. Returns the plugin
    status once settled, or None when this run owns nothing pending. On failure the journal
    stays intact, so a later recovery or the profile's next run retries.
    """
    if profile is None or not _owns_pending_login(profile, run_id):
        return None
    with profile.exclusive():
        if not _owns_pending_login(profile, run_id):
            return None
        pending = profile.pending()
        artifact = next(
            (p for p in candidate().plugins if p.row["artifact"] == pending.get("plugin_artifact")),
            None,
        )
        if artifact is None:
            raise KarnError("login_recovery_requires_previous_plugin")
        python = install_plugin(artifact, host.plugin_cache)
        with PluginProcess(artifact, python, profile) as plugin:
            preserve_pending_native(profile, host.docker.stop_and_confirm)
            recover_login(
                profile, plugin, host.docker.stop_and_confirm, cleanup=host.docker.cleanup_run
            )
            try:
                return plugin.status()
            except KarnError:
                # The login is settled; only its informational status is unavailable.
                return []


def _failure_reason(error: Exception) -> str:
    """A KarnError's code, else only the exception type: messages can carry paths or secrets."""
    return str(error) if isinstance(error, KarnError) else type(error).__name__


def _conclude(record, unpublished, *, run_id, run_dir, results_repo, state_root, host):
    """Publish a final record if needed, reporting the run's own login settlement separately.

    Settlement never blocks publication: whatever it hits, including a busy login, the
    record is published and a LoginSettlementPendingError carries it back.
    """
    failure = None
    try:
        try:
            inputs = json.loads((run_dir / "run-input.json").read_text())
            login = inputs.get("login")
        except (OSError, ValueError):
            inputs, login = None, record.run_metadata.get("login_profile")
        profile = login_profile(state_root, login)
        if inputs is None and profile is not None and _owns_pending_login(profile, run_id):
            raise KarnError("login_recovery_input_unavailable")
        _settle_own_login(
            run_id,
            profile,
            host,
            lambda: _retained_candidate(run_dir, inputs, record.candidate),
        )
    except Exception as error:  # noqa: BLE001 -- a final record is published whatever settlement hits.
        failure = error
    _publish(results_repo, unpublished, record, run_dir)
    if failure is not None:
        raise LoginSettlementPendingError(_failure_reason(failure), record)
    return record


def _recover(
    *,
    run_id,
    run_dir,
    bench_root,
    results_repo,
    state_root,
    grader_image,
    grading_timeout,
    grader,
) -> KarnRunRecord:
    from .observations import summarize_events

    host = DockerHost(plugin_cache=Path(state_root).resolve() / "plugins")
    finalized = _finalized_record(run_id, run_dir, results_repo)
    if finalized is not None:
        record, unpublished = finalized
        return _conclude(
            record,
            unpublished,
            run_id=run_id,
            run_dir=run_dir,
            results_repo=results_repo,
            state_root=state_root,
            host=host,
        )
    previous_record = _retained_original(run_dir, run_id)
    previous_path = None
    existing = list((Path(results_repo) / "results").glob("*/" + run_id))
    if existing:
        previous_path = existing[0]
        previous_record = read_record(previous_path)
    elif previous_record is not None:
        # An unconfirmed observation whose publication was blocked is still the prior record.
        previous_path = _destination(results_repo, previous_record)
    try:
        inputs = json.loads((run_dir / "run-input.json").read_text())
    except FileNotFoundError:
        # The input is written before launch, so no workload should exist; remove any that does.
        host.docker.cleanup_run("sq-run-" + run_id, run_id)
        raise RunNeverLaunchedError() from None
    except (OSError, ValueError):
        raise KarnError("interrupted_run_input_unavailable:" + run_id) from None
    original = inputs.get("candidate_identity")
    if original is None and previous_record is not None:
        original = previous_record.candidate.to_dict()
    if original is None:
        raise KarnError("original_candidate_identity_unavailable")
    identity = KarnIdentity.from_dict(original)
    candidate = _retained_candidate(run_dir, inputs, identity)
    retained_identity = KarnIdentity.from_dict({"scheme": candidate.scheme, **candidate.identity()})
    if retained_identity != identity or (
        previous_record is not None and previous_record.candidate != identity
    ):
        raise KarnError("retained_definition_identity_mismatch")
    benchmark = load_benchmark(bench_root, inputs["benchmark"])
    grader = grader or _recovery_grader(inputs, grader_image, grading_timeout)
    profile = login_profile(state_root, inputs["login"])
    observed = HostResult(
        run_id,
        candidate.identity(),
        "sq-run-" + run_id,
        str(run_dir / "workspace"),
        str(run_dir / "host"),
        inputs["budget_seconds"],
        status="interrupted",
        failure_stage="recovery",
        error="prior_runner_interrupted",
    )
    telemetry = inputs.get("native_telemetry") or {}
    events, reasons = [], ["prior_runner_interrupted"]
    previous = run_dir / "observations.events.jsonl"
    if previous.exists() and previous.stat().st_size <= 128 * 1024 * 1024:
        for line in previous.read_text().splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                reasons.append("interrupted_observation_line")
    observation_problems = []
    recovery_directory = run_dir / ("recovery-" + str(len(list(run_dir.glob("recovery-*")))))
    with observation_session(
        telemetry_collector(telemetry), recovery_directory, observation_problems
    ) as collector:
        other_run_pending = (
            profile is not None
            and profile.pending() is not None
            and not _owns_pending_login(profile, run_id)
        )
        host.docker.stop_and_confirm(observed.container_name, run_id)
        settlement_failure = None
        try:
            login_state = _settle_own_login(run_id, profile, host, lambda: candidate)
        except LoginInUseError:
            raise
        except Exception as error:  # noqa: BLE001 -- the recovered record is still retained and published.
            settlement_failure = error
            observed.observation_errors.append("login_settlement_pending")
        else:
            if login_state is not None:
                observed.login_state = login_state
        host.docker.cleanup_run(observed.container_name, run_id)
        if profile:
            # Only journals attributed to this run are read: another run's native state
            # belongs to that run's own evidence, never harvested here.
            preserved = run_dir / "host" / NATIVE_PRESERVED
            if preserved.is_dir():
                collector.harvest_native(preserved)
            elif other_run_pending:
                collector.mark_incomplete("native_state_belongs_to_other_run")
        observed.workspace_stopped = True
        try:
            collector.finalize(exit_kind="interrupted")
        except Exception:  # noqa: BLE001 -- authentication is settled even if observation writing fails.
            observation_problems.append("measurement_finalization_failed")
        measurements = summarize_events(
            [*events, *collector.events],
            exit_kind="interrupted",
            collection_reasons=[*reasons, *collector.reasons],
            adapter=telemetry.get("adapter", "codex"),
        )
    if observation_problems:
        observed.observation_errors.extend(observation_problems)
        mark_observation_problems(measurements, observation_problems)
    preserved = run_dir / "host" / NATIVE_PRESERVED
    measurements["subscription_usage"] = subscription_usage(
        usage_provider(inputs.get("login"), telemetry.get("adapter", "codex")),
        codex=codex_usage(preserved) if preserved.is_dir() else None,
        stdout=run_dir / "host" / "stdout.log",
    )
    snapshots = WorkspaceSnapshots(
        run_dir / "workspace", run_dir, import_probe=grader.engine_health
    )
    try:
        snapshots.entries = json.loads((run_dir / "snapshots.json").read_text())
    except (OSError, ValueError):
        snapshots.entries = []
    previous_selection = run_dir / "grading-source.json"
    grading_failure = None
    try:
        if (
            previous_record is not None
            or previous_selection.exists()
            or (run_dir / "workspace_final").exists()
        ):
            selection = snapshots.select(
                final_name=recovery_directory.name + "/workspace_final",
                manifest_name=recovery_directory.name + "/grading-source.json",
            )
        else:
            selection = snapshots.select()
        scores = missing_scores("no_usable_recovered_workspace")
    except GraderError as error:
        selection, grading_failure = None, error
        scores = missing_scores("grading_container_failed:" + error.reason)
    metadata = {
        "run_date": inputs["started_at"],
        "benchmark_input": inputs.get(
            "staged_input",
            (
                previous_record.run_metadata["benchmark_input"]
                if previous_record
                else inputs["benchmark_identity"]
            ),
        ),
        "candidate_definition": candidate.definition,
        "login_profile": inputs["login"],
        "execution": observed.to_dict(),
        "grading_source": selection,
        "grading_isolation": grader.isolation(),
        "measurements": measurements,
        "git_history": retain_git_history(run_dir / "workspace", run_dir),
    }
    if "test_toolchain" in inputs:
        # Recovery never relaunches the candidate; the toolchain is the one the run started with.
        metadata["test_toolchain"] = inputs["test_toolchain"]
    if "provenance" in inputs:
        # Where and from what the run was launched, not where it was recovered.
        metadata["provenance"] = inputs["provenance"]
    if benchmark.identity != inputs["benchmark_identity"]:
        scores = missing_scores("benchmark_changed_since_run_started")
    elif selection and selection["selected"]:
        try:
            metadata["grading_inputs"] = grading_inputs(benchmark)
            baseline = baseline_reference_grade(
                benchmark,
                evaluate=grader.evaluate_run,
                score=_scores,
                grading_inputs_digest=metadata["grading_inputs"]["digest"],
                grader_image_id=grader.isolation()["grader_image_id"],
                store=BaselineStore(Path(state_root).resolve() / "baseline-grades"),
            )
            evaluated = grader.evaluate_run(
                run_dir, benchmark, workspace_source=run_dir / selection["selected"]
            )
            (run_dir / "evaluation.json").write_bytes(
                canonical(dataclasses.asdict(evaluated)) + b"\n"
            )
            scores = _scores(evaluated, benchmark)
            changed = grading_inputs(benchmark)["digest"] != metadata["grading_inputs"]["digest"]
            combined = combined_regression(scores, evaluated, baseline, inputs_changed=changed)
            if combined is not None:
                metadata["combined_regression"] = combined
        except GraderError as error:
            grading_failure = error
            scores = missing_scores("grading_container_failed:" + error.reason)
        except Exception as error:  # noqa: BLE001 -- recovered implementation and measurements remain useful.
            scores = missing_scores("recovery_grading_failed")
            metadata["collection_error"] = {"stage": "grading", "reason": type(error).__name__}
    if grading_failure is not None:
        metadata["grading_failure"] = grading_failure.to_dict()
    record_id = uuid.uuid4().hex if previous_record is not None else run_id
    pointers = [{"kind": "run-artifacts", "location": str(run_dir)}]
    if previous_record is not None:
        metadata.update(recovery_of=run_id, execution_run_id=run_id)
        pointers.append({"kind": "prior-run-record", "location": str(previous_path)})
    record = KarnRunRecord(
        {
            "schema_version": 2,
            "run_id": record_id,
            "candidate": identity.to_dict(),
            "candidate_hash": identity.hash,
            "benchmark": benchmark.id,
            "budget_seconds": inputs["budget_seconds"],
            "run_metadata": metadata,
            "artifact_pointers": pointers,
        },
        scores,
    )
    record.validate()
    # Retain before publishing, so a retry publishes this same record instead of recovering again.
    if previous_record is None:
        _retain(run_dir / "run-record.json", record)
        unpublished = [record]
    else:
        recovery_directory.mkdir(exist_ok=True)
        _retain(recovery_directory / "run-record.json", record)
        _write_atomically(
            run_dir / "recovery-record.json",
            canonical(
                {
                    "run_id": record_id,
                    "candidate_hash": identity.hash,
                    "recovery_of": run_id,
                    "retained": recovery_directory.name + "/run-record.json",
                }
            ).decode()
            + "\n",
            prefix=".recovery-record-",
        )
        unpublished = [previous_record, record]
    _publish(results_repo, unpublished, record, run_dir)
    if settlement_failure is not None:
        raise LoginSettlementPendingError(_failure_reason(settlement_failure), record)
    return record
