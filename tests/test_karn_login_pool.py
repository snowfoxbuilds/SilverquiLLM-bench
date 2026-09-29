"""Per-provider login pools: allocation, waiting, enrollment slots and legacy adoption."""

from __future__ import annotations

import contextlib
import os
import threading

import pytest

from silverquillm.karn.definition import KarnError, canonical
from silverquillm.karn.execution import login_profile
from silverquillm.karn.login import LoginProfile
from silverquillm.karn.login_pool import LoginPool, adopt_legacy_login

PLUGIN = "karn-claude-login"


def pool(tmp_path) -> LoginPool:
    return LoginPool.of(tmp_path / "state", PLUGIN)


def enroll(profile: LoginProfile) -> LoginProfile:
    profile.set_secret("login." + profile.name, canonical({"synthetic": profile.name}).decode())
    return profile


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
    target.slot("unfinished")  # an enrollment that stored nothing is not a slot
    with pytest.raises(KarnError, match="login_pool_empty:karn-claude-login"):
        acquire(target)


def test_a_free_slot_is_locked_for_the_holder_until_released(tmp_path):
    target = pool(tmp_path)
    enroll(target.slot("a"))
    hold, profile = acquire(target)
    assert profile.name == "a" and target.ref(profile) == "karn-claude-login/a"
    with pytest.raises(KarnError, match="login_in_use"), profile.exclusive():
        pass
    hold.close()
    with profile.exclusive():
        pass


def test_a_busy_slot_is_skipped_for_a_free_one(tmp_path):
    target = pool(tmp_path)
    first, second = enroll(target.slot("a")), enroll(target.slot("b"))
    with first.exclusive():
        hold, profile = acquire(target)
    assert profile.name == second.name
    hold.close()


def test_the_run_waits_while_every_usable_slot_is_busy(tmp_path):
    target = pool(tmp_path)
    slot = enroll(target.slot("a"))
    messages = []
    with held_elsewhere(slot) as release:
        hold, profile = acquire(target, on_wait=lambda m: (messages.append(m), release()))
    assert profile.name == "a"
    assert messages == ["waiting for a login slot: all 1 usable karn-claude-login slots are busy"]
    hold.close()


def test_a_pending_slot_of_another_plugin_artifact_is_skipped(tmp_path):
    target = pool(tmp_path)
    pend(enroll(target.slot("a")), artifact="sha256:" + "b" * 64)
    with pytest.raises(KarnError, match="login_pool_pending:karn-claude-login"):
        acquire(target, settle_artifact="sha256:" + "a" * 64)
    enroll(target.slot("b"))
    hold, profile = acquire(target, settle_artifact="sha256:" + "a" * 64)
    assert profile.name == "b"
    hold.close()


def test_a_settled_slot_is_preferred_over_one_this_run_could_settle(tmp_path):
    target = pool(tmp_path)
    pending = enroll(target.slot("a"))
    pend(pending)
    enroll(target.slot("b"))
    hold, profile = acquire(target, settle_artifact="sha256:" + "a" * 64)
    assert profile.name == "b"
    # The pending slot was released again, not left locked.
    with pending.exclusive():
        pass
    hold.close()


def test_a_pending_slot_the_run_can_settle_is_the_last_resort(tmp_path):
    target = pool(tmp_path)
    pending = enroll(target.slot("a"))
    pend(pending)
    hold, profile = acquire(target, settle_artifact="sha256:" + "a" * 64)
    assert profile.name == "a" and profile.pending()["run_id"] == "run-x"
    hold.close()
    with pytest.raises(KarnError, match="login_pool_pending"):
        acquire(target)


def test_a_waiting_run_does_not_take_a_pending_slot_while_another_is_only_busy(tmp_path):
    target = pool(tmp_path)
    pend(enroll(target.slot("a")), artifact="sha256:" + "b" * 64)
    busy = enroll(target.slot("b"))
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
    kept = enroll(target.new_slot())
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


def legacy_profile(tmp_path, construct="bare-claude-opus") -> LoginProfile:
    """A login enrolled before pools existed; enrollment always took its lock."""
    profile = LoginProfile((tmp_path / "state").resolve() / "logins" / construct, construct)
    with profile.exclusive():
        enroll(profile)
    return profile


def test_a_settled_legacy_login_moves_into_its_plugins_pool_once(tmp_path):
    legacy = legacy_profile(tmp_path)
    secret = (legacy.directory / "secret.json").read_bytes()
    assert adopt_legacy_login(tmp_path / "state", "bare-claude-opus", PLUGIN)
    assert not legacy.directory.exists()
    slot = pool(tmp_path).slot("bare-claude-opus")
    assert (slot.directory / "secret.json").read_bytes() == secret
    assert slot.get_secret("login.bare-claude-opus")
    assert not adopt_legacy_login(tmp_path / "state", "bare-claude-opus", PLUGIN)
    assert pool(tmp_path).enrolled() == ["bare-claude-opus"]


def test_a_pending_or_busy_legacy_login_stays_where_its_run_names_it(tmp_path):
    legacy = legacy_profile(tmp_path)
    pend(legacy)
    assert not adopt_legacy_login(tmp_path / "state", "bare-claude-opus", PLUGIN)
    assert legacy.pending() is not None
    legacy.settled()
    with legacy.exclusive():
        assert not adopt_legacy_login(tmp_path / "state", "bare-claude-opus", PLUGIN)
    assert adopt_legacy_login(tmp_path / "state", "bare-claude-opus", PLUGIN)


def test_adoption_never_replaces_an_existing_slot(tmp_path):
    legacy = legacy_profile(tmp_path)
    existing = pool(tmp_path).named_slot("bare-claude-opus")  # an empty, just-created slot
    assert not adopt_legacy_login(tmp_path / "state", "bare-claude-opus", PLUGIN)
    assert legacy.directory.exists() and existing.directory.exists()
    assert not (existing.directory / "secret.json").exists()


def test_adoption_ignores_what_is_not_a_legacy_login(tmp_path):
    logins = (tmp_path / "state").resolve() / "logins"
    (logins / "never-locked").mkdir(parents=True)
    (logins / "never-locked/secret.json").write_text('"x"')
    assert not adopt_legacy_login(tmp_path / "state", "never-locked", PLUGIN)
    legacy_profile(tmp_path, "real")
    os.symlink(logins / "real", logins / "linked")
    assert not adopt_legacy_login(tmp_path / "state", "linked", PLUGIN)
    assert not adopt_legacy_login(tmp_path / "state", PLUGIN, PLUGIN)
    assert not adopt_legacy_login(tmp_path / "state", "real", "karn-unknown-login")
    assert (logins / "real/secret.json").exists()


def test_concurrent_hosts_adopt_a_legacy_login_exactly_once(tmp_path):
    legacy_profile(tmp_path)
    results, start = [], threading.Barrier(6)

    def adopt():
        start.wait()
        results.append(adopt_legacy_login(tmp_path / "state", "bare-claude-opus", PLUGIN))

    threads = [threading.Thread(target=adopt) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results.count(True) == 1
    assert pool(tmp_path).enrolled() == ["bare-claude-opus"]
