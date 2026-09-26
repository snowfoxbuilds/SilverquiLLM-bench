"""One data-collection lifecycle shared by direct runs and batches."""

from __future__ import annotations

import contextlib
import dataclasses
import fcntl
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from silverquillm.queue_state import _write_atomically

from .benchmark import load_benchmark, stage_benchmark
from .definition import KarnError, canonical, load_candidate
from .grader import DEFAULT_GRADER_IMAGE, DEFAULT_GRADING_TIMEOUT, ContainerGrader, GraderError
from .grading_inputs import grading_inputs
from .host import DEFAULT_BUDGET_SECONDS, DockerHost, HostResult
from .login import LoginProfile
from .records import KarnIdentity, KarnRunRecord, missing_scores, write_record
from .snapshots import WorkspaceSnapshots, retain_git_history


@contextlib.contextmanager
def observation_session(factory, directory: Path, problems: list[str], **options):
    collector = factory(directory, **options)
    collector.__enter__()
    try:
        yield collector
    finally:
        try:
            collector.__exit__(*sys.exc_info())
        except Exception:  # noqa: BLE001 -- observation teardown cannot erase stopped implementation evidence.
            problems.append("collector_teardown_failed")


def mark_observation_problems(measurements: dict, problems: list[str]) -> None:
    fields = [
        *measurements.get("agent_turns", {}).values(),
        measurements.get("usage"),
        measurements.get("estimated_cost"),
    ]
    for field in fields:
        if isinstance(field, dict):
            field["reasons"] = sorted(set(field.get("reasons", [])) | set(problems))
            field["completeness"] = "missing" if field.get("value") is None else "partial"


NATIVE_TELEMETRY = ("auto", "codex", "none")


def select_native_telemetry(candidate, requested: str) -> dict:
    """Native Codex journals and the OTel relay, chosen by the operator or batch spec.

    The v4 Construct Definition has no telemetry field, so this is bench-side configuration;
    ``auto`` keeps the documented fallback of detecting a declared ``CODEX_HOME``.
    """
    if requested not in NATIVE_TELEMETRY:
        raise KarnError("invalid_native_telemetry")
    declared = "CODEX_HOME" in candidate.runtime["environment"]
    if requested == "codex" and not declared:
        raise KarnError("native_telemetry_requires_codex_home")
    return {
        "requested": requested,
        "enabled": declared if requested == "auto" else requested == "codex",
        "source": "codex_home_heuristic" if requested == "auto" else "operator",
    }


@contextlib.contextmanager
def run_lock(run_dir: Path):
    """Held while a process executes or recovers a run, so recovery never races a live runner."""
    descriptor = os.open(run_dir / ".runner.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise KarnError("run_in_progress") from None
        yield
    finally:
        os.close(descriptor)


def login_profile(state_root: Path, name: str | None) -> LoginProfile | None:
    if name is None:
        return None
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name):
        raise KarnError("invalid_login_profile_name")
    return LoginProfile(Path(state_root).resolve() / "logins" / name, name)


