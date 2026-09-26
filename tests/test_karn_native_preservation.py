"""Preserving a stale run's native sessions reads only that run's own files, after it stopped."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pytest

from silverquillm.karn import login
from silverquillm.karn.definition import KarnError, canonical
from silverquillm.karn.login import NATIVE_PRESERVED, LoginProfile, preserve_pending_native

HOST = "host-only-rollout"


def stale_run(tmp_path: Path, run_id: str = "run-a") -> tuple[LoginProfile, Path, Path]:
    profile = LoginProfile(tmp_path / "logins/shared", "shared")
    evidence = tmp_path / "runs" / run_id / "host"
    evidence.mkdir(parents=True)
    sessions = profile.state / "work" / "sessions"
    sessions.mkdir(parents=True)
    login.write_private(profile.state / "mounted.json", canonical({"run_id": run_id}))
    profile.journal(
        {"run_id": run_id, "container_name": "sq-run-" + run_id, "evidence_dir": str(evidence)}
    )
    return profile, sessions, evidence


def preserved_files(evidence: Path) -> dict[str, str]:
    root = evidence / NATIVE_PRESERVED / "sessions"
    return {
        str(path.relative_to(root)): path.read_text()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def stopped(stops: list):
    return lambda name, run_id: stops.append((name, run_id))


def test_only_rollout_journals_are_copied_after_the_container_is_confirmed_stopped(tmp_path):
    profile, sessions, evidence = stale_run(tmp_path)
    (sessions / "2026/09").mkdir(parents=True)
    (sessions / "2026/09/rollout-a.jsonl").write_text("own\n")
    (sessions / "auth.json").write_text("secret")
    order = []

    def stop(name, run_id):
        order.append((name, run_id))
        # A container still writing until it is stopped: its final journal must be included.
        (sessions / "rollout-final.jsonl").write_text("final\n")

    outcome = preserve_pending_native(profile, stop)
    assert outcome == {"run_id": "run-a", "preserved": True, "reason": None}
    assert order == [("sq-run-run-a", "run-a")]
    assert preserved_files(evidence) == {
        "2026/09/rollout-a.jsonl": "own\n",
        "rollout-final.jsonl": "final\n",
    }


def test_nothing_is_read_when_the_stale_container_cannot_be_confirmed_stopped(tmp_path):
    profile, sessions, evidence = stale_run(tmp_path)
    (sessions / "rollout-a.jsonl").write_text("own\n")

    def unconfirmed(name, run_id):
        raise KarnError("container_stop_unconfirmed")

    outcome = preserve_pending_native(profile, unconfirmed)
    assert outcome["reason"] == "native_state_container_not_stopped"
    assert not (evidence / NATIVE_PRESERVED).exists()


def test_a_symlinked_session_directory_is_never_followed(tmp_path):
    profile, sessions, evidence = stale_run(tmp_path)
    host = tmp_path / "host-sessions"
    host.mkdir()
    (host / "rollout-host.jsonl").write_text(HOST)
    (sessions / "linked").symlink_to(host)
    (sessions / "rollout-host.jsonl").symlink_to(host / "rollout-host.jsonl")
    (sessions / "rollout-a.jsonl").write_text("own\n")
    assert preserve_pending_native(profile, stopped([]))["preserved"]
    assert preserved_files(evidence) == {"rollout-a.jsonl": "own\n"}


def swap_with_link(real: Path, host: Path, done: threading.Event) -> None:
    """Keep replacing a session directory with a link to host files, as a live container could."""
    hidden = real.with_name(".swapped")
    while not done.is_set():
        try:
            os.rename(real, hidden)
            os.symlink(host, real)
            time.sleep(0.0005)
            os.unlink(real)
            os.rename(hidden, real)
            time.sleep(0.0005)
        except OSError:
            pass


def test_a_directory_swapped_for_a_link_mid_copy_never_redirects_a_read(tmp_path):
    """The container's directories may change under the walk; no read may land on host files."""
    host = tmp_path / "host-sessions"
    host.mkdir()
    for index in range(20):
        (host / f"rollout-{index:02}.jsonl").write_text(HOST)
    for attempt in range(120):
        profile, sessions, evidence = stale_run(tmp_path / str(attempt))
        real = sessions / "day"
        real.mkdir()
        for index in range(20):
            (real / f"rollout-{index:02}.jsonl").write_text("own\n")
        done = threading.Event()
        swapper = threading.Thread(target=swap_with_link, args=(real, host, done), daemon=True)
        swapper.start()
        try:
            preserve_pending_native(profile, stopped([]))
        finally:
            done.set()
            swapper.join()
        assert HOST not in preserved_files(evidence).values()


def test_the_file_count_is_capped(tmp_path, monkeypatch):
    monkeypatch.setattr(login, "MAX_NATIVE_FILES", 3)
    profile, sessions, evidence = stale_run(tmp_path)
    for index in range(4):
        (sessions / f"rollout-{index}.jsonl").write_text("")
    outcome = preserve_pending_native(profile, stopped([]))
    assert outcome["reason"] == "native_state_limit_exceeded"
    assert not (evidence / NATIVE_PRESERVED).exists()


@pytest.mark.parametrize("other", [True, False])
def test_state_of_another_run_is_never_preserved_as_the_pending_run(tmp_path, other):
    profile, sessions, evidence = stale_run(tmp_path)
    (sessions / "rollout-a.jsonl").write_text("own\n")
    if other:
        login.write_private(profile.state / "mounted.json", canonical({"run_id": "run-b"}))
    else:
        (profile.state / "mounted.json").unlink()
    stops = []
    assert preserve_pending_native(profile, stopped(stops))["reason"] == "native_state_unavailable"
    assert stops == [] and not (evidence / NATIVE_PRESERVED).exists()
