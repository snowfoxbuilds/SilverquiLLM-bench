"""Signing a slot in again keeps a pending run's native evidence, and Login Block decisions
are made while the slot is held, so no block is missed or lifted for another owner."""

from __future__ import annotations

import contextlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from silverquillm.karn import host as host_module
from silverquillm.karn import login, login_admin, login_pool
from silverquillm.karn.definition import KarnError, PluginArtifact, canonical, digest
from silverquillm.karn.host import DockerHost
from silverquillm.karn.login import (
    NATIVE_PRESERVED,
    LoginProfile,
    PluginProcess,
    admit_plugin_mounts,
    install_plugin,
)
from silverquillm.karn.login_block import block, is_blocked
from silverquillm.karn.login_pool import LoginPool, LoginPoolBusyError

from . import test_karn_claude_login as claude_plugin
from . import test_karn_login as codex_plugin
from .test_karn_login_pool import enroll, pend

PROVIDERS = {
    "codex": (codex_plugin.FIXTURE, codex_plugin.enrolled, "sessions/2026/11/rollout-a.jsonl"),
    "claude": (claude_plugin.FIXTURE, claude_plugin.enrolled, "projects/-workspace/s-1.jsonl"),
}
NOW = datetime(2026, 11, 4, 18, 0, tzinfo=UTC)


def plugin_artifact(fixture: Path) -> PluginArtifact:
    manifest = json.loads((fixture / "install.json").read_text())["manifest"]
    row = {
        "id": manifest["id"],
        "version": manifest["version"],
        "source": "catalog",
        "artifact": digest(canonical(manifest, ascii_only=True)),
    }
    wheels = tuple((fixture / name, value) for name, value in manifest["wheels"].items())
    return PluginArtifact(row, manifest, fixture / "install.json", wheels, None)


@pytest.fixture(scope="module", params=sorted(PROVIDERS))
def plugin(request, tmp_path_factory):
    """The real login plugin of each provider, installed once."""
    if sys.version_info[:2] != (3, 13):
        pytest.skip("The pinned Karn Plugin SDK requires CPython 3.13")
    fixture, enrolled, journal = PROVIDERS[request.param]
    artifact = plugin_artifact(fixture)
    python = install_plugin(artifact, tmp_path_factory.mktemp("cache"), python=sys.executable)
    return artifact, python, enrolled, journal


class Stops:
    """The host's Docker as enrollment sees it: what it stopped and cleaned up."""

    def __init__(self, refuse: bool = False):
        self.stopped, self.cleaned, self.refuse = [], [], refuse

    def stop_and_confirm(self, name, run_id):
        if self.refuse:
            raise KarnError("container_stop_unconfirmed")
        self.stopped.append(run_id)

    def cleanup_run(self, name, run_id):
        self.cleaned.append(run_id)


def interrupted(tmp_path, plugin, profile=None, run_id="run-a") -> tuple[LoginProfile, Path]:
    """A slot whose run was killed with its login mounted and a native journal written."""
    artifact, python, enrolled, journal = plugin
    profile = profile or LoginProfile(tmp_path / "logins" / "slot-1", "slot-1")
    enrolled(profile)
    evidence = tmp_path / "runs" / run_id / "host"
    evidence.mkdir(parents=True)
    output = tmp_path / "output"
    output.mkdir()
    mounts = [{"Type": "bind", "Source": str(output), "Target": "/output", "ReadOnly": False}]
    with profile.exclusive(), PluginProcess(artifact, python, profile) as process:
        mounts = admit_plugin_mounts(
            mounts, process.invoke("before_container_mount", run_id, mounts), profile.state
        )
    profile.journal(
        {
            "run_id": run_id,
            "container_name": "sq-run-" + run_id,
            "evidence_dir": str(evidence),
            "plugin_artifact": artifact.row["artifact"],
            "mounts": mounts,
        }
    )
    native = profile.state / "work" / journal
    native.parent.mkdir(parents=True, exist_ok=True)
    native.write_text("interrupted\n")
    return profile, evidence


def sign_in(profile, plugin, monkeypatch, *, status=0, docker=None):
    artifact, python, *_ = plugin
    monkeypatch.setattr(PluginProcess, "setup", lambda self: status)
    docker = docker or Stops()
    host = DockerHost(docker=docker, plugin_cache=Path("/nonexistent"))
    return host.enroll_login(profile, artifact, executable=python)


def kept(evidence: Path, plugin) -> str:
    return (evidence / NATIVE_PRESERVED / plugin[3]).read_text()


# ---- a pending run's evidence ---------------------------------------------------------------


