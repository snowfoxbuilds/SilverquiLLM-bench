"""Login Pool slot management: numeric order, Login Blocks, removal, and the short commands."""

from __future__ import annotations

import contextlib
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner

from silverquillm.cli import main
from silverquillm.karn import login_admin
from silverquillm.karn.definition import KarnError, canonical, digest
from silverquillm.karn.execution import run_benchmark
from silverquillm.karn.host import DockerHost
from silverquillm.karn.login import LoginInUseError, PluginProcess, install_plugin
from silverquillm.karn.login_block import (
    BLOCK_FILE,
    block,
    block_if_relogin_needed,
    is_blocked,
    login_block,
    relogin_needed,
)
from silverquillm.karn.login_cooldown import set_cooldown
from silverquillm.karn.login_pool import (
    LoginPool,
    LoginPoolBusyError,
    enrolled_slots,
    slot_order,
)
from silverquillm.monitor.headless import _login_state
from silverquillm.monitor.pools import login_profiles

from .grader_fixtures import local_grader
from .test_karn_lifecycle import (
    SessionDocker,
    benchmark_data,
    login_candidate,
    pool_slot,
)
from .test_karn_lifecycle import enroll as enroll_codex
from .test_karn_login import artifact, plugin_python  # noqa: F401 -- module fixtures
from .test_karn_login_pool import enroll, held_elsewhere, pend

CLAUDE = "karn-claude-login"
CODEX = "karn-codex-login"
NOW = datetime(2026, 11, 4, 18, 0, tzinfo=UTC)


def pool_of(tmp_path, plugin_id=CLAUDE, *names) -> LoginPool:
    target = LoginPool.of(tmp_path / "state", plugin_id)
    for name in names:
        enroll(target.named_slot(name), plugin_id)
    return target


def login(tmp_path, *args, input=None):
    return CliRunner().invoke(
        main, ["login", *args, "--state-root", str(tmp_path / "state")], input=input
    )


# ---- order ---------------------------------------------------------------------------------


def test_slots_order_by_their_number_not_as_text(tmp_path):
    names = [f"slot-{n}" for n in (1, 10, 2, 11, 9)]
    target = pool_of(tmp_path, CODEX, *names, "research")
    expected = ["research", "slot-1", "slot-2", "slot-9", "slot-10", "slot-11"]
    assert target.enrolled() == expected
    assert enrolled_slots(target.root, CODEX) == expected
    assert [p.slot for p in login_profiles(tmp_path / "state", frozenset())] == expected
    assert sorted(["b-2", "b-10", "a"], key=slot_order) == ["a", "b-2", "b-10"]


def test_acquisition_tries_slot_2_before_slot_10(tmp_path):
    target = pool_of(tmp_path, CODEX, "slot-1", "slot-2", "slot-10")
    block(target.root / "slot-1", reason="relogin_needed", run_id=None, now=NOW)
    with contextlib.ExitStack() as hold:
        assert target.acquire(hold, poll_seconds=0.01).name == "slot-2"


# ---- Login Blocks ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("plugin_id", "rows", "needed"),
    [
        (CLAUDE, [{"login": "slot-1", "claude-login": "relogin needed, harvest failed"}], True),
        (CLAUDE, [{"login": "slot-1", "claude-login": "relogin needed"}], True),
        (CODEX, [{"login": "slot-1", "codex-login": "relogin needed"}], True),
        (CLAUDE, [{"login": "slot-1", "claude-login": "harvest failed"}], False),
        (CLAUDE, [{"login": "slot-1", "codex-login": "relogin needed"}], False),
        (CLAUDE, [{"login": "slot-1"}], False),
        (CLAUDE, [], False),
        (CLAUDE, None, False),
    ],
)
def test_only_the_plugins_own_relogin_flag_asks_for_a_block(plugin_id, rows, needed):
    assert relogin_needed(plugin_id, rows) is needed


