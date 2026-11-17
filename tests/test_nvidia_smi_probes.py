"""One host-wide nvidia-smi: a probe that will not die blocks the next one in any process."""

from __future__ import annotations

import multiprocessing
import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

from silverquillm.karn import model_server
from silverquillm.karn.model_server import (
    PROBE_LOCK,
    PROBE_RECORD,
    GpuReading,
    _process_start,
    read_gpus,
)

READING = "0, GPU-a, NVIDIA H100 80GB HBM3, 14, 81559, 700.00, 580.1"


def fake_nvidia_smi(bindir: Path, *, stuck: bool) -> Path:
    """An ``nvidia-smi`` that logs each start; stuck, it never answers."""
    started = bindir / "started"
    script = bindir / "nvidia-smi"
    body = "exec sleep 60" if stuck else f'case "$1" in --query-gpu=*) echo "{READING}";; esac'
    script.write_text(f"#!/bin/sh\necho $$ >> {started}\n{body}\n")
    script.chmod(0o755)
    return started


def _probe_in_worker(state_root, bindir, results, fault=None):
    """A scheduler worker's claim-time reading, with a probe SIGKILL cannot reap; *fault*
    names how its startup fails."""
    os.environ["PATH"] = f"{bindir}:{os.environ['PATH']}"
    model_server.NVIDIA_SMI_SECONDS = 0.3
    subprocess.Popen.kill = lambda self: None
    if fault == "dies_before_authorising":
        write = model_server._write_record

        def write_then_die(path, document):
            write(path, document)
            os._exit(0)

        model_server._write_record = write_then_die
    reading = model_server.read_gpus(state_root=Path(state_root))
    results.put((reading.reason, reading.gpus is not None))


def in_a_worker(state_root, bindir, fault=None):
    context = multiprocessing.get_context("spawn")
    results = context.Queue()
    worker = context.Process(target=_probe_in_worker, args=(state_root, bindir, results, fault))
    worker.start()
    worker.join(30)
    assert worker.exitcode == 0
    return results.get(timeout=5) if fault is None else None


def stand_ins(bindir: Path) -> list[int]:
    """Live processes started for this fake ``nvidia-smi``, whether gated or executed."""
    path = str(bindir).encode()
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            command = (entry / "cmdline").read_bytes()
            ours = path in (entry / "environ").read_bytes()
        except OSError:
            continue
        gated = model_server._GATE.encode() in command
        if ours and (gated or b"sleep" in command) and _process_start(int(entry.name)):
            found.append(int(entry.name))
    return found


def never_ran(started: Path, bindir: Path) -> None:
    """No probe touched the driver, and none is left behind."""
    assert not started.exists()
    until = time.monotonic() + 10
    while stand_ins(bindir):
        assert time.monotonic() < until, stand_ins(bindir)
        time.sleep(0.05)


def gone(pid, timeout=10):
    until = time.monotonic() + timeout
    while _process_start(pid) is not None:
        if time.monotonic() > until:
            raise AssertionError(f"probe {pid} did not go")
        time.sleep(0.05)


def test_a_stuck_probe_outlives_its_worker_and_no_later_worker_starts_another(tmp_path):
    state, bindir = tmp_path / "state", tmp_path / "bin"
    bindir.mkdir()
    started = fake_nvidia_smi(bindir, stuck=True)
    try:
        assert in_a_worker(state, bindir) == ("nvidia_smi_unavailable", False)
        [pid] = map(int, started.read_text().split())
        assert _process_start(pid) is not None
        for _ in range(2):
            assert in_a_worker(state, bindir) == ("nvidia_smi_unavailable", False)
        assert started.read_text().split() == [str(pid)]
    finally:
        for line in started.read_text().split():
            os.kill(int(line), signal.SIGKILL)
    gone(pid)
    fake_nvidia_smi(bindir, stuck=False)
    assert in_a_worker(state, bindir) == (None, True)
    assert not (state / PROBE_RECORD).exists()


def test_an_interrupted_probe_stays_recorded_until_it_is_gone(tmp_path, monkeypatch):
    state, bindir = tmp_path / "state", tmp_path / "bin"
    bindir.mkdir()
    started = fake_nvidia_smi(bindir, stuck=True)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setattr(subprocess.Popen, "kill", lambda self: None)

    def interrupted(self, timeout=None):
        until = time.monotonic() + 10
        while not started.exists() and time.monotonic() < until:
            time.sleep(0.01)
        raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(subprocess.Popen, "communicate", interrupted)
        with pytest.raises(KeyboardInterrupt):
            read_gpus(state_root=state)
    [pid] = map(int, started.read_text().split())
    try:
        assert (state / PROBE_RECORD).exists()
        # Another process knows nothing of this one's abandoned probe but the record.
        monkeypatch.setattr(model_server, "_abandoned", [])
        assert read_gpus(state_root=state) == GpuReading(None, reason="nvidia_smi_unavailable")
        # The monitor honours the record without writing one.
        assert read_gpus(state_root=state, record=False).reason == "nvidia_smi_unavailable"
        assert started.read_text().split() == [str(pid)]
    finally:
        os.kill(pid, signal.SIGKILL)
    gone(pid)
    monkeypatch.setattr(model_server, "_abandoned", [])
    fake_nvidia_smi(bindir, stuck=False)
    assert read_gpus(state_root=state).gpus[0]["name"] == "NVIDIA H100 80GB HBM3"
    assert not (state / PROBE_RECORD).exists()


