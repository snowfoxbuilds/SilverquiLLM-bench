"""Login Cooldowns: the `login cooldown` command, pool acquisition, and the monitor's reading."""

from __future__ import annotations

import contextlib
import json
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
from click.testing import CliRunner

from silverquillm.cli import main
from silverquillm.karn.definition import KarnError
from silverquillm.karn.login_cooldown import (
    COOLDOWN_FILE,
    clear_cooldown,
    cooldown_until,
    parse_duration,
    set_cooldown,
)
from silverquillm.karn.login_pool import LoginPool
from silverquillm.monitor.pools import login_profiles

from .test_karn_login_pool import enroll, held_elsewhere

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def codex_pool(tmp_path, *names):
    target = LoginPool.of(tmp_path / "state", "karn-codex-login")
    for name in names:
        enroll(target.named_slot(name), target.plugin_id)
    return target


def cooldown(tmp_path, *args):
    return CliRunner().invoke(
        main, ["login", "cooldown", "--state-root", str(tmp_path / "state"), *args]
    )


@pytest.mark.parametrize(
    ("text", "span"),
    [
        ("30m", timedelta(minutes=30)),
        ("5h", timedelta(hours=5)),
        ("2d", timedelta(days=2)),
        ("1h30m", timedelta(hours=1, minutes=30)),
        (" 45S ", timedelta(seconds=45)),
    ],
)
def test_a_duration_reads_days_hours_minutes_and_seconds(text, span):
    assert parse_duration(text) == span


@pytest.mark.parametrize("text", ["", "0m", "5", "h", "-5h", "5h-", "1w", "400d", "5h 30m"])
def test_a_duration_that_is_not_a_positive_span_up_to_a_year_is_refused(text):
    with pytest.raises(KarnError, match="invalid_cooldown_duration"):
        parse_duration(text)


def test_cooldown_sets_named_slots_and_leaves_their_logins_alone(tmp_path):
    target = codex_pool(tmp_path, "slot-1", "slot-2", "slot-3")
    secret = (target.root / "slot-1" / "secret.json").read_bytes()
    result = cooldown(
        tmp_path, "--agent", "codex", "--duration", "5h", "--slots", "slot-1", "slot-2"
    )
    assert result.exit_code == 0, result.output
    assert "karn-codex-login/slot-1: cooling down until" in result.output
    for name in ("slot-1", "slot-2"):
        document = json.loads((target.root / name / COOLDOWN_FILE).read_text())
        set_at = datetime.fromisoformat(document["set_at"])
        until = datetime.fromisoformat(document["until"])
        assert until - set_at == timedelta(hours=5)
        assert cooldown_until(target.root / name) == until
    assert not (target.root / "slot-3" / COOLDOWN_FILE).exists()
    assert (target.root / "slot-1" / "secret.json").read_bytes() == secret


def test_cooldown_takes_slots_as_arguments_too_and_all_takes_every_slot(tmp_path):
    target = codex_pool(tmp_path, "slot-1", "slot-2")
    result = cooldown(
        tmp_path, "--agent", "codex", "--duration", "1h", "--slots", "slot-1", "slot-2"
    )
    assert result.exit_code == 0, result.output
    assert cooldown(tmp_path, "--agent", "codex", "--clear", "--all").exit_code == 0
    assert all(cooldown_until(target.root / name) is None for name in ("slot-1", "slot-2"))
    assert cooldown(tmp_path, "--agent", "codex", "--duration", "1h", "--all").exit_code == 0
    assert all(cooldown_until(target.root / name) for name in ("slot-1", "slot-2"))


def test_clearing_lifts_only_the_named_slots(tmp_path):
    target = codex_pool(tmp_path, "slot-1", "slot-2")
    cooldown(tmp_path, "--agent", "codex", "--duration", "1h", "--all")
    result = cooldown(tmp_path, "--agent", "codex", "--clear", "--slots", "slot-1")
    assert result.exit_code == 0, result.output
    assert "slot-1: cooldown lifted" in result.output
    assert cooldown_until(target.root / "slot-1") is None
    assert cooldown_until(target.root / "slot-2") is not None
    again = cooldown(tmp_path, "--agent", "codex", "--clear", "--slots", "slot-1")
    assert "slot-1: no cooldown" in again.output


def test_an_unknown_slot_is_refused_with_the_enrolled_ones_listed(tmp_path):
    target = codex_pool(tmp_path, "slot-1", "slot-2")
    result = cooldown(tmp_path, "--agent", "codex", "--duration", "1h", "--slots", "slot-9")
    assert result.exit_code == 2
    assert "slot-9" in result.output and "slot-1, slot-2" in result.output
    assert not (target.root / "slot-9").exists()
    # The other pool's slots are not this pool's.
    claude = cooldown(tmp_path, "--agent", "claude", "--duration", "1h", "--slots", "slot-1")
    assert claude.exit_code == 2 and "enrolled: none" in claude.output


