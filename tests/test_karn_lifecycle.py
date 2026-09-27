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
    # B's login and native state stay B's: A's recovery neither settles nor preserves them.
    assert profile.pending()["run_id"] == "run-b"
    assert not (tmp_path / "runs/run-b/host" / NATIVE_PRESERVED).exists()
    assert (profile.state / "work/sessions/rollout-run-b.jsonl").is_file()
    recovery.recover_benchmark(
        run_id="run-b",
        spec={},
        state_root=state,
        **{key: common[key] for key in ("bench_root", "results_dir", "results_repo")},
    )
    assert profile.pending() is None
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


@pytest.mark.parametrize("failure", [RuntimeError("boom"), KarnError("invalid_canonical_json")])
def test_an_unrecoverable_row_fails_and_the_scheduler_continues(tmp_path, failure):
    directory = batch(tmp_path / "batches")

    def interrupted(**kwargs):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        scheduler(tmp_path, directory, executor=interrupted).run_until_idle()

    def broken(**kwargs):
        raise failure

    executed = []

    def execute(**kwargs):
        executed.append(kwargs["run_id"])
        return completed(**kwargs)

    assert scheduler(tmp_path, directory, executor=execute, recoverer=broken).run_until_idle() == 1
    state = json.loads((directory / "state/trial.json").read_text())
    expected = "recovery_failed:" + (str(failure) if isinstance(failure, KarnError) else "RuntimeError")
    assert [(row["status"], row.get("error")) for row in state["runs"]] == [
        ("failed", expected),
        ("done", None),
    ]
    assert executed == [state["runs"][1]["run_id"]]


def test_a_recoverer_interrupt_still_propagates(tmp_path):
    directory = batch(tmp_path / "batches")

    def interrupted(**kwargs):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        scheduler(tmp_path, directory, executor=interrupted).run_until_idle()
    with pytest.raises(KeyboardInterrupt):
        scheduler(tmp_path, directory, recoverer=interrupted).run_until_idle()
    state = json.loads((directory / "state/trial.json").read_text())
    assert [row["status"] for row in state["runs"]] == ["running"]


# ---- authentication settlement on recovery ------------------------------------------------


def published_bytes(results_repo: Path) -> dict:
    return {
        str(path.relative_to(results_repo)): path.read_bytes()
        for path in sorted(Path(results_repo).rglob("*.json"))
    }


class RecoveryDocker(FakeDocker):
    """Recovery must never launch a workload or need the candidate image."""

    def inspect_image(self, reference):
        raise AssertionError("recovery inspected the candidate image")

    def stop_and_confirm(self, name, run_id):
        self.commands.append(("stop", name, run_id))
        super().stop_and_confirm(name, run_id)


def failing_harvest(monkeypatch):
    from silverquillm.karn import login as login_module

    original = login_module.PluginProcess.invoke

    def invoke(self, hook, *args):
        if hook == "after_container_exit":
            raise KarnError("plugin_harvest_failed")
        return original(self, hook, *args)

    monkeypatch.setattr(login_module.PluginProcess, "invoke", invoke)


def harvest_failed_run(tmp_path, *, run_id="run-a", hold_records=False):
    """A completed, stopped run whose login harvest failed, leaving the profile pending."""
    candidate = login_candidate(tmp_path)
    state = (tmp_path / "state").resolve()
    profile = LoginProfile(state / "logins/shared", "shared")
    enroll(profile)
    common = {
        "bench_root": benchmark_data(tmp_path / "data"),
        "results_dir": tmp_path / "runs",
        "results_repo": tmp_path / "records",
        "state_root": state,
    }
    with pytest.MonkeyPatch.context() as patch:
        failing_harvest(patch)
        record = run_benchmark(
            **common,
            build_output=candidate.build_output,
            construct="bare",
            benchmark_id="example",
            login="shared",
            run_id=run_id,
            host=DockerHost(
                docker=SessionDocker(), plugin_cache=state / "plugins", plugin_python=sys.executable
            ),
        )
    assert record.run_metadata["execution"]["workspace_stopped"]
    assert "login_harvest_failed" in record.run_metadata["execution"]["observation_errors"]
    assert profile.pending()["run_id"] == run_id
    return SimpleNamespace(
        candidate=candidate, profile=profile, common=common, record=record, run_id=run_id
    )


