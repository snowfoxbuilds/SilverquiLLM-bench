"""Interruption, recovery ownership, and contention across the Karn run lifecycle."""

from __future__ import annotations

import base64
import json
import os
import shutil
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from silverquillm.karn import recovery
from silverquillm.karn.batching import KarnScheduler
from silverquillm.karn.definition import KarnError, canonical, digest, load_candidate
from silverquillm.karn.execution import run_benchmark
from silverquillm.karn.grader import ContainerGrader
from silverquillm.karn.host import DockerHost
from silverquillm.karn.login import NATIVE_PRESERVED, LoginProfile
from silverquillm.karn.records import RecordWritePendingError, write_record
from silverquillm.results_repo import RunRecordExistsError, iter_run_records

from .grader_fixtures import local_grader
from .test_karn_execution import FixtureHost, benchmark_data, options
from .test_karn_host import FIXTURES, FakeDocker, make_candidate

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _grade_without_docker(request, monkeypatch):
    """Runs, schedulers and recoveries built inside these tests grade through the local stand-in."""
    if request.node.get_closest_marker("integration"):
        return
    monkeypatch.setattr(
        ContainerGrader, "from_image", classmethod(lambda cls, reference=None, **kw: local_grader(**kw))
    )


def batch(directory: Path, entries: int = 2) -> Path:
    directory.mkdir()
    spec = '[[runs]]\nbuild_output="fixture"\nconstruct="bare"\nbenchmark="example"\n'
    (directory / "trial.toml").write_text('format="karn-v4"\n' + spec * entries)
    return directory


def completed(**kwargs):
    return SimpleNamespace(
        run_id=kwargs["run_id"],
        run_metadata={"execution": {"status": "completed"}},
        candidate=SimpleNamespace(to_dict=dict),
    )


def scheduler(tmp_path, directory, **changes):
    return KarnScheduler(
        directory,
        bench_root=tmp_path,
        results_dir=tmp_path / "runs",
        results_repo=tmp_path / "records",
        state_root=tmp_path / "state",
        replay_without_state=["trial"],
        **changes,
    )


@pytest.mark.parametrize("created_run_directory", [True, False])
def test_interrupt_before_run_input_fails_the_row_and_the_batch_continues(
    tmp_path, monkeypatch, created_run_directory
):
    directory = batch(tmp_path / "batches")

    def interrupted(**kwargs):
        if created_run_directory:
            (kwargs["results_dir"] / kwargs["run_id"]).mkdir(parents=True)
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        scheduler(tmp_path, directory, executor=interrupted).run_until_idle()
    state = json.loads((directory / "state/trial.json").read_text())
    assert [row["status"] for row in state["runs"]] == ["running"]
    abandoned = state["runs"][0]["run_id"]

    docker = FakeDocker()
    monkeypatch.setattr(
        recovery, "DockerHost", lambda **kwargs: SimpleNamespace(docker=docker, plugin_cache=None)
    )
    executed = []

    def execute(**kwargs):
        executed.append(kwargs["run_id"])
        return completed(**kwargs)

    assert scheduler(tmp_path, directory, executor=execute).run_until_idle() == 1
    state = json.loads((directory / "state/trial.json").read_text())
    assert [(row["status"], row.get("error")) for row in state["runs"]] == [
        ("failed", "interrupted_before_launch"),
        ("done", None),
    ]
    assert ("cleanup", "sq-run-" + abandoned, abandoned) in docker.commands
    assert executed == [state["runs"][1]["run_id"]]


def test_login_contention_defers_the_batch_entry_instead_of_consuming_it(tmp_path):
    directory = batch(tmp_path / "batches", entries=1)
    opts = options(tmp_path / "fixture")
    profile = LoginProfile(tmp_path / "state/logins/shared", "shared")
    (directory / "trial.toml").write_text(
        'format="karn-v4"\n[[runs]]\nbuild_output='
        + json.dumps(str(opts["build_output"]))
        + '\nconstruct="bare"\nbenchmark="example"\nlogin="shared"\n'
    )
    runner = scheduler(
        opts["bench_root"],
        directory,
        executor=lambda **kwargs: run_benchmark(**kwargs, host=FixtureHost()),
    )
    runner.options["state_root"] = (tmp_path / "state").resolve()
    with profile.exclusive():
        assert runner.run_until_idle() == 0
    state = json.loads((directory / "state/trial.json").read_text())
    assert state["runs"] == []
    assert any("login_in_use" in warning for warning in runner.warnings)
    assert not (opts["bench_root"] / "runs").exists()
    assert runner.run_until_idle() == 1
    state = json.loads((directory / "state/trial.json").read_text())
    assert [row["status"] for row in state["runs"]] == ["done"]