def test_a_relogin_flag_blocks_the_slot_and_names_the_run(tmp_path, capsys):
    target = pool_of(tmp_path, CLAUDE, "slot-1")
    rows = [{"login": "slot-1", "claude-login": "relogin needed"}]
    assert block_if_relogin_needed(target.root / "slot-1", CLAUDE, "slot-1", rows, "run-a")
    assert login_block(target.root / "slot-1")["run_id"] == "run-a"
    assert login_block(target.root / "slot-1")["reason"] == "relogin_needed"
    assert "blocked login slot karn-claude-login/slot-1" in capsys.readouterr().err
    assert not block_if_relogin_needed(target.root / "slot-1", CLAUDE, "slot-1", [], "run-b")
    assert login_block(target.root / "slot-1")["run_id"] == "run-a"


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes through directory permissions")
def test_a_block_that_cannot_be_written_is_reported_not_raised(tmp_path, capsys):
    target = pool_of(tmp_path, CLAUDE, "slot-1")
    (target.root / "slot-1").chmod(0o500)
    try:
        rows = [{"login": "slot-1", "claude-login": "relogin needed"}]
        assert not block_if_relogin_needed(target.root / "slot-1", CLAUDE, "slot-1", rows, "r")
    finally:
        (target.root / "slot-1").chmod(0o700)
    assert "needs relogin but was not blocked" in capsys.readouterr().err
    assert not is_blocked(target.root / "slot-1")


def test_an_unreadable_block_still_blocks(tmp_path):
    target = pool_of(tmp_path, CLAUDE, "slot-1")
    (target.root / "slot-1" / BLOCK_FILE).write_text("not json")
    assert is_blocked(target.root / "slot-1")
    assert login_block(target.root / "slot-1")["reason"] == "unreadable"
    assert not target.has_claimable_slot()


def test_a_blocked_slot_is_passed_over_and_a_fully_blocked_pool_waits(tmp_path):
    target = pool_of(tmp_path, CLAUDE, "slot-1", "slot-2")
    block(target.root / "slot-1", reason="relogin_needed", run_id=None, now=NOW)
    assert target.has_claimable_slot()
    with contextlib.ExitStack() as hold:
        assert target.acquire(hold, poll_seconds=0.01).name == "slot-2"
    block(target.root / "slot-2", reason="relogin_needed", run_id=None, now=NOW)
    assert not target.has_claimable_slot()
    # Busy, not unavailable: the scheduler defers the entry instead of failing it.
    with contextlib.ExitStack() as hold, pytest.raises(LoginPoolBusyError):
        target.acquire(hold, wait=False)


def test_a_waiting_run_says_its_slots_are_blocked(tmp_path, monkeypatch):
    target = pool_of(tmp_path, CLAUDE, "slot-1", "slot-2")
    block(target.root / "slot-1", reason="relogin_needed", run_id=None, now=NOW)
    messages = []
    with held_elsewhere(target.slot("slot-2")) as release:

        def report(message):
            messages.append(message)
            release()

        with contextlib.ExitStack() as hold:
            assert target.acquire(hold, poll_seconds=0.01, on_wait=report).name == "slot-2"
    assert messages == [
        (
            "waiting for a login slot: 1 usable karn-claude-login slots are busy"
            " and 1 blocked until re-enrolled"
        )
    ]


