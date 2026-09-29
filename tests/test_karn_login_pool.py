"""Per-provider login pools: allocation, waiting, enrollment slots and legacy adoption."""

from __future__ import annotations

import contextlib
import os
import threading

import pytest

from silverquillm.karn.definition import KarnError, canonical
from silverquillm.karn.execution import login_profile
from silverquillm.karn.login import LoginProfile
from silverquillm.karn.login_pool import (
    SLOT_RECORD,
    LoginPool,
    adopt_legacy_login,
    stored_login_plugin,
)

PLUGIN = "karn-claude-login"
STORED = {
    "karn-claude-login": {".credentials.json": "e30=", ".claude.json": "e30="},
    "karn-codex-login": {"auth.json": "e30="},
}


def pool(tmp_path) -> LoginPool:
    return LoginPool.of(tmp_path / "state", PLUGIN)


def document(plugin=PLUGIN) -> str:
    """A secret document shaped as the plugin's own store writes it."""
    return canonical({"format": 1, "revision": "a" * 32, "files": STORED[plugin]}).decode()


def enroll(profile: LoginProfile, plugin=PLUGIN) -> LoginProfile:
    profile.set_secret("login." + profile.name, document(plugin))
    return profile


def slot(target: LoginPool, name: str) -> LoginProfile:
    return enroll(target.named_slot(name), target.plugin_id)


def pend(profile: LoginProfile, artifact="sha256:" + "a" * 64, run_id="run-x") -> None:
    profile.journal({"run_id": run_id, "plugin_artifact": artifact})


def acquire(target: LoginPool, **options):
    hold = contextlib.ExitStack()
    return hold, target.acquire(hold, poll_seconds=0.01, **options)


@contextlib.contextmanager
def held_elsewhere(profile):
    held, done = threading.Event(), threading.Event()

    def hold():
        with profile.exclusive():
            held.set()
            done.wait(30)

    thread = threading.Thread(target=hold)
    thread.start()
    held.wait()
    try:
        yield done.set
    finally:
        done.set()
        thread.join()


def test_an_empty_pool_refuses_and_names_the_plugin(tmp_path):
    target = pool(tmp_path)
    target.named_slot("unfinished")  # an enrollment that stored nothing is not a slot
    with pytest.raises(KarnError, match="login_pool_empty:karn-claude-login"):
        acquire(target)


def test_a_free_slot_is_locked_for_the_holder_until_released(tmp_path):
    target = pool(tmp_path)
    slot(target, "a")
    hold, profile = acquire(target)
    assert profile.name == "a" and target.ref(profile) == "karn-claude-login/a"
    with pytest.raises(KarnError, match="login_in_use"), profile.exclusive():
        pass
    hold.close()
    with profile.exclusive():
        pass


def test_a_busy_slot_is_skipped_for_a_free_one(tmp_path):
    target = pool(tmp_path)
    first, second = slot(target, "a"), slot(target, "b")
    with first.exclusive():
        hold, profile = acquire(target)
    assert profile.name == second.name
    hold.close()


def test_the_run_waits_while_every_usable_slot_is_busy(tmp_path):
    target = pool(tmp_path)
    only = slot(target, "a")
    messages = []
    with held_elsewhere(only) as release:
        hold, profile = acquire(target, on_wait=lambda m: (messages.append(m), release()))
    assert profile.name == "a"
    assert messages == ["waiting for a login slot: all 1 usable karn-claude-login slots are busy"]
    hold.close()


def test_a_pending_slot_of_another_plugin_artifact_is_skipped(tmp_path):
    target = pool(tmp_path)
    pend(slot(target, "a"), artifact="sha256:" + "b" * 64)
    with pytest.raises(KarnError, match="login_pool_pending:karn-claude-login"):
        acquire(target, settle_artifact="sha256:" + "a" * 64)
    slot(target, "b")
    hold, profile = acquire(target, settle_artifact="sha256:" + "a" * 64)
    assert profile.name == "b"
    hold.close()