def test_direct_run_refuses_a_busy_login_before_creating_evidence(tmp_path):
    opts = options(tmp_path)
    profile = LoginProfile(Path(opts["state_root"]).resolve() / "logins/shared", "shared")
    with profile.exclusive(), pytest.raises(KarnError, match="login_in_use"):
        run_benchmark(**opts, login="shared")
    assert not Path(opts["results_dir"]).exists()


def test_record_write_times_out_and_the_scheduler_retries_it(tmp_path, monkeypatch):
    import fcntl

    from silverquillm.karn import records

    opts = options(tmp_path)
    monkeypatch.setattr(records, "RECORD_LOCK_SECONDS", 0.2)
    monkeypatch.setattr(
        records.write_record,
        "__kwdefaults__",
        {"lock_seconds": 0.2},
    )
    results = Path(opts["results_repo"]) / "results"
    results.mkdir(parents=True)
    holder = os.open(results, os.O_RDONLY | os.O_DIRECTORY)
    fcntl.flock(holder, fcntl.LOCK_EX)
    try:
        with pytest.raises(RecordWritePendingError) as pending:
            run_benchmark(**opts, run_id="pending")
    finally:
        os.close(holder)
    assert pending.value.record.run_id == "pending"
    assert (Path(opts["results_dir"]) / "pending/run-record.json").is_file()
    assert not list(iter_run_records(opts["results_repo"]))
    assert not any(path.name.startswith(".") for path in Path(opts["results_repo"]).iterdir())
    written = recovery.recover_benchmark(
        run_id="pending",
        spec={},
        **{key: opts[key] for key in ("bench_root", "results_dir", "results_repo", "state_root")},
    )
    assert written.run_id == "pending"
    assert [record.run_id for _, record in iter_run_records(opts["results_repo"])] == ["pending"]


def test_scheduler_marks_and_later_writes_a_pending_record(tmp_path, monkeypatch):
    directory = batch(tmp_path / "batches", entries=1)
    record = SimpleNamespace(
        run_id="x",
        run_metadata={"execution": {"status": "completed"}},
        candidate=SimpleNamespace(to_dict=dict),
    )

    def pending(**kwargs):
        raise RecordWritePendingError(record)

    scheduler(tmp_path, directory, executor=pending).run_until_idle()
    state = json.loads((directory / "state/trial.json").read_text())
    assert state["runs"][0]["record_write_pending"] is True
    assert state["runs"][0]["status"] == "done"
    retried = []
    scheduler(
        tmp_path,
        directory,
        executor=pending,
        recoverer=lambda **kwargs: retried.append(kwargs["run_id"]),
    ).run_until_idle()
    state = json.loads((directory / "state/trial.json").read_text())
    assert retried == [state["runs"][0]["run_id"]]
    assert "record_write_pending" not in state["runs"][0]
    assert "error" not in state["runs"][0]


def test_record_lock_leaves_no_file_in_the_results_repository(tmp_path):
    record = run_benchmark(**options(tmp_path))
    repository = tmp_path / "records"
    assert sorted(path.name for path in repository.iterdir()) == ["results"]
    assert sorted(path.name for path in (repository / "results").iterdir()) == [
        record.candidate.hash
    ]
    with pytest.raises(RunRecordExistsError):
        write_record(repository, record, lock_seconds=0.1)


# ---- native state ownership -------------------------------------------------------------


def login_candidate(tmp_path):
    candidate = make_candidate(tmp_path)
    shutil.copytree(FIXTURES / "login-build/plugins", candidate.build_output / "plugins")
    manifest = json.loads(
        (candidate.build_output / "plugins/karn-codex-login-0.1.0/install.json").read_text()
    )["manifest"]
    candidate.runtime["plugins"] = [
        {
            "id": manifest["id"],
            "version": manifest["version"],
            "source": "catalog",
            "artifact": digest(canonical(manifest, ascii_only=True)),
        }
    ]
    candidate.definition_path.write_bytes(canonical(candidate.definition))
    return load_candidate(candidate.build_output, "bare", image_inspector=lambda ref: {"Id": ref})