@pytest.mark.parametrize("status", [0, 1])
def test_signing_in_again_keeps_the_pending_runs_native_journals(
    tmp_path, plugin, monkeypatch, status
):
    profile, evidence = interrupted(tmp_path, plugin)
    block(profile.directory, reason="relogin_needed", run_id="run-a", now=NOW)
    docker = Stops()
    assert sign_in(profile, plugin, monkeypatch, status=status, docker=docker) == status
    assert kept(evidence, plugin) == "interrupted\n"
    assert docker.stopped[0] == "run-a" and docker.cleaned == ["run-a"]
    assert profile.pending() is None
    assert not (profile.state / "mounted.json").exists()
    # A failed or cancelled sign-in still settles the run, but leaves the slot blocked.
    assert is_blocked(profile.directory) == (status != 0)


def test_a_failed_copy_refuses_the_sign_in_and_a_retry_keeps_the_journals(
    tmp_path, plugin, monkeypatch
):
    profile, evidence = interrupted(tmp_path, plugin)

    def unwritable(*args, **kwargs):
        raise OSError("disk full")

    with monkeypatch.context() as broken:
        broken.setattr(login, "iter_regular_files", unwritable)
        broken.setattr(PluginProcess, "setup", lambda self: pytest.fail("signed in"))
        with pytest.raises(KarnError, match="login_native_state_not_preserved:.*copy_failed"):
            DockerHost(docker=Stops(), plugin_cache=Path("/nonexistent")).enroll_login(
                profile, plugin[0], executable=plugin[1]
            )
    assert profile.pending()["run_id"] == "run-a"
    assert (profile.state / "mounted.json").exists()
    assert not (evidence / NATIVE_PRESERVED).exists()
    assert sign_in(profile, plugin, monkeypatch) == 0
    assert kept(evidence, plugin) == "interrupted\n"


def test_an_unconfirmed_stop_reads_nothing_and_settles_nothing(tmp_path, plugin, monkeypatch):
    profile, evidence = interrupted(tmp_path, plugin)
    monkeypatch.setattr(PluginProcess, "setup", lambda self: pytest.fail("signed in"))
    with pytest.raises(KarnError, match="native_state_container_not_stopped"):
        DockerHost(docker=Stops(refuse=True), plugin_cache=Path("/nonexistent")).enroll_login(
            profile, plugin[0], executable=plugin[1]
        )
    assert profile.pending()["run_id"] == "run-a"
    assert not (evidence / NATIVE_PRESERVED).exists()


def test_another_runs_mounted_state_is_never_kept_as_the_pending_runs(
    tmp_path, plugin, monkeypatch
):
    profile, _ = interrupted(tmp_path, plugin)
    other = tmp_path / "runs/run-b/host"
    other.mkdir(parents=True)
    journal = profile.pending()
    profile.journal({**journal, "run_id": "run-b", "evidence_dir": str(other)})
    # The plugin will not harvest a mount another run made either, so nothing settles.
    with pytest.raises(KarnError, match="login_harvest_pending"):
        sign_in(profile, plugin, monkeypatch)
    assert not (other / NATIVE_PRESERVED).exists()
    assert profile.pending()["run_id"] == "run-b"


def test_a_settlement_retried_after_its_copy_keeps_the_first_copy(tmp_path, plugin, monkeypatch):
    profile, evidence = interrupted(tmp_path, plugin)

    class CleanupFails(Stops):
        def cleanup_run(self, name, run_id):
            raise KarnError("cleanup_failed")

    with pytest.raises(KarnError, match="cleanup_failed"):
        sign_in(profile, plugin, monkeypatch, docker=CleanupFails())
    assert profile.pending()["run_id"] == "run-a"
    (profile.state / "work" / plugin[3]).unlink(missing_ok=True)
    assert sign_in(profile, plugin, monkeypatch) == 0
    assert kept(evidence, plugin) == "interrupted\n"
    assert profile.pending() is None


def test_a_loss_no_retry_can_cure_is_reported_and_settled(tmp_path, plugin, monkeypatch, capsys):
    profile, evidence = interrupted(tmp_path, plugin)
    evidence.rmdir()
    assert sign_in(profile, plugin, monkeypatch) == 0
    assert profile.pending() is None
    assert (
        "settling the login of run run-a without its native state"
        " (native_state_run_directory_unavailable)" in capsys.readouterr().err
    )


def test_another_plugin_artifact_is_refused_before_the_run_is_stopped(
    tmp_path, plugin, monkeypatch
):
    profile, evidence = interrupted(tmp_path, plugin)
    profile.journal({**profile.pending(), "plugin_artifact": "sha256:" + "b" * 64})
    docker = Stops()
    with pytest.raises(KarnError, match="login_recovery_requires_previous_plugin"):
        sign_in(profile, plugin, monkeypatch, docker=docker)
    assert docker.stopped == [] and not (evidence / NATIVE_PRESERVED).exists()


