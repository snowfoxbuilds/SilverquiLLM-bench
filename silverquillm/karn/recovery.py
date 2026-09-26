"""Recover a local interrupted run without replaying its model task."""

from __future__ import annotations

import dataclasses
import json
import uuid
from pathlib import Path

from silverquillm.evaluator import evaluate_run
from silverquillm.queue_state import _write_atomically

from .benchmark import load_benchmark
from .definition import KarnError, canonical, load_candidate
from .execution import _scores, login_profile, mark_observation_problems, observation_session
from .grading_inputs import grading_inputs
from .host import DockerHost, HostResult
from .login import PluginProcess, install_plugin, recover_login
from .records import KarnIdentity, KarnRunRecord, missing_scores, read_record, write_record
from .snapshots import WorkspaceSnapshots, retain_git_history


def recover_benchmark(
    *,
    run_id: str,
    spec: dict,
    bench_root: Path,
    results_dir: Path,
    results_repo: Path,
    state_root: Path,
    collector_host=None,
) -> KarnRunRecord:
    from .observations import CodexTelemetryCollector, summarize_events

    run_dir = Path(results_dir) / run_id
    previous_record = None
    previous_path = None
    recovery_link = run_dir / "recovery-record.json"
    if recovery_link.is_file():
        link = json.loads(recovery_link.read_text())
        linked = Path(results_repo) / "results" / link["candidate_hash"] / link["run_id"]
        if linked.is_dir():
            recovered = read_record(linked)
            if (
                recovered.run_metadata.get("recovery_of") == run_id
                and recovered.run_metadata["execution"]["workspace_stopped"]
            ):
                return recovered
    retained_record = run_dir / "run-record.json"
    if retained_record.is_file():
        retained = json.loads(retained_record.read_text())
        completed = KarnRunRecord(retained["manifest"], retained["scores"])
        completed.validate()
        if completed.run_id != run_id:
            raise KarnError("recovery_run_identity_mismatch")
        destination = Path(results_repo) / "results" / completed.candidate.hash / run_id
        if completed.run_metadata["execution"]["workspace_stopped"]:
            if destination.is_dir():
                return read_record(destination)
            write_record(results_repo, completed)
            return completed
    existing = list((Path(results_repo) / "results").glob("*/" + run_id))
    if len(existing) > 1:
        raise KarnError("ambiguous_interrupted_run_record")
    if existing:
        previous_path = existing[0]
        previous_record = read_record(previous_path)
        if previous_record.run_metadata["execution"]["workspace_stopped"]:
            return previous_record
    try:
        inputs = json.loads((run_dir / "run-input.json").read_text())
    except (OSError, ValueError):
        raise KarnError("interrupted_run_input_unavailable:" + run_id) from None
    original = inputs.get("candidate_identity")
    if original is None and previous_record is not None:
        original = previous_record.candidate.to_dict()
    if original is None:
        raise KarnError("original_candidate_identity_unavailable")
    identity = KarnIdentity.from_dict(original)
    candidate = load_candidate(run_dir / "candidate", inputs["construct"])
    retained_identity = KarnIdentity.from_dict({"scheme": "karn-v4", **candidate.identity()})
    if retained_identity != identity or (
        previous_record is not None and previous_record.candidate != identity
    ):
        raise KarnError("retained_definition_identity_mismatch")
    benchmark = load_benchmark(bench_root, inputs["benchmark"])
    host = DockerHost(plugin_cache=Path(state_root) / "plugins")
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
        CodexTelemetryCollector, recovery_directory, observation_problems
    ) as collector:
        if profile:
            with profile.exclusive():
                host.docker.stop_and_confirm(observed.container_name, run_id)
                artifact = next(
                    (p for p in candidate.plugins if p.row["id"] == "karn-codex-login"), None
                )
                if artifact is None:
                    raise KarnError("recovery_login_plugin_missing")
                python = install_plugin(artifact, host.plugin_cache)
                with PluginProcess(artifact, python, profile) as plugin:
                    if (profile.state / "work").is_dir():
                        collector.harvest_native(profile.state / "work")
                    recover_login(
                        profile,
                        plugin,
                        host.docker.stop_and_confirm,
                        cleanup=host.docker.cleanup_run,
                    )
                    observed.login_state = plugin.status()
                host.docker.cleanup_run(observed.container_name, run_id)
        else:
            host.docker.stop_and_confirm(observed.container_name, run_id)
            host.docker.cleanup_run(observed.container_name, run_id)
        observed.workspace_stopped = True
        try:
            collector.finalize(exit_kind="interrupted")
        except Exception:  # noqa: BLE001 -- authentication is settled even if observation writing fails.
            observation_problems.append("measurement_finalization_failed")
        measurements = summarize_events(
            [*events, *collector.events],
            exit_kind="interrupted",
            collection_reasons=[*reasons, *collector.reasons],
        )
    if observation_problems:
        observed.observation_errors.extend(observation_problems)
        mark_observation_problems(measurements, observation_problems)
    snapshots = WorkspaceSnapshots(run_dir / "workspace", run_dir)
    try:
        snapshots.entries = json.loads((run_dir / "snapshots.json").read_text())
    except (OSError, ValueError):
        snapshots.entries = []
    previous_selection = run_dir / "grading-source.json"
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
        "measurements": measurements,
        "git_history": retain_git_history(run_dir / "workspace", run_dir),
    }
    if benchmark.identity != inputs["benchmark_identity"]:
        scores = missing_scores("benchmark_changed_since_run_started")
    elif selection["selected"]:
        try:
            metadata["grading_inputs"] = grading_inputs(benchmark)
            evaluated = evaluate_run(
                run_dir, benchmark, workspace_source=run_dir / selection["selected"]
            )
            (run_dir / "evaluation.json").write_bytes(
                canonical(dataclasses.asdict(evaluated)) + b"\n"
            )
            scores = _scores(evaluated, benchmark)
        except Exception as error:  # noqa: BLE001 -- recovered implementation and measurements remain useful.
            scores = missing_scores("recovery_grading_failed")
            metadata["collection_error"] = {"stage": "grading", "reason": type(error).__name__}
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
    if previous_record is None:
        _write_atomically(
            run_dir / "run-record.json",
            canonical({"manifest": record.manifest, "scores": scores}).decode() + "\n",
            prefix=".run-record-",
        )
    write_record(results_repo, record)
    if previous_record is not None:
        _write_atomically(
            recovery_link,
            canonical(
                {"run_id": record_id, "candidate_hash": identity.hash, "recovery_of": run_id}
            ).decode()
            + "\n",
            prefix=".recovery-record-",
        )
    return record