def enroll(profile):
    auth = canonical(
        {
            "tokens": {
                key: "synthetic-" + key
                for key in ("access_token", "refresh_token", "id_token", "account_id")
            }
        }
    )
    profile.set_secret(
        "login." + profile.name,
        canonical(
            {
                "format": 1,
                "revision": "a" * 32,
                "files": {"auth.json": base64.b64encode(auth).decode()},
            }
        ).decode(),
    )


class SessionDocker(FakeDocker):
    """Writes one native rollout, tagged with its run, into the mounted native home."""

    def command(self, *args, **kwargs):
        if args[0] == "create":
            self.native = next(
                part.split(",")[1].removeprefix("src=")
                for part in args
                if isinstance(part, str) and part.endswith("dst=/native")
            )
            self.run_id = next(
                part.split("=", 1)[1] for part in args if str(part).startswith("org.silverquillm")
            )
        if args[0] == "start":
            sessions = Path(self.native) / "sessions"
            sessions.mkdir(exist_ok=True)
            (sessions / f"rollout-{self.run_id}.jsonl").write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "timestamp": "2026-09-26T00:00:00Z",
                        "payload": {"id": "thread-" + self.run_id, "cli_version": "0.153.4"},
                    }
                )
                + "\n"
            )
        return super().command(*args, **kwargs)


class DyingHost(DockerHost):
    """Emulates the runner process dying after launch: nothing after the start runs."""

    def _finish(self, *args):
        pass