@pytest.mark.parametrize(
    "args",
    [
        ["--agent", "codex", "--duration", "1h"],  # no slots
        ["--agent", "codex", "--duration", "1h", "--all", "--slots", "slot-1"],
        ["--agent", "codex", "--slots", "slot-1"],  # neither duration nor clear
        ["--agent", "codex", "--duration", "1h", "--clear", "--slots", "slot-1"],
        ["--agent", "gemini", "--duration", "1h", "--slots", "slot-1"],
    ],
)
def test_cooldown_needs_one_choice_of_slots_and_of_action(tmp_path, args):
    codex_pool(tmp_path, "slot-1")
    assert cooldown(tmp_path, *args).exit_code == 2


def test_a_bad_duration_is_reported_without_writing(tmp_path):
    target = codex_pool(tmp_path, "slot-1")
    result = cooldown(tmp_path, "--agent", "codex", "--duration", "soon", "--slots", "slot-1")
    assert result.exit_code == 1 and "invalid_cooldown_duration" in result.output
    assert not (target.root / "slot-1" / COOLDOWN_FILE).exists()


def test_enrolling_still_needs_its_build_and_construct(tmp_path):
    result = CliRunner().invoke(main, ["login", "--state-root", str(tmp_path / "state")])
    assert result.exit_code == 2
    assert "--build-output" in result.output and "--construct" in result.output


# Reading -----------------------------------------------------------------------


def test_an_expired_or_unreadable_cooldown_is_no_cooldown(tmp_path):
    directory = codex_pool(tmp_path, "slot-1").root / "slot-1"
    set_cooldown(directory, NOW + timedelta(hours=1), now=NOW)
    assert cooldown_until(directory, now=NOW) == NOW + timedelta(hours=1)
    assert cooldown_until(directory, now=NOW + timedelta(hours=2)) is None
    for content in ("not json", "[]", '{"until": 5}', '{"until": "2026-10-08T13:00:00"}'):
        (directory / COOLDOWN_FILE).write_text(content)
        assert cooldown_until(directory, now=NOW) is None
    assert clear_cooldown(directory) and not clear_cooldown(directory)


# Acquisition -------------------------------------------------------------------


def test_acquisition_passes_over_a_cooled_down_slot(tmp_path):
    target = codex_pool(tmp_path, "slot-1", "slot-2")
    set_cooldown(target.root / "slot-1", datetime.now(UTC) + timedelta(hours=1), now=NOW)
    with contextlib.ExitStack() as hold:
        assert target.acquire(hold, poll_seconds=0.01).name == "slot-2"


def test_a_run_waits_while_every_slot_cools_down_and_takes_one_when_it_ends(tmp_path):
    target = codex_pool(tmp_path, "slot-1")
    # Two seconds: the stored end is cut to whole seconds, so at least one is left to wait.
    set_cooldown(target.root / "slot-1", datetime.now(UTC) + timedelta(seconds=2), now=NOW)
    waited: list[str] = []
    started = time.monotonic()
    with contextlib.ExitStack() as hold:
        profile = target.acquire(hold, poll_seconds=0.05, on_wait=waited.append)
    assert profile.name == "slot-1"
    assert time.monotonic() - started >= 0.5
    assert waited == [
        "waiting for a login slot: all 1 usable karn-codex-login slots are cooling down"
    ]


def test_a_cooldown_never_disturbs_the_run_already_holding_the_slot(tmp_path):
    target = codex_pool(tmp_path, "slot-1")
    profile = target.slot("slot-1")
    with held_elsewhere(profile):
        result = cooldown(tmp_path, "--agent", "codex", "--duration", "1h", "--slots", "slot-1")
        assert result.exit_code == 0, result.output
    assert cooldown_until(target.root / "slot-1") is not None


def test_a_cooldown_set_while_waiting_keeps_the_run_waiting(tmp_path):
    target = codex_pool(tmp_path, "slot-1")
    set_cooldown(target.root / "slot-1", datetime.now(UTC) + timedelta(hours=1), now=NOW)
    taken = threading.Event()

    def take():
        with contextlib.ExitStack() as hold:
            target.acquire(hold, poll_seconds=0.02, on_wait=lambda message: None)
            taken.set()

    worker = threading.Thread(target=take, daemon=True)
    worker.start()
    time.sleep(0.2)
    assert not taken.is_set()
    clear_cooldown(target.root / "slot-1")
    assert taken.wait(timeout=5)


# The monitor -------------------------------------------------------------------


def test_the_monitor_reads_each_profiles_cooldown_without_writing(tmp_path):
    target = codex_pool(tmp_path, "slot-1", "slot-2")
    set_cooldown(target.root / "slot-2", NOW + timedelta(hours=3), now=NOW)
    before = sorted(path.name for path in target.root.rglob("*"))
    profiles = {
        view.slot: view for view in login_profiles(tmp_path / "state", frozenset(), now=NOW)
    }
    assert profiles["slot-1"].cooldown_until is None
    assert profiles["slot-2"].cooldown_until == NOW + timedelta(hours=3)
    assert profiles["slot-1"].free and not profiles["slot-2"].free
    later = login_profiles(tmp_path / "state", frozenset(), now=NOW + timedelta(hours=4))
    assert all(view.cooldown_until is None for view in later)
    assert sorted(path.name for path in target.root.rglob("*")) == before