def recovery_docker(monkeypatch, state):
    docker = RecoveryDocker()
    monkeypatch.setattr(
        recovery, "DockerHost", lambda **kwargs: DockerHost(docker=docker, plugin_cache=state / "plugins")
    )
    return docker


def recover_run_id(run, run_id=None):
    return recovery.recover_benchmark(run_id=run_id or run.run_id, spec={}, **run.common)


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13")
def test_recovery_settles_a_published_runs_failed_harvest_once_without_replay(
    tmp_path, monkeypatch
):
    run = harvest_failed_run(tmp_path)
    published = published_bytes(run.common["results_repo"])
    docker = recovery_docker(monkeypatch, run.common["state_root"])
    first = recover_run_id(run)
    assert first.run_id == run.run_id and first.manifest == run.record.manifest
    assert run.profile.pending() is None
    assert not (run.profile.state / "work").exists()
    preserved = tmp_path / "runs" / run.run_id / "host" / NATIVE_PRESERVED
    assert (preserved / f"sessions/rollout-{run.run_id}.jsonl").is_file()
    assert published_bytes(run.common["results_repo"]) == published
    assert not {"create", "start"} & {command[0] for command in docker.commands}
    second = recover_run_id(run)
    assert second.manifest == first.manifest
    assert published_bytes(run.common["results_repo"]) == published


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13")
def test_recovery_settles_and_publishes_a_retained_only_record(tmp_path, monkeypatch):
    import fcntl

    from silverquillm.karn import records

    monkeypatch.setattr(records.write_record, "__kwdefaults__", {"lock_seconds": 0.2})
    results = tmp_path / "records/results"
    results.mkdir(parents=True)
    holder = os.open(results, os.O_RDONLY | os.O_DIRECTORY)
    fcntl.flock(holder, fcntl.LOCK_EX)
    try:
        with pytest.raises(RecordWritePendingError):
            harvest_failed_run(tmp_path)
    finally:
        os.close(holder)
    profile = LoginProfile((tmp_path / "state").resolve() / "logins/shared", "shared")
    assert profile.pending()["run_id"] == "run-a"
    assert not list(iter_run_records(tmp_path / "records"))
    recovery_docker(monkeypatch, (tmp_path / "state").resolve())
    retained = json.loads((tmp_path / "runs/run-a/run-record.json").read_text())
    record = recovery.recover_benchmark(
        run_id="run-a",
        spec={},
        bench_root=tmp_path / "data",
        results_dir=tmp_path / "runs",
        results_repo=tmp_path / "records",
        state_root=tmp_path / "state",
    )
    assert record.manifest == retained["manifest"]
    assert [r.run_id for _, r in iter_run_records(tmp_path / "records")] == ["run-a"]
    assert profile.pending() is None


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13")
def test_recovery_uses_the_retained_plugin_after_the_build_and_cache_change(tmp_path, monkeypatch):
    run = harvest_failed_run(tmp_path)
    shutil.rmtree(run.candidate.build_output / "plugins")
    shutil.rmtree(run.common["state_root"] / "plugins")
    recovery_docker(monkeypatch, run.common["state_root"])
    recover_run_id(run)
    assert run.profile.pending() is None


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13")
def test_a_failed_settlement_keeps_the_login_pending_and_is_reported(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from silverquillm.cli import main

    run = harvest_failed_run(tmp_path)
    published = published_bytes(run.common["results_repo"])
    journal = run.profile.pending()
    recovery_docker(monkeypatch, run.common["state_root"])
    with pytest.MonkeyPatch.context() as patch:
        failing_harvest(patch)
        with pytest.raises(recovery.LoginSettlementPendingError) as pending:
            recover_run_id(run)
        arguments = ["recover", run.run_id]
        for key, value in run.common.items():
            arguments += ["--" + key.replace("_", "-"), str(value)]
        reported = CliRunner().invoke(main, arguments)
    assert pending.value.record.manifest == run.record.manifest
    assert "login_harvest_pending" in str(pending.value) or "plugin_harvest_failed" in str(
        pending.value
    )
    assert reported.exit_code == 1 and "login_settlement_pending" in reported.output
    assert run.profile.pending() == journal
    assert published_bytes(run.common["results_repo"]) == published
    # A plugin other than the one this run used is refused, never substituted.
    run.profile.journal({**journal, "plugin_artifact": "sha256:" + "0" * 64})
    with pytest.raises(recovery.LoginSettlementPendingError, match="requires_previous_plugin"):
        recover_run_id(run)
    run.profile.journal(journal)
    recover_run_id(run)
    assert run.profile.pending() is None
    assert published_bytes(run.common["results_repo"]) == published


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13")
def test_a_busy_login_leaves_settlement_pending_without_changing_the_record(
    tmp_path, monkeypatch
):
    run = harvest_failed_run(tmp_path)
    published = published_bytes(run.common["results_repo"])
    journal = run.profile.pending()
    recovery_docker(monkeypatch, run.common["state_root"])
    with (
        run.profile.exclusive(),
        pytest.raises(recovery.LoginSettlementPendingError, match="login_in_use"),
    ):
        recover_run_id(run)
    assert run.profile.pending() == journal
    assert published_bytes(run.common["results_repo"]) == published
    recover_run_id(run)
    assert run.profile.pending() is None


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13")
def test_any_settlement_failure_still_publishes_the_retained_record(
    tmp_path, monkeypatch, held_records
):
    held_records.hold()
    with pytest.raises(RecordWritePendingError):
        harvest_failed_run(tmp_path)
    held_records.release()
    profile = LoginProfile((tmp_path / "state").resolve() / "logins/shared", "shared")
    journal = profile.pending()
    recovery_docker(monkeypatch, (tmp_path / "state").resolve())

    def timed_out(*args, **kwargs):
        raise subprocess.TimeoutExpired("pip", 180)

    monkeypatch.setattr(recovery, "install_plugin", timed_out)
    with pytest.raises(recovery.LoginSettlementPendingError, match="TimeoutExpired") as pending:
        recovery.recover_benchmark(
            run_id="run-a",
            spec={},
            bench_root=tmp_path / "data",
            results_dir=tmp_path / "runs",
            results_repo=tmp_path / "records",
            state_root=tmp_path / "state",
        )
    assert [r.run_id for _, r in iter_run_records(tmp_path / "records")] == ["run-a"]
    assert pending.value.record.run_id == "run-a"
    assert profile.pending() == journal


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13")
def test_a_status_failure_after_settlement_is_not_reported_as_pending(tmp_path, monkeypatch):
    from silverquillm.karn import login as login_module

    run = harvest_failed_run(tmp_path)
    recovery_docker(monkeypatch, run.common["state_root"])

    def unavailable(self):
        raise KarnError("plugin_status_unavailable")

    monkeypatch.setattr(login_module.PluginProcess, "status", unavailable)
    recover_run_id(run)
    assert run.profile.pending() is None


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13")
def test_recovery_leaves_another_runs_pending_login_alone(tmp_path, monkeypatch):
    run = harvest_failed_run(tmp_path)
    recovery_docker(monkeypatch, run.common["state_root"])
    recover_run_id(run)
    with pytest.raises(SystemExit):
        run_benchmark(
            **run.common,
            build_output=run.candidate.build_output,
            construct="bare",
            benchmark_id="example",
            login="shared",
            run_id="run-b",
            host=die_after_start(
                DyingHost(
                    docker=SessionDocker(),
                    plugin_cache=run.common["state_root"] / "plugins",
                    plugin_python=sys.executable,
                )
            ),
        )
    journal = run.profile.pending()
    assert journal["run_id"] == "run-b"
    docker = recovery_docker(monkeypatch, run.common["state_root"])
    recover_run_id(run)
    assert run.profile.pending() == journal
    assert not (tmp_path / "runs/run-b/host" / NATIVE_PRESERVED).exists()
    assert (run.profile.state / "work/sessions/rollout-run-b.jsonl").is_file()
    assert not any(command[1:] == ("sq-run-run-b", "run-b") for command in docker.commands)


# ---- scheduler publication retries --------------------------------------------------------


@pytest.fixture
def held_records(tmp_path, monkeypatch):
    """Take the results lock, as a concurrent writer would, until the test releases it."""
    import fcntl

    from silverquillm.karn import records

    monkeypatch.setattr(records.write_record, "__kwdefaults__", {"lock_seconds": 0.2})
    results = tmp_path / "records/results"
    held = []

    def hold():
        results.mkdir(parents=True, exist_ok=True)
        held.append(os.open(results, os.O_RDONLY | os.O_DIRECTORY))
        fcntl.flock(held[-1], fcntl.LOCK_EX)

    def release():
        os.close(held.pop())

    yield SimpleNamespace(hold=hold, release=release)
    for descriptor in held:
        os.close(descriptor)


class UnstoppedHost(FixtureHost):
    """The workload's writers could not be confirmed stopped, so its record is not final."""

    def run(self, *args, **kwargs):
        result = super().run(*args, **kwargs)
        result.status, result.workspace_stopped = "host_failed", False
        return result


def batch_with(tmp_path, build_output: Path, entries: int = 2) -> Path:
    directory = tmp_path / "batches"
    directory.mkdir()
    spec = (
        "[[runs]]\nbuild_output="
        + json.dumps(str(build_output))
        + '\nconstruct="bare"\nbenchmark="example"\n'
    )
    (directory / "trial.toml").write_text('format="karn-v4"\n' + spec * entries)
    return directory


def batch_scheduler(tmp_path, directory, executor):
    return KarnScheduler(
        directory,
        bench_root=tmp_path / "data",
        results_dir=tmp_path / "runs",
        results_repo=tmp_path / "records",
        state_root=tmp_path / "state",
        replay_without_state=["trial"],
        executor=executor,
    )


def dying_first_entry(host):
    """The first entry's runner dies mid-run, leaving its row running."""

    def execute(**kwargs):
        run_benchmark(**kwargs, host=host)
        raise SystemExit(137)

    return execute


class Killed(FixtureHost):
    def run(self, *args, **kwargs):
        raise SystemExit(137)


@pytest.mark.parametrize("host", [Killed, UnstoppedHost])
def test_scheduler_recovery_under_record_contention_publishes_later_without_replay(
    tmp_path, monkeypatch, held_records, host
):
    opts = options(tmp_path)
    directory = batch_with(tmp_path, opts["build_output"])
    with pytest.raises(SystemExit):
        batch_scheduler(tmp_path, directory, dying_first_entry(host())).run_until_idle()
    state_path = directory / "state/trial.json"
    first = json.loads(state_path.read_text())["runs"][0]
    assert first["status"] == "running"
    held_records.hold()
    monkeypatch.setattr(
        recovery,
        "DockerHost",
        lambda **kwargs: SimpleNamespace(docker=FakeDocker(), plugin_cache=None),
    )
    executed = []

    def execute(**kwargs):
        executed.append(kwargs["run_id"])
        return run_benchmark(**kwargs, host=FixtureHost())

    snapshots = []
    for _ in range(2):  # recovery itself contends, then a later retry fails again
        batch_scheduler(tmp_path, directory, execute).run_until_idle()
        rows = json.loads(state_path.read_text())["runs"]
        assert rows[0]["record_write_pending"] is True
        assert (rows[0]["status"], rows[0]["execution_status"]) == ("failed", "interrupted")
        assert rows[0]["error"] == "prior_runner_interrupted"
        assert rows[0]["execution_run_id"] == first["run_id"]
        snapshots.append(
            (
                rows[0].get("recovery_record"),
                sorted(
                    path.read_bytes()
                    for path in (tmp_path / "runs" / first["run_id"]).rglob("run-record.json")
                ),
            )
        )
    assert snapshots[0] == snapshots[1]
    assert len(executed) == 1 and first["run_id"] not in executed
    assert rows[1]["record_write_pending"] is True
    if host is UnstoppedHost:
        assert rows[0]["recovery_of"] == first["run_id"]
        assert rows[0]["recovery_record"] != first["run_id"]
    before = published_bytes(tmp_path / "records")
    held_records.release()
    (directory / "trial.toml").unlink()  # retries never need the batch file
    batch_scheduler(tmp_path, directory, execute).run_until_idle()
    rows = json.loads(state_path.read_text())["runs"]
    assert not any("record_write_pending" in row for row in rows)
    assert rows[0]["error"] == "prior_runner_interrupted" and "error" not in rows[1]
    assert len(executed) == 1
    published = {r.run_id: r for _, r in iter_run_records(tmp_path / "records")}
    recovered = published[rows[0].get("recovery_record", first["run_id"])]
    assert recovered.run_metadata["execution"]["status"] == "interrupted"
    assert rows[1]["run_id"] in published
    retained = [
        json.loads(path.read_text())["manifest"]
        for path in (tmp_path / "runs" / first["run_id"]).rglob("run-record.json")
        if json.loads(path.read_text())["manifest"]["run_id"] == recovered.run_id
    ]
    assert retained == [recovered.manifest]
    after = published_bytes(tmp_path / "records")
    assert all(after[key] == value for key, value in before.items())


def test_scheduler_retries_login_settlement_without_replay(tmp_path):
    directory = batch(tmp_path / "batches", entries=1)
    harvest_failed = SimpleNamespace(
        run_id="x",
        run_metadata={
            "execution": {"status": "completed", "observation_errors": ["login_harvest_failed"]}
        },
        candidate=SimpleNamespace(to_dict=dict),
    )
    executed = []

    def execute(**kwargs):
        executed.append(kwargs["run_id"])
        return harvest_failed

    scheduler(tmp_path, directory, executor=execute).run_until_idle()
    state = json.loads((directory / "state/trial.json").read_text())
    assert state["runs"][0]["login_settlement_pending"] == "login_harvest_failed"
    assert state["runs"][0]["status"] == "done"

    def still_pending(**kwargs):
        raise recovery.LoginSettlementPendingError("login_harvest_pending", harvest_failed)

    scheduler(tmp_path, directory, executor=execute, recoverer=still_pending).run_until_idle()
    state = json.loads((directory / "state/trial.json").read_text())
    assert state["runs"][0]["login_settlement_pending"] == (
        "login_settlement_pending:login_harvest_pending"
    )
    settled = []
    scheduler(
        tmp_path,
        directory,
        executor=execute,
        recoverer=lambda **kwargs: settled.append(kwargs["run_id"]),
    ).run_until_idle()
    state = json.loads((directory / "state/trial.json").read_text())
    assert "login_settlement_pending" not in state["runs"][0]
    assert settled == [state["runs"][0]["run_id"]] and len(executed) == 1


def test_a_crash_between_retaining_and_linking_republishes_the_same_record(
    tmp_path, monkeypatch, held_records
):
    opts = options(tmp_path)
    run_benchmark(**{**opts, "host": UnstoppedHost()}, run_id="unstopped")
    monkeypatch.setattr(
        recovery,
        "DockerHost",
        lambda **kwargs: SimpleNamespace(docker=FakeDocker(), plugin_cache=None),
    )
    common = {key: opts[key] for key in ("bench_root", "results_dir", "results_repo", "state_root")}
    written = recovery._write_atomically

    def crash_on_link(path, *args, **kwargs):
        if Path(path).name == "recovery-record.json":
            raise KeyboardInterrupt
        return written(path, *args, **kwargs)

    monkeypatch.setattr(recovery, "_write_atomically", crash_on_link)
    with pytest.raises(KeyboardInterrupt):
        recovery.recover_benchmark(run_id="unstopped", spec={}, **common)
    monkeypatch.setattr(recovery, "_write_atomically", written)
    [retained] = (tmp_path / "runs/unstopped").glob("recovery-*/run-record.json")
    retained_id = json.loads(retained.read_text())["manifest"]["run_id"]
    record = recovery.recover_benchmark(run_id="unstopped", spec={}, **common)
    assert record.run_id == retained_id
    assert len(list((tmp_path / "runs/unstopped").glob("recovery-*/run-record.json"))) == 1
    assert recovery.recover_benchmark(run_id="unstopped", spec={}, **common).run_id == retained_id


def test_a_tampered_recovery_link_is_never_followed(tmp_path, monkeypatch):
    opts = options(tmp_path)
    run_benchmark(**{**opts, "host": UnstoppedHost()}, run_id="unstopped")
    monkeypatch.setattr(
        recovery,
        "DockerHost",
        lambda **kwargs: SimpleNamespace(docker=FakeDocker(), plugin_cache=None),
    )
    common = {key: opts[key] for key in ("bench_root", "results_dir", "results_repo", "state_root")}
    genuine = recovery.recover_benchmark(run_id="unstopped", spec={}, **common)
    run_dir = tmp_path / "runs/unstopped"
    [retained] = run_dir.glob("recovery-*/run-record.json")
    forged = json.loads(retained.read_text())
    forged["manifest"]["run_id"] = "forged"
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(forged))
    (run_dir / "recovery-record.json").write_text(
        json.dumps(
            {
                "run_id": "forged",
                "candidate_hash": genuine.candidate.hash,
                "recovery_of": "unstopped",
                "retained": str(outside),
            }
        )
    )
    shutil.rmtree(tmp_path / "records/results" / genuine.candidate.hash / genuine.run_id)
    record = recovery.recover_benchmark(run_id="unstopped", spec={}, **common)
    assert record.run_id == genuine.run_id
    assert "forged" not in {r.run_id for _, r in iter_run_records(tmp_path / "records")}