def die_after_start(host):
    original = host.docker.command

    def command(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[0] == "start":
            raise SystemExit(137)
        return result

    host.docker.command = command
    return host


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13")
def test_recovery_never_attributes_another_runs_native_sessions(tmp_path, monkeypatch):
    candidate = login_candidate(tmp_path)
    state = (tmp_path / "state").resolve()
    profile = LoginProfile(state / "logins/shared", "shared")
    enroll(profile)
    common = {
        "build_output": candidate.build_output,
        "construct": "bare",
        "benchmark_id": "example",
        "bench_root": benchmark_data(tmp_path / "data"),
        "results_dir": tmp_path / "runs",
        "results_repo": tmp_path / "records",
        "state_root": state,
        "login": "shared",
    }

    def host():
        return die_after_start(
            DyingHost(
                docker=SessionDocker(), plugin_cache=state / "plugins", plugin_python=sys.executable
            )
        )

    for run_id in ("run-a", "run-b"):
        with pytest.raises(SystemExit):
            run_benchmark(**common, run_id=run_id, host=host())
    runs = (tmp_path / "runs").resolve()
    # Starting B settled A's stale login, preserving A's journal into A's own evidence first.
    assert (runs / "run-a/host" / NATIVE_PRESERVED / "sessions/rollout-run-a.jsonl").is_file()
    assert profile.pending()["run_id"] == "run-b"

    monkeypatch.setattr(
        recovery,
        "DockerHost",
        lambda **kwargs: DockerHost(docker=FakeDocker(), plugin_cache=state / "plugins"),
    )
    options = {key: common[key] for key in ("bench_root", "results_dir", "results_repo")}
    recovered = {}
    for run_id in ("run-a", "run-b"):
        recovered[run_id] = recovery.recover_benchmark(
            run_id=run_id, spec={}, state_root=state, **options
        )
        events = [
            json.loads(line)
            for line in (runs / run_id / "recovery-0/observations.events.jsonl")
            .read_text()
            .splitlines()
        ]
        assert {event["thread_id"] for event in events} == {"thread-" + run_id}
    assert profile.pending() is None
    assert not (profile.state / "work").exists()
    reasons = recovered["run-a"].run_metadata["measurements"]["usage"]["reasons"]
    assert "native_state_belongs_to_other_run" not in reasons


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13")
def test_recovery_without_its_own_native_state_marks_the_other_runs_ownership(
    tmp_path, monkeypatch
):
    candidate = login_candidate(tmp_path)
    state = (tmp_path / "state").resolve()
    profile = LoginProfile(state / "logins/shared", "shared")
    enroll(profile)
    common = {
        "build_output": candidate.build_output,
        "construct": "bare",
        "benchmark_id": "example",
        "bench_root": benchmark_data(tmp_path / "data"),
        "results_dir": tmp_path / "runs",
        "results_repo": tmp_path / "records",
        "state_root": state,
        "login": "shared",
    }
    for run_id in ("run-a", "run-b"):
        with pytest.raises(SystemExit):
            run_benchmark(
                **common,
                run_id=run_id,
                host=die_after_start(
                    DyingHost(
                        docker=SessionDocker(),
                        plugin_cache=state / "plugins",
                        plugin_python=sys.executable,
                    )
                ),
            )
    # A's evidence was lost after B settled it; A must not borrow B's live state.
    shutil.rmtree((tmp_path / "runs/run-a/host") / NATIVE_PRESERVED)
    monkeypatch.setattr(
        recovery,
        "DockerHost",
        lambda **kwargs: DockerHost(docker=FakeDocker(), plugin_cache=state / "plugins"),
    )
    record = recovery.recover_benchmark(
        run_id="run-a",
        spec={},
        state_root=state,
        **{key: common[key] for key in ("bench_root", "results_dir", "results_repo")},
    )
    events = (tmp_path / "runs/run-a/recovery-0/observations.events.jsonl").read_text()
    assert "thread-run-b" not in events
    assert "native_state_belongs_to_other_run" in json.dumps(record.run_metadata["measurements"])
    assert (tmp_path / "runs/run-b/host" / NATIVE_PRESERVED / "sessions").is_dir()


# ---- direct recovery command --------------------------------------------------------------


class ContainerDocker(FakeDocker):
    def __init__(self, running):
        super().__init__(running=running)
        self.cleaned = []

    def cleanup_run(self, container_name, run_id):
        self.cleaned.append(container_name)
        self.running = False


def killed_direct_run(tmp_path):
    opts = options(tmp_path)

    class Killed(FixtureHost):
        def run(self, *args, **kwargs):
            raise SystemExit(137)

    with pytest.raises(SystemExit):
        run_benchmark(**{**opts, "host": Killed()}, run_id="killed")
    return opts


def invoke_recover(opts, *extra):
    from click.testing import CliRunner

    from silverquillm.cli import main

    return CliRunner().invoke(
        main,
        [
            "recover",
            "killed",
            "--bench-root",
            str(opts["bench_root"]),
            "--results-dir",
            str(opts["results_dir"]),
            "--results-repo",
            str(opts["results_repo"]),
            "--state-root",
            str(opts["state_root"]),
            *extra,
        ],
    )


def test_recover_command_refuses_a_running_container_then_recovers_once(tmp_path, monkeypatch):
    opts = killed_direct_run(tmp_path)
    docker = ContainerDocker(running=True)
    monkeypatch.setattr(
        recovery, "DockerHost", lambda **kwargs: SimpleNamespace(docker=docker, plugin_cache=None)
    )
    refused = invoke_recover(opts)
    assert refused.exit_code == 1 and "run_container_still_running" in refused.output
    assert not list(iter_run_records(opts["results_repo"]))

    # The image is gone: recovery must not inspect or run it.
    from silverquillm.karn import definition

    monkeypatch.setattr(
        definition,
        "inspect_image",
        lambda reference: pytest.fail("recovery inspected the candidate image"),
    )
    first = invoke_recover(opts, "--stop")
    assert first.exit_code == 0, first.output
    report = json.loads(first.output)
    assert report["run_id"] == "killed" and report["execution"] == "interrupted"
    assert docker.stopped and not docker.running
    records = list(iter_run_records(opts["results_repo"]))
    assert [record.run_id for _, record in records] == ["killed"]

    again = invoke_recover(opts, "--stop")
    assert again.exit_code == 0 and json.loads(again.output)["run_id"] == "killed"
    assert len(list(iter_run_records(opts["results_repo"]))) == 1


def test_recover_refuses_a_run_that_is_still_executing(tmp_path):
    from silverquillm.karn.execution import run_lock

    opts = killed_direct_run(tmp_path)
    with (
        run_lock(Path(opts["results_dir"]).resolve() / "killed"),
        pytest.raises(KarnError, match="run_in_progress"),
    ):
        recovery.recover_benchmark(
            run_id="killed",
            spec={},
            **{
                key: opts[key]
                for key in ("bench_root", "results_dir", "results_repo", "state_root")
            },
        )


def test_recover_reports_a_run_that_never_launched(tmp_path, monkeypatch):
    opts = options(tmp_path)
    (Path(opts["results_dir"]) / "killed").mkdir(parents=True)
    docker = ContainerDocker(running=False)
    monkeypatch.setattr(
        recovery, "DockerHost", lambda **kwargs: SimpleNamespace(docker=docker, plugin_cache=None)
    )
    result = invoke_recover(opts)
    assert result.exit_code == 1
    assert json.loads(result.output) == {
        "execution": "interrupted_before_launch",
        "run_id": "killed",
    }


# ---- signals ----------------------------------------------------------------------------

SIGNAL_RUNNER = textwrap.dedent(
    """
    import pathlib, sys, time
    from silverquillm.karn import execution
    from silverquillm.karn.host import HostResult

    marker = pathlib.Path(sys.argv[1])

    class BlockingHost:
        docker = None

        def preflight(self, candidate, budget_seconds):
            pass

        def run(self, candidate, workspace, evidence_dir, prompt, **kwargs):
            evidence_dir.mkdir(parents=True)
            result = HostResult(
                kwargs["run_id"], candidate.identity(), "fixture", str(workspace),
                str(evidence_dir), kwargs["budget_seconds"],
            )
            marker.write_text("started")
            try:
                while True:
                    time.sleep(0.05)
            except KeyboardInterrupt:
                # DockerHost.run stops and confirms the container on this path.
                result.status, result.workspace_stopped = "interrupted", True
                (marker.parent / "stopped").write_text("container stopped")
            kwargs["after_stop"](result, None)
            return result

    execution.DockerHost = lambda **kwargs: BlockingHost()
    from tests.grader_fixtures import local_grader
    execution.ContainerGrader.from_image = classmethod(
        lambda cls, reference=None, **kwargs: local_grader(**kwargs)
    )
    load = execution.load_candidate
    execution.load_candidate = lambda path, construct, **kwargs: load(
        path, construct, image_inspector=lambda reference: {"Id": reference}
    )
    from silverquillm.cli import main

    main(sys.argv[2:])
    """
)


@pytest.mark.parametrize("number", [signal.SIGTERM, signal.SIGHUP])
def test_terminating_signals_take_the_interrupted_path_and_write_a_record(tmp_path, number):
    opts = options(tmp_path)
    marker = tmp_path / "started"
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            SIGNAL_RUNNER,
            str(marker),
            "run",
            "--build-output",
            str(opts["build_output"]),
            "--construct",
            "bare",
            "--benchmark",
            "example",
            "--bench-root",
            str(opts["bench_root"]),
            "--results-dir",
            str(opts["results_dir"]),
            "--results-repo",
            str(opts["results_repo"]),
            "--state-root",
            str(opts["state_root"]),
        ],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + 60
    while not marker.exists():
        assert process.poll() is None, process.communicate()
        assert time.monotonic() < deadline
        time.sleep(0.05)
    process.send_signal(number)
    output, errors = process.communicate(timeout=120)
    assert process.returncode == 130, errors.decode()
    assert (tmp_path / "stopped").read_text() == "container stopped"
    assert json.loads(output)["execution"] == "interrupted"
    records = list(iter_run_records(opts["results_repo"]))
    assert len(records) == 1
    assert records[0][1].run_metadata["execution"]["status"] == "interrupted"