def test_the_monitor_shows_a_block_as_its_own_state(tmp_path):
    target = pool_of(tmp_path, CLAUDE, "slot-1", "slot-2")
    block(target.root / "slot-1", reason="relogin_needed", run_id="run-a", now=NOW)
    first, second = login_profiles(tmp_path / "state", frozenset())
    assert (first.blocked, first.blocked_run, first.free) == ("relogin_needed", "run-a", False)
    assert _login_state(first) == "blocked"
    assert second.blocked is None and second.free


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13")
def test_a_run_whose_login_failed_authentication_blocks_its_slot(tmp_path):
    candidate = login_candidate(tmp_path)
    state = (tmp_path / "state").resolve()
    profile = pool_slot(state)
    enroll_codex(profile)

    class AuthFailing(SessionDocker):
        def command(self, *args, **kwargs):
            if args[0] == "create":
                self.output = next(
                    part.split(",")[1].removeprefix("src=")
                    for part in args
                    if isinstance(part, str) and part.endswith("dst=/output")
                )
            if args[0] == "start":
                Path(self.output, "result.json").write_text('{"failure_code":"authentication"}')
            return super().command(*args, **kwargs)

    run_benchmark(
        build_output=candidate.build_output,
        construct="bare",
        benchmark_id="example",
        bench_root=benchmark_data(tmp_path / "data"),
        results_dir=tmp_path / "runs",
        results_repo=tmp_path / "records",
        state_root=state,
        run_id="run-a",
        grader=local_grader(),
        host=DockerHost(
            docker=AuthFailing(), plugin_cache=state / "plugins", plugin_python=sys.executable
        ),
    )
    assert login_block(profile.directory) == {
        "reason": "relogin_needed",
        "run_id": "run-a",
        "set_at": login_block(profile.directory)["set_at"],
    }
    target = LoginPool.of(state, CODEX)
    with contextlib.ExitStack() as hold, pytest.raises(LoginPoolBusyError):
        target.acquire(hold, wait=False)


# ---- removal --------------------------------------------------------------------------------


def test_removing_a_slot_deletes_it_and_frees_its_number(tmp_path):
    target = pool_of(tmp_path, CLAUDE, "slot-1", "slot-2")
    target.remove("slot-1")
    assert target.enrolled() == ["slot-2"]
    assert not (target.root / "slot-1").exists()
    assert target.new_slot().name == "slot-1"


def test_a_removal_confirmed_for_one_login_never_deletes_its_successor(tmp_path):
    target = pool_of(tmp_path, CLAUDE, "slot-1")
    confirmed = target.identity("slot-1")
    target.remove("slot-1")
    enroll(target.new_slot(), CLAUDE)
    with pytest.raises(KarnError, match="login_slot_replaced"):
        target.remove("slot-1", identity=confirmed)
    assert target.enrolled() == ["slot-1"]
    target.remove("slot-1", identity=target.identity("slot-1"))
    assert target.enrolled() == [] and not any(target.root.glob(".removing-*"))


def test_a_dangling_pending_journal_still_refuses_removal(tmp_path):
    target = pool_of(tmp_path, CLAUDE, "slot-1")
    (target.root / "slot-1" / "active.json").symlink_to(tmp_path / "gone")
    with pytest.raises(KarnError, match="login_slot_pending"):
        target.remove("slot-1")


def test_a_stray_file_in_the_pool_never_breaks_its_order(tmp_path):
    target = pool_of(tmp_path, CLAUDE, "slot-2", "slot-10")
    (target.root / "²").write_text("")
    assert target.enrolled() == ["slot-2", "slot-10"]
    assert sorted(["x²", "x1"], key=slot_order) == ["x1", "x²"]
    with pytest.raises(KarnError, match="invalid_login_slot"):
        login_admin.slot_name("²")
    assert login_admin.slot_name(" 3 ") == "slot-3"


def test_a_closed_stderr_never_stops_a_block(tmp_path, monkeypatch):
    target = pool_of(tmp_path, CLAUDE, "slot-1")

    class Closed:
        def write(self, text):
            raise BrokenPipeError

        def flush(self):
            raise BrokenPipeError

    monkeypatch.setattr("sys.stderr", Closed())
    rows = [{"login": "slot-1", "claude-login": "relogin needed"}]
    assert block_if_relogin_needed(target.root / "slot-1", CLAUDE, "slot-1", rows, "run-a")
    assert is_blocked(target.root / "slot-1")