def test_the_monitors_reading_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(model_server, "_abandoned", [])
    state, bindir = tmp_path / "state", tmp_path / "bin"
    bindir.mkdir()
    fake_nvidia_smi(bindir, stuck=False)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    assert read_gpus(state_root=state, record=False).gpus is not None
    assert not state.exists()


def test_a_record_that_cannot_be_written_runs_no_probe_and_leaves_none(tmp_path):
    state, bindir = tmp_path / "state", tmp_path / "bin"
    bindir.mkdir()
    state.mkdir()
    (state / PROBE_LOCK).touch()
    state.chmod(0o500)
    started = fake_nvidia_smi(bindir, stuck=True)
    try:
        for _ in range(3):
            assert in_a_worker(state, bindir) == ("nvidia_smi_unavailable", False)
        never_ran(started, bindir)
    finally:
        state.chmod(0o700)
    fake_nvidia_smi(bindir, stuck=False)
    assert in_a_worker(state, bindir) == (None, True)
    assert not (state / PROBE_RECORD).exists()


@pytest.mark.parametrize("fault", [OSError(28, "No space left on device"), KeyboardInterrupt()])
def test_a_failed_or_interrupted_record_write_runs_no_probe(tmp_path, monkeypatch, fault):
    state, bindir = tmp_path / "state", tmp_path / "bin"
    bindir.mkdir()
    started = fake_nvidia_smi(bindir, stuck=True)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setattr(model_server, "_abandoned", [])

    def failing(source, target):
        raise fault

    with monkeypatch.context() as patch:
        patch.setattr(model_server.os, "replace", failing)
        if isinstance(fault, KeyboardInterrupt):
            with pytest.raises(KeyboardInterrupt):
                read_gpus(state_root=state)
        else:
            assert read_gpus(state_root=state).reason == "nvidia_smi_unavailable"
    never_ran(started, bindir)
    assert not (state / PROBE_RECORD).exists()
    assert [path.name for path in state.iterdir()] == [PROBE_LOCK]
    assert model_server._abandoned == []
    fake_nvidia_smi(bindir, stuck=False)
    assert read_gpus(state_root=state).gpus is not None


def test_a_worker_that_dies_before_authorising_its_probe_runs_none(tmp_path):
    state, bindir = tmp_path / "state", tmp_path / "bin"
    bindir.mkdir()
    started = fake_nvidia_smi(bindir, stuck=True)
    in_a_worker(state, bindir, fault="dies_before_authorising")
    assert (state / PROBE_RECORD).exists()
    never_ran(started, bindir)
    # The record names a stand-in that is gone: stale, it blocks nothing.
    fake_nvidia_smi(bindir, stuck=False)
    assert in_a_worker(state, bindir) == (None, True)
    assert not (state / PROBE_RECORD).exists()


def test_a_child_gone_before_its_identity_is_read_is_never_recorded(tmp_path, monkeypatch):
    state, bindir = tmp_path / "state", tmp_path / "bin"
    bindir.mkdir()
    started = fake_nvidia_smi(bindir, stuck=True)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setattr(model_server, "_abandoned", [])
    with monkeypatch.context() as patch:
        patch.setattr(model_server, "_process_start", lambda pid: None)
        assert read_gpus(state_root=state).reason == "nvidia_smi_unavailable"
    never_ran(started, bindir)
    assert not (state / PROBE_RECORD).exists()


@pytest.mark.parametrize(
    "record",
    [
        {"pid": 1, "start": None},
        {"pid": None, "start": None},
        {"pid": "1", "start": 5},
        {"pid": True, "start": 5},
        {"pid": 1, "start": "5"},
        {"pid": 1},
        "garbage",
    ],
)
def test_a_leftover_malformed_record_is_stale_and_recovers_by_itself(tmp_path, monkeypatch, record):
    import json

    state, bindir = tmp_path / "state", tmp_path / "bin"
    bindir.mkdir()
    state.mkdir()
    (state / PROBE_RECORD).write_text(json.dumps(record))
    fake_nvidia_smi(bindir, stuck=False)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setattr(model_server, "_abandoned", [])
    # The monitor reads past it without touching it.
    assert read_gpus(state_root=state, record=False).gpus is not None
    assert (state / PROBE_RECORD).exists()
    assert read_gpus(state_root=state).gpus is not None
    assert not (state / PROBE_RECORD).exists()