def collector_address() -> str:
    try:
        address = socket.gethostbyname(socket.gethostname())
        if not ipaddress.ip_address(address).is_loopback:
            return address
    except (OSError, ValueError):
        pass
    result = subprocess.run(
        ["docker", "network", "inspect", "bridge"], capture_output=True, timeout=30, check=False
    )
    try:
        return json.loads(result.stdout)[0]["IPAM"]["Config"][0]["Gateway"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise KarnError("collector_host_required") from None


def _scores(evaluated, benchmark) -> dict:
    result = missing_scores("grading_did_not_execute")
    for name, cards in (
        ("card_correctness", evaluated.sos_results),
        ("fdn_regression", evaluated.fdn_results),
    ):
        if name == "card_correctness":
            expected = {
                f"{benchmark.target_set}_{int(c) if c.isdigit() else c}" for c in benchmark.cards
            }
        else:
            directory = benchmark.root / "workspace/cards/fdn"
            expected = (
                {path.name for path in directory.iterdir() if (path / "card_spec.json").is_file()}
                if directory.is_dir()
                else set()
            )

        def case_counts(value):
            if value.test_nodes:
                executed = [
                    node
                    for node in value.test_nodes
                    if "::" in node["test_node"] and "<collection-error>" not in node["test_node"]
                ]
                return sum(node["outcome"] == "pass" for node in executed), len(executed)
            return value.tests_passed, value.tests_total

        counts = {key: case_counts(value) for key, value in cards.items()}
        observed = {key for key, (_, total) in counts.items() if total > 0}
        total = sum(total for _, total in counts.values())
        passed = sum(passed for passed, _ in counts.values())
        missing = sorted(expected - observed)
        reasons = sorted(
            {
                error
                for value in cards.values()
                for error in value.errors
                if not error.startswith("FAILED ")
            }
        )
        if missing:
            reasons.append("some_cards_have_no_executed_audited_tests")
        result[name] = {
            "evaluated": total > 0,
            "complete": bool(total) and not reasons,
            "pass_rate": passed / total if total else None,
            "tests_passed": passed if total else None,
            "tests_total": total or None,
            "missing_reasons": reasons or ([] if total else ["no_executed_tests"]),
            "coverage": {
                "population_cards": sorted(expected),
                "evaluated_cards": sorted(observed),
                "uncovered_cards": missing,
            },
            "cards": {key: dataclasses.asdict(value) for key, value in cards.items()},
        }
    engine = evaluated.engine_result
    result["engine_regression"] = {
        "evaluated": engine.tests_total > 0,
        "complete": engine.tests_total > 0
        and not any(not error.startswith("FAILED ") for error in engine.errors),
        "pass_rate": engine.pass_rate if engine.tests_total else None,
        "tests_passed": engine.tests_passed if engine.tests_total else None,
        "tests_total": engine.tests_total or None,
        "missing_reasons": [error for error in engine.errors if not error.startswith("FAILED ")]
        or ([] if engine.tests_total else ["no_executed_engine_tests"]),
        "diagnostics": engine.errors,
    }
    return result


def run_benchmark(
    *,
    build_output: Path,
    construct: str,
    benchmark_id: str,
    bench_root: Path,
    results_dir: Path,
    results_repo: Path,
    state_root: Path,
    login: str | None = None,
    budget_seconds: int = DEFAULT_BUDGET_SECONDS,
    run_id: str | None = None,
    snapshot_seconds: float = 60,
    collector_host: str | None = None,
    host: DockerHost | None = None,
    collector_factory=None,
    grader_image: str = DEFAULT_GRADER_IMAGE,
    grading_timeout: int = DEFAULT_GRADING_TIMEOUT,
    grader: ContainerGrader | None = None,
    evaluator=None,
    native_telemetry: str = "auto",
) -> KarnRunRecord:
    """Refuse what cannot run before any evidence exists, then collect under both locks.

    A busy login raises :class:`LoginInUseError` without creating a run directory, so a
    batch can defer the entry instead of consuming it.
    """
    candidate = load_candidate(
        build_output, construct, **({"image_inspector": host.docker.inspect_image} if host else {})
    )
    benchmark = load_benchmark(bench_root, benchmark_id)
    selected_login = login_profile(state_root, login)
    grader = grader or ContainerGrader.from_image(grader_image, timeout=grading_timeout)
    evaluator = evaluator or grader.evaluate_run
    host = host or DockerHost(plugin_cache=Path(state_root).resolve() / "plugins")
    telemetry = select_native_telemetry(candidate, native_telemetry)
    host.preflight(candidate, budget_seconds)
    run_id = run_id or uuid.uuid4().hex
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", run_id):
        raise KarnError("invalid_run_id")
    run_dir = Path(results_dir).resolve() / run_id
    with contextlib.ExitStack() as held:
        login_hold = held.enter_context(contextlib.ExitStack())
        if selected_login is not None:
            login_hold.enter_context(selected_login.exclusive())
        run_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
        held.enter_context(run_lock(run_dir))
        return _collect(
            candidate=candidate,
            construct=construct,
            benchmark=benchmark,
            login=login,
            selected_login=selected_login,
            host=host,
            telemetry=telemetry,
            run_id=run_id,
            run_dir=run_dir,
            results_repo=results_repo,
            budget_seconds=budget_seconds,
            snapshot_seconds=snapshot_seconds,
            collector_host=collector_host,
            collector_factory=collector_factory,
            grader=grader,
            evaluator=evaluator,
            login_hold=login_hold,
        )


def _collect(
    *,
    candidate,
    construct,
    benchmark,
    login,
    selected_login,
    host,
    telemetry,
    run_id,
    run_dir,
    results_repo,
    budget_seconds,
    snapshot_seconds,
    collector_host,
    collector_factory,
    grader,
    evaluator,
    login_hold,
) -> KarnRunRecord:
    from .observations import CodexTelemetryCollector

    start = datetime.now(UTC).isoformat()
    artifact_dir = run_dir / "candidate"
    artifact_dir.mkdir()
    selected_dir = artifact_dir / "constructs" / construct
    selected_dir.mkdir(parents=True)
    (selected_dir / "definition.json").write_bytes(candidate.canonical_bytes + b"\n")
    for artifact in candidate.plugins:
        destination = artifact_dir / "plugins" / artifact.install_path.parent.name
        shutil.copytree(artifact.install_path.parent, destination)
    identity = KarnIdentity.from_dict({"scheme": "karn-v4", **candidate.identity()})
    run_input = {
        "run_id": run_id,
        "construct": construct,
        "candidate_identity": identity.to_dict(),
        "benchmark": benchmark.id,
        "benchmark_identity": benchmark.identity,
        "login": login,
        "budget_seconds": budget_seconds,
        "native_telemetry": telemetry,
        "started_at": start,
    }
    _write_atomically(
        run_dir / "run-input.json", canonical(run_input).decode() + "\n", prefix=".run-input-"
    )

    workspace = run_dir / "workspace"
    scores = missing_scores("run_not_started")
    metadata = {
        "run_date": start,
        "benchmark_input": benchmark.identity,
        "candidate_definition": candidate.definition,
        "login_profile": login,
        "native_telemetry": telemetry,
        "grading_source": None,
        "grading_isolation": grader.isolation(),
        "measurements": None,
    }
    observed = HostResult(
        run_id,
        candidate.identity(),
        "sq-run-" + run_id,
        str(workspace),
        str(run_dir),
        budget_seconds,
    )
    observation_problems = []
    stage = "staging"
    try:
        prompt, metadata["benchmark_input"] = stage_benchmark(benchmark, workspace)
        run_input["staged_input"] = metadata["benchmark_input"]
        _write_atomically(
            run_dir / "run-input.json", canonical(run_input).decode() + "\n", prefix=".run-input-"
        )
        (run_dir / "prompt.md").write_text(prompt)
        native = telemetry["enabled"]
        factory = collector_factory or CodexTelemetryCollector
        bind = collector_host or (collector_address() if native else "127.0.0.1")
        with observation_session(
            factory, run_dir, observation_problems, bind_host=bind
        ) as collector:
            with WorkspaceSnapshots(
                workspace,
                run_dir,
                import_probe=grader.engine_health,
                interval_seconds=snapshot_seconds,
            ) as snapshots:
                stage = "execution"

                def after_stop(result, native_state):
                    if native_state is not None:
                        collector.harvest_native(native_state)
                    else:
                        collector.mark_incomplete("native_state_unavailable")

                arguments = {}
                if native:
                    arguments = {
                        "runtime_config": lambda network: collector.config_toml(
                            network.telemetry_endpoint
                        ),
                        "collector_endpoint": collector.endpoint,
                    }
                try:
                    observed = host.run(
                        candidate,
                        workspace,
                        run_dir / "host",
                        prompt,
                        run_id=run_id,
                        budget_seconds=budget_seconds,
                        login_profile=selected_login,
                        login_lock_held=selected_login is not None,
                        after_stop=after_stop,
                        **arguments,
                    )
                except (Exception, KeyboardInterrupt) as error:  # noqa: BLE001 -- stop before preserving a host failure.
                    observed.status = (
                        "interrupted" if isinstance(error, KeyboardInterrupt) else "host_failed"
                    )
                    observed.failure_stage = "execution"
                    observed.error = (
                        str(error) if isinstance(error, KarnError) else type(error).__name__
                    )
                    host.docker.stop_and_confirm(observed.container_name, run_id)
                    observed.workspace_stopped = True
                    collector.mark_incomplete("host_execution_failed")
                # The host has harvested the login; grading must not keep it from other runs.
                login_hold.close()
            try:
                metadata["measurements"] = collector.finalize(exit_kind=observed.status)
            except Exception:  # noqa: BLE001 -- measurement failure must not suppress grading.
                from .observations import summarize_events

                metadata["measurements"] = summarize_events(
                    getattr(collector, "events", []),
                    exit_kind=observed.status,
                    collection_reasons=["measurement_finalization_failed"],
                )
        if observed.workspace_stopped:
            stage = "harvest"
            metadata["git_history"] = retain_git_history(workspace, run_dir)
            selection = snapshots.select()
            metadata["grading_source"] = selection
            if selection["selected"]:
                stage = "grading"
                metadata["grading_inputs"] = grading_inputs(benchmark)
                evaluated = evaluator(
                    run_dir, benchmark, workspace_source=run_dir / selection["selected"]
                )
                (run_dir / "evaluation.json").write_bytes(
                    canonical(dataclasses.asdict(evaluated)) + b"\n"
                )
                scores = _scores(evaluated, benchmark)
                after_grading = grading_inputs(benchmark)
                if after_grading["digest"] != metadata["grading_inputs"]["digest"]:
                    metadata["grading_inputs"]["changed_during_grading"] = True
                    metadata["grading_inputs"]["after"] = after_grading
            else:
                scores = missing_scores("no_usable_workspace_or_snapshot")
        else:
            scores = missing_scores("workspace_writers_not_confirmed_stopped")
    except KeyboardInterrupt:
        observed.status, observed.failure_stage, observed.error = (
            "interrupted",
            stage,
            "operator_interruption",
        )
        scores = missing_scores("interrupted_before_grading")
    except GraderError as error:
        metadata["grading_failure"] = error.to_dict()
        scores = missing_scores("grading_container_failed:" + error.reason)
    except Exception as error:  # noqa: BLE001 -- failed collection still produces an immutable observation.
        if stage in ("staging", "execution"):
            observed.status, observed.failure_stage = "host_failed", stage
            observed.error = str(error) if isinstance(error, KarnError) else type(error).__name__
        metadata["collection_error"] = {"stage": stage, "reason": type(error).__name__}
        scores = missing_scores("collection_failed:" + stage)
    if observation_problems:
        observed.observation_errors.extend(observation_problems)
        metadata["observation_errors"] = observation_problems
        if metadata["measurements"] is not None:
            mark_observation_problems(metadata["measurements"], observation_problems)
            _write_atomically(
                run_dir / "observations.json",
                canonical(metadata["measurements"]).decode() + "\n",
                prefix=".observations-",
            )
    metadata["execution"] = observed.to_dict()
    if metadata["measurements"] is None:
        from .observations import summarize_events

        metadata["measurements"] = summarize_events(
            [], exit_kind=observed.status, collection_reasons=["measurement_collection_unavailable"]
        )
    record = KarnRunRecord(
        {
            "schema_version": 2,
            "run_id": run_id,
            "candidate": identity.to_dict(),
            "candidate_hash": identity.hash,
            "benchmark": benchmark.id,
            "budget_seconds": budget_seconds,
            "run_metadata": metadata,
            "artifact_pointers": [
                {"kind": "run-artifacts", "location": str(run_dir)},
                {"kind": "karn-definition", "location": str(selected_dir / "definition.json")},
            ],
        },
        scores,
    )
    record.validate()
    _write_atomically(
        run_dir / "run-record.json",
        canonical({"manifest": record.manifest, "scores": record.scores}).decode() + "\n",
        prefix=".run-record-",
    )
    write_record(results_repo, record)
    return record