def test_a_slot_in_use_pending_or_unknown_is_never_removed(tmp_path):
    target = pool_of(tmp_path, CLAUDE, "slot-1", "slot-2")
    with held_elsewhere(target.slot("slot-1")), pytest.raises(LoginInUseError):
        target.remove("slot-1")
    pend(target.slot("slot-2"))
    with pytest.raises(KarnError, match="login_slot_pending"):
        target.remove("slot-2")
    with pytest.raises(KarnError, match="login_slot_not_enrolled"):
        target.remove("slot-3")
    assert target.enrolled() == ["slot-1", "slot-2"]


# ---- the cached login plugin ----------------------------------------------------------------


def cache_entry(state_root: Path, manifest: dict, *, mtime: float | None = None) -> Path:
    (state_root / "plugins").mkdir(mode=0o700, parents=True, exist_ok=True)
    entry = state_root / "plugins" / digest(canonical(manifest, ascii_only=True)).split(":")[1]
    entry.mkdir(mode=0o700)
    (entry / "bin").mkdir()
    (entry / "bin/python").write_text("")
    (entry / "artifact.json").write_bytes(canonical(manifest))
    if mtime is not None:
        os.utime(entry / "artifact.json", (mtime, mtime))
    return entry


def manifest(plugin_id=CLAUDE, version="0.1.0"):
    return {
        "id": plugin_id,
        "module": plugin_id.replace("-", "_"),
        "version": version,
        "sdk_major": 1,
        "hooks": [],
        "python": "3.13",
        "wheels": {},
    }


def test_the_newest_cached_plugin_of_the_pool_is_chosen(tmp_path):
    state = tmp_path / "state"
    cache_entry(state, manifest(version="0.1.0"), mtime=1_000)
    newest = cache_entry(state, manifest(version="0.2.0"), mtime=2_000)
    cache_entry(state, manifest(CODEX), mtime=3_000)
    chosen = login_admin.cached_login_plugin(state, CLAUDE)
    assert chosen.executable == newest / "bin/python"
    assert chosen.artifact.row == {
        "id": CLAUDE,
        "artifact": "sha256:" + newest.name,
        "configuration": {},
    }


def test_a_named_artifact_is_chosen_over_a_newer_one(tmp_path):
    state = tmp_path / "state"
    older = cache_entry(state, manifest(version="0.1.0"), mtime=1_000)
    cache_entry(state, manifest(version="0.2.0"), mtime=2_000)
    chosen = login_admin.cached_login_plugin(state, CLAUDE, artifact="sha256:" + older.name)
    assert chosen.executable == older / "bin/python"
    with pytest.raises(KarnError, match="login_plugin_artifact_not_cached:karn-claude-login"):
        login_admin.cached_login_plugin(state, CLAUDE, artifact="sha256:" + "0" * 64)


def test_a_cache_entry_whose_manifest_changed_is_never_trusted(tmp_path):
    state = tmp_path / "state"
    entry = cache_entry(state, manifest())
    (entry / "artifact.json").write_bytes(canonical({**manifest(), "module": "elsewhere"}))
    with pytest.raises(KarnError, match="login_plugin_not_cached:karn-claude-login"):
        login_admin.cached_login_plugin(state, CLAUDE)


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="pinned Plugin SDK needs 3.13")
def test_a_cache_entry_others_can_write_or_a_partial_manifest_is_never_used(tmp_path):
    state = tmp_path / "state"
    shared = cache_entry(state, manifest(version="0.2.0"))
    shared.chmod(0o777)
    with pytest.raises(KarnError, match="login_plugin_not_cached"):
        login_admin.cached_login_plugin(state, CLAUDE)
    partial = {key: value for key, value in manifest(version="0.3.0").items() if key != "module"}
    cache_entry(state, partial)
    with pytest.raises(KarnError, match="login_plugin_not_cached"):
        login_admin.cached_login_plugin(state, CLAUDE)
    good = cache_entry(state, manifest(version="0.4.0"))
    assert login_admin.cached_login_plugin(state, CLAUDE).executable == good / "bin/python"
    (state / "plugins").chmod(0o755)
    with pytest.raises(KarnError, match="login_plugin_not_cached"):
        login_admin.cached_login_plugin(state, CLAUDE)