def test_a_settled_slot_is_preferred_over_one_this_run_could_settle(tmp_path):
    target = pool(tmp_path)
    pending = slot(target, "a")
    pend(pending)
    slot(target, "b")
    hold, profile = acquire(target, settle_artifact="sha256:" + "a" * 64)
    assert profile.name == "b"
    # The pending slot was released again, not left locked.
    with pending.exclusive():
        pass
    hold.close()


def test_a_pending_slot_the_run_can_settle_is_the_last_resort(tmp_path):
    target = pool(tmp_path)
    pending = slot(target, "a")
    pend(pending)
    hold, profile = acquire(target, settle_artifact="sha256:" + "a" * 64)
    assert profile.name == "a" and profile.pending()["run_id"] == "run-x"
    hold.close()
    with pytest.raises(KarnError, match="login_pool_pending"):
        acquire(target)


def test_a_waiting_run_does_not_take_a_pending_slot_while_another_is_only_busy(tmp_path):
    target = pool(tmp_path)
    pend(slot(target, "a"), artifact="sha256:" + "b" * 64)
    busy = slot(target, "b")
    with held_elsewhere(busy) as release:
        hold, profile = acquire(target, on_wait=lambda _: release())
    assert profile.name == "b"
    hold.close()


def test_new_slots_are_numbered_and_never_shared(tmp_path):
    target = pool(tmp_path)
    names = []
    threads = [
        threading.Thread(target=lambda: names.append(target.new_slot().name)) for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(names, key=lambda n: int(n.split("-")[1])) == [f"slot-{i}" for i in range(1, 9)]


def test_a_failed_new_enrollment_leaves_no_slot_behind(tmp_path):
    target = pool(tmp_path)
    unfinished = target.new_slot()
    target.discard_unenrolled(unfinished)
    assert not unfinished.directory.exists()
    kept = enroll(target.new_slot())  # enrollment stored a login, so it is kept
    target.discard_unenrolled(kept)
    assert kept.directory.exists() and kept.name == "slot-1"


@pytest.mark.parametrize("name", ["", ".hidden", "a/b", "x" * 65])
def test_slot_names_are_validated(tmp_path, name):
    with pytest.raises(KarnError, match="invalid_login_slot"):
        pool(tmp_path).slot(name)


def test_run_inputs_resolve_to_pool_slots_and_legacy_profiles(tmp_path):
    state = tmp_path / "state"
    slot = login_profile(state, "karn-claude-login/slot-1")
    assert (slot.directory, slot.name) == (
        state.resolve() / "logins/karn-claude-login/slot-1",
        "slot-1",
    )
    legacy = login_profile(state, "bare-claude-opus")
    assert legacy.directory == state.resolve() / "logins/bare-claude-opus"
    for invalid in ("other-plugin/slot-1", "karn-claude-login/../x", "karn-claude-login/"):
        with pytest.raises(KarnError):
            login_profile(state, invalid)


def legacy_profile(tmp_path, construct="bare-claude-opus", plugin=PLUGIN) -> LoginProfile:
    """A login enrolled before pools existed; enrollment always took its lock."""
    profile = LoginProfile((tmp_path / "state").resolve() / "logins" / construct, construct)
    with profile.exclusive():
        enroll(profile, plugin)
    return profile


STATE = "state"


def adopt(tmp_path, construct="bare-claude-opus", plugin=PLUGIN):
    return adopt_legacy_login(tmp_path / STATE, construct, plugin)


def test_a_settled_legacy_login_moves_into_its_plugins_pool_once(tmp_path):
    legacy = legacy_profile(tmp_path)
    secret = (legacy.directory / "secret.json").read_bytes()
    assert adopt(tmp_path) == "karn-claude-login/bare-claude-opus"
    assert not legacy.directory.exists()
    moved = pool(tmp_path).slot("bare-claude-opus")
    assert (moved.directory / "secret.json").read_bytes() == secret
    assert moved.get_secret("login.bare-claude-opus")
    with pytest.raises(KarnError, match="legacy_login_not_found"):
        adopt(tmp_path)
    assert pool(tmp_path).enrolled() == ["bare-claude-opus"]


def test_a_codex_login_is_never_adopted_into_the_claude_pool(tmp_path):
    legacy = legacy_profile(tmp_path, "bare", plugin="karn-codex-login")
    with pytest.raises(KarnError, match="legacy_login_belongs_to_other_plugin"):
        adopt(tmp_path, "bare", "karn-claude-login")
    assert legacy.directory.exists() and pool(tmp_path).enrolled() == []
    assert adopt(tmp_path, "bare", "karn-codex-login") == "karn-codex-login/bare"


def test_a_legacy_login_without_a_recognizable_store_is_refused(tmp_path):
    legacy = LoginProfile((tmp_path / STATE).resolve() / "logins/odd", "odd")
    with legacy.exclusive():
        legacy.set_secret("login.odd", canonical({"synthetic": "odd"}).decode())
    with pytest.raises(KarnError, match="legacy_login_unrecognized"):
        adopt(tmp_path, "odd")
    assert legacy.directory.exists()


@pytest.mark.parametrize(
    ("files", "plugin"),
    [
        ({"auth.json": "x"}, "karn-codex-login"),
        ({".credentials.json": "x"}, "karn-claude-login"),
        ({".credentials.json": "x", ".claude.json": "y"}, "karn-claude-login"),
        ({"auth.json": "x", ".credentials.json": "y"}, None),
        ({".claude.json": "x"}, None),
        ({}, None),
    ],
)
def test_a_stored_document_names_its_plugin_by_shape(files, plugin):
    value = {"format": 1, "revision": "a" * 32, "files": files}
    assert stored_login_plugin(canonical(value).decode()) == plugin
    assert stored_login_plugin(canonical({**value, "revision": "short"}).decode()) is None
    assert stored_login_plugin(canonical({**value, "extra": 1}).decode()) is None


def test_a_pending_or_busy_legacy_login_stays_where_its_run_names_it(tmp_path):
    legacy = legacy_profile(tmp_path)
    pend(legacy)
    with pytest.raises(KarnError, match="legacy_login_pending"):
        adopt(tmp_path)
    assert legacy.pending() is not None
    legacy.settled()
    (legacy.state / "mounted.json").write_text("{}")  # a harvest not yet finished
    with pytest.raises(KarnError, match="legacy_login_pending"):
        adopt(tmp_path)
    (legacy.state / "mounted.json").unlink()
    with legacy.exclusive(), pytest.raises(KarnError, match="login_in_use"):
        adopt(tmp_path)
    assert adopt(tmp_path)


def test_adoption_never_replaces_an_existing_slot(tmp_path):
    legacy = legacy_profile(tmp_path)
    existing = pool(tmp_path).named_slot("bare-claude-opus")  # an empty, just-created slot
    with pytest.raises(KarnError, match="login_slot_exists"):
        adopt(tmp_path)
    assert legacy.directory.exists() and existing.directory.exists()
    assert not (existing.directory / "secret.json").exists()


def test_adoption_refuses_what_is_not_a_legacy_login(tmp_path):
    logins = (tmp_path / STATE).resolve() / "logins"
    (logins / "never-locked").mkdir(parents=True)
    (logins / "never-locked/secret.json").write_text('"x"')
    with pytest.raises(KarnError, match="legacy_login_not_found"):
        adopt(tmp_path, "never-locked")
    legacy_profile(tmp_path, "real")
    os.symlink(logins / "real", logins / "linked")
    with pytest.raises(KarnError, match="legacy_login_not_found"):
        adopt(tmp_path, "linked")
    with pytest.raises(KarnError, match="invalid_legacy_login"):
        adopt(tmp_path, PLUGIN)
    with pytest.raises(KarnError, match="invalid_login_pool"):
        adopt(tmp_path, "real", "karn-unknown-login")
    assert (logins / "real/secret.json").exists()


def test_concurrent_adoptions_move_a_legacy_login_exactly_once(tmp_path):
    legacy_profile(tmp_path)
    results, start = [], threading.Barrier(6)

    def attempt():
        start.wait()
        try:
            results.append(adopt(tmp_path))
        except KarnError as error:
            results.append(str(error))

    threads = [threading.Thread(target=attempt) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results.count("karn-claude-login/bare-claude-opus") == 1
    assert pool(tmp_path).enrolled() == ["bare-claude-opus"]


def test_a_slot_recorded_for_another_plugin_is_never_allocated(tmp_path):
    claude = pool(tmp_path)
    codex = LoginPool.of(tmp_path / STATE, "karn-codex-login")
    stray = slot(codex, "moved")
    os.rename(stray.directory, claude.root / "moved")
    assert claude.enrolled() == []
    with pytest.raises(KarnError, match="login_pool_empty"):
        acquire(claude)
    with pytest.raises(KarnError, match="login_slot_belongs_to_other_plugin"):
        claude.named_slot("moved")


def test_an_unrecorded_slot_holding_a_login_is_never_claimed(tmp_path):
    target = pool(tmp_path)
    unrecorded = slot(target, "a")
    (unrecorded.directory / SLOT_RECORD).unlink()
    assert target.enrolled() == []
    with pytest.raises(KarnError, match="login_slot_unrecorded"):
        target.named_slot("a")


def test_discarding_an_unenrolled_slot_waits_for_no_holder_and_keeps_a_login(tmp_path):
    target = pool(tmp_path)
    fresh = target.new_slot()
    with fresh.exclusive():
        target.discard_unenrolled(fresh)  # another enrollment holds it: kept
    assert fresh.directory.exists()
    enroll(fresh)
    target.discard_unenrolled(fresh)  # it now holds a login: kept
    assert fresh.directory.exists()


def test_a_holder_of_a_removed_slot_is_refused_its_lock(tmp_path):
    target = pool(tmp_path)
    fresh = target.new_slot()
    with fresh.exclusive():  # creates its lock file, as an enrollment's lock would
        pass
    stale = os.open(fresh.directory / "runner.lock", os.O_RDWR)
    try:
        target.discard_unenrolled(fresh)
        assert not fresh.directory.exists()
        recreated = target.named_slot(fresh.name)
        # The new lock file is its own; a lock on the removed one guards nothing.
        with recreated.exclusive():
            pass
        assert not os.path.samestat(os.fstat(stale), os.stat(recreated.directory / "runner.lock"))
    finally:
        os.close(stale)


def test_a_moved_lock_file_is_refused_after_it_is_locked(tmp_path, monkeypatch):
    import fcntl

    original = fcntl.flock
    target = pool(tmp_path)
    profile = slot(target, "a")
    moved = tmp_path / "elsewhere"

    def flock_then_move(descriptor, operation):
        original(descriptor, operation)
        if not moved.exists():
            os.rename(profile.directory, moved)

    monkeypatch.setattr("silverquillm.karn.login.fcntl.flock", flock_then_move)
    with pytest.raises(KarnError, match="login_in_use"), profile.exclusive():
        pass


def test_a_damaged_slot_is_skipped_with_a_warning_and_others_serve(tmp_path):
    target = pool(tmp_path)
    damaged = slot(target, "a")
    slot(target, "b")
    damaged.directory.chmod(0o755)
    warnings = []
    hold, profile = acquire(target, on_wait=warnings.append)
    assert profile.name == "b"
    assert warnings == ["skipping login slot karn-claude-login/a: login_directory_must_be_private"]
    hold.close()
    damaged.directory.chmod(0o700)


def test_locks_taken_while_choosing_are_released_deterministically(tmp_path):
    target = pool(tmp_path)
    pending = slot(target, "a")
    pend(pending)
    unreadable = slot(target, "b")
    (unreadable.directory / "active.json").write_text("[]")  # a malformed journal
    with pytest.raises(KarnError, match="login_pool_pending"):
        acquire(target)
    for profile in (pending, unreadable):
        with profile.exclusive():
            pass
    hold, chosen = acquire(target, settle_artifact="sha256:" + "a" * 64)
    assert chosen.name == "a"
    with unreadable.exclusive():
        pass
    hold.close()


@pytest.mark.parametrize("name", ["karn-claude-login", "karn-codex-login"])
def test_a_plugin_id_is_never_a_legacy_login_name(tmp_path, name):
    with pytest.raises(KarnError, match="invalid_login_profile_name"):
        login_profile(tmp_path / STATE, name)