def test_login_refresh_from_the_plugin_cache_keeps_the_pending_runs_journals(
    tmp_path, plugin, monkeypatch
):
    state = tmp_path / "state"
    install_plugin(plugin[0], state / "plugins", python=sys.executable)
    plugin_id = plugin[0].row["id"]
    slot = LoginPool.of(state, plugin_id).named_slot("slot-1")
    _, evidence = interrupted(tmp_path, plugin, slot)
    monkeypatch.setattr(PluginProcess, "setup", lambda self: 0)
    monkeypatch.setattr(
        host_module,
        "DockerHost",
        lambda plugin_cache: DockerHost(docker=Stops(), plugin_cache=plugin_cache),
    )
    agent = login_admin.PROVIDER_OF[plugin_id]
    assert login_admin.enroll_slot(state, agent, "slot-1") == (f"{plugin_id}/slot-1", 0)
    assert kept(evidence, plugin) == "interrupted\n"


# ---- Login Block decisions under the slot's lock --------------------------------------------


def test_a_successful_sign_in_lifts_the_block_before_it_releases_the_slot(
    tmp_path, plugin, monkeypatch
):
    profile = LoginProfile(tmp_path / "logins" / "slot-1", "slot-1")
    plugin[2](profile)
    block(profile.directory, reason="relogin_needed", run_id=None, now=NOW)
    exclusive, released = LoginProfile.exclusive, []

    @contextlib.contextmanager
    def held(self):
        with exclusive(self):
            yield
            released.append(is_blocked(self.directory))

    monkeypatch.setattr(LoginProfile, "exclusive", held)
    assert sign_in(profile, plugin, monkeypatch) == 0
    # Lifted after the slot is released, it could lift a block its next owner wrote.
    assert released == [False]


def blocked_on_release(monkeypatch, directory: Path):
    """The slot's run blocks it in the moment between a chooser's check and its lock."""
    checked = login_pool.is_blocked

    def is_blocked_then_block(path):
        if Path(path) == directory and not checked(path):
            block(directory, reason="relogin_needed", run_id="run-a", now=NOW)
            return False
        return checked(path)

    monkeypatch.setattr(login_pool, "is_blocked", is_blocked_then_block)


def pool(tmp_path, *names) -> LoginPool:
    target = LoginPool.of(tmp_path / "state", "karn-claude-login")
    for name in names:
        enroll(target.named_slot(name), target.plugin_id)
    return target


def test_a_slot_blocked_while_it_was_being_chosen_is_passed_over(tmp_path, monkeypatch):
    target = pool(tmp_path, "slot-1", "slot-2")
    blocked_on_release(monkeypatch, target.root / "slot-1")
    with contextlib.ExitStack() as hold:
        assert target.acquire(hold, wait=False).name == "slot-2"
    # The passed-over slot's lock was released.
    with target.slot("slot-1").exclusive():
        pass


def test_a_pool_whose_last_slot_was_just_blocked_waits(tmp_path, monkeypatch):
    target = pool(tmp_path, "slot-1")
    blocked_on_release(monkeypatch, target.root / "slot-1")
    with contextlib.ExitStack() as hold, pytest.raises(LoginPoolBusyError):
        target.acquire(hold, wait=False)

    class Waited(Exception):
        pass

    def sleep(seconds):
        raise Waited

    waits = []
    monkeypatch.setattr(login_pool.time, "sleep", sleep)
    with contextlib.ExitStack() as hold, pytest.raises(Waited):
        target.acquire(hold, poll_seconds=0, on_wait=waits.append)
    assert waits == [
        "waiting for a login slot: all 1 usable karn-claude-login slots are blocked until re-enrolled"
    ]


def test_a_blocked_pending_slot_is_never_taken_to_settle(tmp_path, monkeypatch):
    target = pool(tmp_path, "slot-1")
    artifact = "sha256:" + "a" * 64
    pend(target.slot("slot-1"), artifact=artifact)
    blocked_on_release(monkeypatch, target.root / "slot-1")
    with contextlib.ExitStack() as hold, pytest.raises(LoginPoolBusyError):
        target.acquire(hold, settle_artifact=artifact, wait=False)


def test_the_capacity_hint_counts_a_slot_blocked_while_it_looked(tmp_path, monkeypatch):
    target = pool(tmp_path, "slot-1")
    blocked_on_release(monkeypatch, target.root / "slot-1")
    assert not target.has_claimable_slot()