def test_an_unreadable_cache_entry_never_hides_the_others(tmp_path):
    state = tmp_path / "state"
    good = cache_entry(state, manifest(version="0.1.0"), mtime=1_000)
    broken = cache_entry(state, manifest(version="0.2.0"), mtime=2_000)
    (broken / "artifact.json").unlink()
    (broken / "artifact.json").mkdir()
    assert login_admin.cached_login_plugin(state, CLAUDE).executable == good / "bin/python"


def test_a_cached_plugin_runs_as_the_artifact_it_was_installed_from(
    tmp_path,
    artifact,  # noqa: F811
):
    state = tmp_path / "state"
    install_plugin(artifact, state / "plugins", python=sys.executable)
    cached = login_admin.cached_login_plugin(state, CODEX)
    assert cached.artifact.row["artifact"] == artifact.row["artifact"]
    profile = LoginPool.of(state, CODEX).named_slot("slot-1")
    with profile.exclusive(), PluginProcess(cached.artifact, cached.executable, profile) as plugin:
        assert plugin.status() == [{"login": "slot-1"}]


def test_a_slot_with_a_pending_login_signs_in_with_that_runs_plugin(tmp_path, monkeypatch):
    state = tmp_path / "state"
    older = cache_entry(state, manifest(version="0.1.0"), mtime=1_000)
    cache_entry(state, manifest(version="0.2.0"), mtime=2_000)
    target = pool_of(tmp_path, CLAUDE, "slot-1")
    pend(target.slot("slot-1"), artifact="sha256:" + older.name)
    used = []
    monkeypatch.setattr(
        DockerHost,
        "enroll_login",
        lambda self, profile, plugin, *, executable: used.append(plugin.row) or 0,
    )
    assert login_admin.enroll_slot(state, "claude", "slot-1") == ("karn-claude-login/slot-1", 0)
    assert used[0]["artifact"] == "sha256:" + older.name


def test_a_new_slot_whose_sign_in_fails_is_discarded(tmp_path, monkeypatch):
    state = tmp_path / "state"
    cache_entry(state, manifest())
    pool_of(tmp_path, CLAUDE, "slot-1")
    monkeypatch.setattr(DockerHost, "enroll_login", lambda *args, **kwargs: 1)
    assert login_admin.enroll_slot(state, "claude") == ("karn-claude-login/slot-2", 1)
    assert not (state / "logins" / CLAUDE / "slot-2").exists()


# ---- the commands ---------------------------------------------------------------------------


@pytest.fixture
def signed_in(tmp_path, monkeypatch):
    """Every sign-in succeeds and stores a login, recording which slot it was for."""
    cache_entry(tmp_path / "state", manifest())
    cache_entry(tmp_path / "state", manifest(CODEX))
    calls = []

    def sign_in(self, profile, plugin, *, executable):
        calls.append(profile.name)
        enroll(profile, plugin.row["id"])
        return 0

    monkeypatch.setattr(DockerHost, "enroll_login", sign_in)
    return calls


def test_login_add_enrolls_the_next_slot_from_the_cached_plugin(tmp_path, signed_in):
    result = login(tmp_path, "add", "claude")
    assert result.exit_code == 0, result.output
    assert "karn-claude-login/slot-1: enrolled" in result.output
    assert login(tmp_path, "add", "claude").exit_code == 0
    assert signed_in == ["slot-1", "slot-2"]