def test_signal_handlers_are_restored_and_repeats_do_not_abort_cleanup():
    from silverquillm.karn.interruption import terminate_as_interrupt

    before = signal.getsignal(signal.SIGTERM)
    cleaned = []
    with pytest.raises(KeyboardInterrupt), terminate_as_interrupt():
        try:
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(1)
        finally:
            os.kill(os.getpid(), signal.SIGTERM)
            cleaned.append(True)
    assert cleaned == [True]
    assert signal.getsignal(signal.SIGTERM) is before


# ---- preflight, telemetry selection, redaction, enrollment paths ---------------------------


class ProbeDocker(FakeDocker):
    def __init__(self, returncode):
        super().__init__()
        self.returncode = returncode

    def command(self, *args, **kwargs):
        self.commands.append(args)
        return SimpleNamespace(returncode=self.returncode, stdout=b"", stderr=b"")


@pytest.mark.parametrize("returncode", [0, 1])
def test_restricted_network_requires_python3_in_the_image_before_launch(tmp_path, returncode):
    candidate = make_candidate(tmp_path, network={"mode": "restricted", "https_hosts": []})
    docker = ProbeDocker(returncode)
    host = DockerHost(docker=docker)
    if returncode:
        with pytest.raises(KarnError, match="restricted_network_requires_python3"):
            host.preflight(candidate, 60)
    else:
        host.preflight(candidate, 60)
    (probe,) = docker.commands
    assert probe[:2] == ("run", "--rm") and "none" in probe and candidate.image_id in probe
    DockerHost(docker=ProbeDocker(1)).preflight(make_candidate(tmp_path / "open"), 60)