def test_login_refresh_takes_a_number_or_a_name(tmp_path, signed_in):
    pool_of(tmp_path, CODEX, "slot-3")
    assert login(tmp_path, "refresh", "codex", "3").exit_code == 0
    assert login(tmp_path, "refresh", "codex", "slot-3").exit_code == 0
    assert signed_in == ["slot-3", "slot-3"]
    missing = login(tmp_path, "refresh", "codex", "4")
    assert missing.exit_code == 2
    assert "Not enrolled in the codex pool: 4 (enrolled: slot-3)" in missing.output


def test_without_a_cached_plugin_the_long_form_is_named(tmp_path):
    pool_of(tmp_path, CLAUDE, "slot-1")
    result = login(tmp_path, "refresh", "claude", "1")
    assert result.exit_code == 1
    assert "login_plugin_not_cached:karn-claude-login" in result.output
    assert "--build-output" in result.output


def test_login_remove_asks_first_unless_told_yes(tmp_path):
    target = pool_of(tmp_path, CODEX, "slot-1", "slot-2")
    kept = login(tmp_path, "remove", "codex", "1", input="n\n")
    assert kept.exit_code == 1 and target.enrolled() == ["slot-1", "slot-2"]
    removed = login(tmp_path, "remove", "codex", "1", input="y\n")
    assert removed.exit_code == 0, removed.output
    assert login(tmp_path, "remove", "codex", "slot-2", "--yes").exit_code == 0
    assert target.enrolled() == []


def test_login_remove_refuses_a_slot_in_use(tmp_path):
    target = pool_of(tmp_path, CODEX, "slot-1")
    with held_elsewhere(target.slot("slot-1")):
        result = login(tmp_path, "remove", "codex", "1", "--yes")
    assert result.exit_code == 1 and "login_in_use" in result.output
    assert target.enrolled() == ["slot-1"]


def test_login_unblock_lifts_only_the_named_blocks(tmp_path):
    target = pool_of(tmp_path, CLAUDE, "slot-1", "slot-2")
    for name in ("slot-1", "slot-2"):
        block(target.root / name, reason="relogin_needed", run_id=None, now=NOW)
    result = login(tmp_path, "unblock", "claude", "1")
    assert result.exit_code == 0, result.output
    assert "karn-claude-login/slot-1: block lifted" in result.output
    assert not is_blocked(target.root / "slot-1") and is_blocked(target.root / "slot-2")


def test_login_ls_lists_slots_in_order_with_their_state(tmp_path):
    pool_of(tmp_path, CODEX, "slot-1", "slot-10", "slot-2")
    target = pool_of(tmp_path, CLAUDE, "slot-1")
    block(target.root / "slot-1", reason="relogin_needed", run_id="run-a", now=NOW)
    result = login(tmp_path, "ls")
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert [line.split()[:3] for line in lines] == [
        ["claude", "slot-1", "blocked"],
        ["codex", "slot-1", "free"],
        ["codex", "slot-2", "free"],
        ["codex", "slot-10", "free"],
    ]
    assert "relogin_needed after run run-a" in lines[0]
    assert [line.split()[1] for line in login(tmp_path, "ls", "codex").output.splitlines()] == [
        "slot-1",
        "slot-2",
        "slot-10",
    ]


def test_bare_login_points_at_the_subcommands(tmp_path):
    result = login(tmp_path)
    assert result.exit_code == 2
    assert "login add claude" in result.output
    stray = CliRunner().invoke(main, ["login", "slot-1"])
    assert "subcommands:" in stray.output and "refresh" in stray.output


def test_ls_shows_a_cooldown_and_a_pending_login(tmp_path):
    target = pool_of(tmp_path, CODEX, "slot-1", "slot-2")
    set_cooldown(target.root / "slot-1", datetime.now(UTC) + timedelta(hours=2), now=NOW)
    pend(target.slot("slot-2"), run_id="run-z")
    lines = login(tmp_path, "ls").output.splitlines()
    assert lines[0].split()[:3] == ["codex", "slot-1", "cooldown"]
    assert lines[1].split()[:3] == ["codex", "slot-2", "pending"]
    assert "run run-z must be recovered" in lines[1]