def test_run_refuses_an_unusable_host_before_creating_evidence(tmp_path):
    class Refusing(FixtureHost):
        def preflight(self, candidate, budget_seconds):
            raise KarnError("restricted_network_requires_python3")

    opts = options(tmp_path, host=Refusing())
    with pytest.raises(KarnError, match="restricted_network_requires_python3"):
        run_benchmark(**opts)
    assert not Path(opts["results_dir"]).exists()


def test_native_telemetry_is_explicit_with_a_documented_codex_home_fallback(tmp_path):
    from silverquillm.karn.batching import load_batch
    from silverquillm.karn.execution import select_native_telemetry

    plain = make_candidate(tmp_path / "plain")
    native = make_candidate(tmp_path / "native")
    native.runtime["environment"]["CODEX_HOME"] = "/native"
    assert select_native_telemetry(plain, "auto")["enabled"] is False
    assert select_native_telemetry(native, "auto") == {
        "requested": "auto",
        "enabled": True,
        "source": "codex_home_heuristic",
    }
    assert select_native_telemetry(native, "none")["enabled"] is False
    assert select_native_telemetry(native, "codex")["source"] == "operator"
    with pytest.raises(KarnError, match="native_telemetry_requires_codex_home"):
        select_native_telemetry(plain, "codex")
    record = run_benchmark(**options(tmp_path / "run"), native_telemetry="none")
    assert record.run_metadata["native_telemetry"]["requested"] == "none"
    spec = '[[runs]]\nbuild_output="b"\nconstruct="bare"\nbenchmark="example"\n'
    path = tmp_path / "telemetry.toml"
    path.write_text('format="karn-v4"\n' + spec + 'native_telemetry="codex"\n')
    assert load_batch(path)["runs"][0]["native_telemetry"] == "codex"
    path.write_text('format="karn-v4"\n' + spec + 'native_telemetry="always"\n')
    with pytest.raises(KarnError, match="invalid_karn_run_spec"):
        load_batch(path)


def test_log_tail_redacts_a_secret_straddling_the_retention_boundary():
    from silverquillm.karn.docker import redacted_tail

    secret = b"refresh-token-value"
    payload = b"a" * 40 + secret + b"b" * 5
    for maximum in range(len(payload) + 2):
        tail = redacted_tail(payload, maximum, {secret})
        assert len(tail) <= maximum
        assert not any(secret[-size:] in tail for size in range(4, len(secret) + 1))
    assert redacted_tail(payload, 20, {secret}) == b"b" * 5
    assert redacted_tail(payload, 64, {secret}).endswith(b"[REDACTED]" + b"b" * 5)


def test_enrollment_resolves_a_symlinked_state_root(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from silverquillm.cli import main
    from silverquillm.karn import commands

    candidate = login_candidate(tmp_path)
    real = tmp_path / "real-state"
    real.mkdir()
    linked = tmp_path / "linked-state"
    linked.symlink_to(real)
    caches = []

    class Recorder:
        def __init__(self, *, plugin_cache):
            caches.append(plugin_cache)

        def enroll_login(self, profile, artifact):
            return 0

    monkeypatch.setattr(commands, "DockerHost", Recorder)
    monkeypatch.setattr(
        commands,
        "load_candidate",
        lambda path, construct: load_candidate(
            path, construct, image_inspector=lambda ref: {"Id": ref}
        ),
    )
    result = CliRunner().invoke(
        main,
        [
            "login",
            "shared",
            "--build-output",
            str(candidate.build_output),
            "--construct",
            "bare",
            "--state-root",
            str(linked),
        ],
    )
    assert result.exit_code == 0, result.output
    assert caches == [real.resolve() / "plugins"]


@pytest.fixture
def python_image():
    checked = subprocess.run(
        ["docker", "image", "inspect", "python:3.13-slim"], capture_output=True, check=False
    )
    if checked.returncode:
        pytest.skip("requires already available python:3.13-slim; tests do not pull")
    return json.loads(checked.stdout)[0]["Id"]


@pytest.mark.integration
@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13")
def test_real_killed_direct_run_is_recovered_once_by_command(tmp_path, python_image):
    import uuid

    from click.testing import CliRunner

    from silverquillm.cli import main

    candidate = make_candidate(
        tmp_path,
        image=python_image,
        main=[
            "python3",
            "-c",
            "import pathlib, time; pathlib.Path('/workspace/partial.py').write_text('x'); time.sleep(300)",
        ],
    )
    shutil.copytree(FIXTURES / "login-build/plugins", candidate.build_output / "plugins")
    manifest = json.loads(
        (candidate.build_output / "plugins/karn-codex-login-0.1.0/install.json").read_text()
    )["manifest"]
    candidate.runtime["plugins"] = [
        {
            "id": manifest["id"],
            "version": manifest["version"],
            "source": "catalog",
            "artifact": digest(canonical(manifest, ascii_only=True)),
        }
    ]
    candidate.definition_path.write_bytes(canonical(candidate.definition))
    state = (tmp_path / "state").resolve()
    profile = LoginProfile(state / "logins/shared", "shared")
    enroll(profile)
    run_id = "killed-" + uuid.uuid4().hex[:12]
    name = "sq-run-" + run_id
    opts = {
        "bench_root": benchmark_data(tmp_path / "data"),
        "results_dir": tmp_path / "runs",
        "results_repo": tmp_path / "records",
        "state_root": state,
    }
    try:
        with pytest.raises(SystemExit):
            run_benchmark(
                **opts,
                build_output=candidate.build_output,
                construct="bare",
                benchmark_id="example",
                login="shared",
                budget_seconds=300,
                run_id=run_id,
                host=die_after_start(
                    DyingHost(plugin_cache=state / "plugins", plugin_python=sys.executable)
                ),
            )
        inspected = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", name],
            capture_output=True,
            text=True,
            check=False,
        )
        assert inspected.stdout.strip() == "true"
        assert profile.pending()["run_id"] == run_id

        def recover(*extra):
            arguments = ["recover", run_id, *extra]
            for key, value in opts.items():
                arguments += ["--" + key.replace("_", "-"), str(value)]
            return CliRunner().invoke(main, arguments)

        refused = recover()
        assert refused.exit_code == 1 and "run_container_still_running" in refused.output
        first = recover("--stop")
        assert first.exit_code == 0, first.output
        assert json.loads(first.output)["run_id"] == run_id
        gone = subprocess.run(["docker", "inspect", name], capture_output=True, check=False)
        assert gone.returncode != 0
        assert profile.pending() is None and not (profile.state / "work").exists()
        second = recover("--stop")
        assert second.exit_code == 0 and json.loads(second.output)["run_id"] == run_id
        assert [record.run_id for _, record in iter_run_records(opts["results_repo"])] == [run_id]
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)


def test_login_is_released_before_grading(tmp_path):
    from silverquillm.evaluator import FullEvalResult

    opts = options(tmp_path)
    profile = LoginProfile(Path(opts["state_root"]).resolve() / "logins/shared", "shared")
    acquired = []

    def evaluator(*args, **kwargs):
        with profile.exclusive():
            acquired.append(True)
        return FullEvalResult()

    run_benchmark(**opts, login="shared", evaluator=evaluator)
    assert acquired == [True]
