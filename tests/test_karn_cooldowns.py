"""Cooldown Schedules: the store, the `login cooldown` command, acquisition and the monitor."""

from __future__ import annotations

import contextlib
import json
import os
import threading
import time
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from click.testing import CliRunner

from silverquillm.cli import main
from silverquillm.karn.cooldowns import (
    COOLDOWNS_FILE,
    LEGACY_COOLDOWN_FILE,
    add_cooldown,
    clear_schedule,
    cooldown,
    end_in_force_after,
    extend_hold,
    held_until,
    parse_duration,
    parse_time,
    read_schedule,
    remove_cooldown,
)
from silverquillm.karn.definition import KarnError
from silverquillm.karn.login_pool import LoginPool, LoginPoolBusyError
from silverquillm.monitor.pools import login_profiles

from .test_karn_login_pool import enroll, held_elsewhere

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
FABLE = "claude-fable-5-2"
OPUS = "claude-opus-5-5"
PACIFIC = ZoneInfo("America/Los_Angeles")


def hold(directory, until, *, now=NOW, start=None, scope="all", source="operator", note=None):
    window = cooldown(start or now, until, now=now, scope=scope, source=source, note=note)
    return add_cooldown(directory, window, now=now)


def codex_pool(tmp_path, *names):
    target = LoginPool.of(tmp_path / "state", "karn-codex-login")
    for name in names:
        enroll(target.named_slot(name), target.plugin_id)
    return target


def claude_pool(tmp_path, *names):
    target = LoginPool.of(tmp_path / "state", "karn-claude-login")
    for name in names:
        enroll(target.named_slot(name), target.plugin_id)
    return target


def run_cooldown(tmp_path, *args):
    return CliRunner().invoke(
        main, ["login", "cooldown", "--state-root", str(tmp_path / "state"), *args]
    )


def schedule(directory):
    return json.loads((directory / COOLDOWNS_FILE).read_text())["cooldowns"]


# Times and spans -----------------------------------------------------------------


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


# 2026-10-08 12:00 UTC is Thursday 05:00 in Los Angeles (PDT, UTC-7).
@pytest.mark.parametrize(
    ("text", "local"),
    [
        ("14:00", datetime(2026, 10, 8, 14, 0, tzinfo=PACIFIC)),
        ("04:30", datetime(2026, 10, 9, 4, 30, tzinfo=PACIFIC)),  # passed today: tomorrow
        ("Fri 09:00", datetime(2026, 10, 9, 9, 0, tzinfo=PACIFIC)),
        ("friday 9:00", datetime(2026, 10, 9, 9, 0, tzinfo=PACIFIC)),
        ("thu 06:00", datetime(2026, 10, 8, 6, 0, tzinfo=PACIFIC)),  # later today
        ("Thu 04:00", datetime(2026, 10, 15, 4, 0, tzinfo=PACIFIC)),  # passed today: next week
        ("2026-11-20 09:00", datetime(2026, 11, 20, 9, 0, tzinfo=PACIFIC)),  # PST by then
        ("2026-11-20T09:00", datetime(2026, 11, 20, 9, 0, tzinfo=PACIFIC)),
    ],
)
def test_a_time_is_read_in_local_time_and_means_its_next_occurrence(text, local):
    assert parse_time(text, now=NOW, tz=PACIFIC) == local


def test_an_offset_counts_from_now_or_from_the_given_start():
    assert parse_time("+3h", now=NOW) == NOW + timedelta(hours=3)
    assert parse_time("1d", now=NOW) == NOW + timedelta(days=1)
    start = NOW + timedelta(days=2)
    assert parse_time("+1h30m", now=NOW, base=start) == start + timedelta(hours=1, minutes=30)


@pytest.mark.parametrize(
    "text", ["", "soon", "25:00", "14:60", "Frx 09:00", "2026-02-30 09:00", "14", "-3h", "1w"]
)
def test_anything_else_is_refused(text):
    with pytest.raises(KarnError, match="invalid_cooldown_(time|duration)"):
        parse_time(text, now=NOW, tz=PACIFIC)


def test_a_cooldown_must_end_after_it_starts_after_now_and_within_a_year():
    with pytest.raises(KarnError, match="cooldown_ends_before_it_starts"):
        cooldown(NOW + timedelta(hours=2), NOW + timedelta(hours=1), now=NOW)
    with pytest.raises(KarnError, match="cooldown_ends_before_it_starts"):
        cooldown(NOW - timedelta(hours=2), NOW - timedelta(hours=1), now=NOW)
    with pytest.raises(KarnError, match="cooldown_beyond_horizon"):
        cooldown(NOW, NOW + timedelta(days=366), now=NOW)
    with pytest.raises(KarnError, match="invalid_cooldown_note"):
        cooldown(NOW, NOW + timedelta(hours=1), now=NOW, note="line\nbreak")
    with pytest.raises(KarnError, match="invalid_cooldown_scope"):
        cooldown(NOW, NOW + timedelta(hours=1), now=NOW, scope="opus")


# The store ---------------------------------------------------------------------


def test_a_schedule_holds_several_windows_and_only_one_in_force_holds_back(tmp_path):
    directory = codex_pool(tmp_path, "slot-1").root / "slot-1"
    hold(directory, NOW + timedelta(hours=2), start=NOW + timedelta(hours=1), note="lunch")
    hold(directory, NOW + timedelta(hours=5), start=NOW + timedelta(hours=4))
    hold(directory, NOW + timedelta(hours=3), start=NOW + timedelta(hours=1, minutes=30))
    assert [c.start for c in read_schedule(directory, now=NOW)] == [
        NOW + timedelta(hours=1),
        NOW + timedelta(hours=1, minutes=30),
        NOW + timedelta(hours=4),
    ]
    assert held_until(directory, now=NOW) is None
    # Overlapping windows are kept apart; the profile is held until the last one ends.
    assert held_until(directory, now=NOW + timedelta(hours=1, minutes=45)) == NOW + timedelta(
        hours=3
    )
    assert held_until(directory, now=NOW + timedelta(hours=3, minutes=30)) is None
    stored = schedule(directory)
    assert stored[0] == {
        "start": "2026-10-08T13:00:00Z",
        "end": "2026-10-08T14:00:00Z",
        "set_at": "2026-10-08T12:00:00Z",
        "scope": "all",
        "source": "operator",
        "note": "lunch",
    }
    assert oct(os.stat(directory / COOLDOWNS_FILE).st_mode & 0o777) == "0o600"


def test_a_write_drops_ended_windows(tmp_path):
    directory = codex_pool(tmp_path, "slot-1").root / "slot-1"
    hold(directory, NOW + timedelta(hours=1))
    later = NOW + timedelta(hours=2)
    hold(directory, later + timedelta(hours=1), now=later)
    assert [entry["start"] for entry in schedule(directory)] == ["2026-10-08T14:00:00Z"]


def test_a_fable_scoped_window_holds_back_only_fable_runs(tmp_path):
    directory = claude_pool(tmp_path, "slot-1").root / "slot-1"
    hold(directory, NOW + timedelta(hours=1), scope="fable", source="usage-limit")
    assert held_until(directory, model=FABLE, now=NOW) == NOW + timedelta(hours=1)
    assert held_until(directory, model=OPUS, now=NOW) is None
    assert held_until(directory, now=NOW) is None
    hold(directory, NOW + timedelta(minutes=30))
    assert held_until(directory, model=OPUS, now=NOW) == NOW + timedelta(minutes=30)
    assert held_until(directory, model=FABLE, now=NOW) == NOW + timedelta(hours=1)


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        "[]",
        '{"format": 2, "cooldowns": []}',
        '{"format": 1, "cooldowns": {}}',
        '{"format": 1, "cooldowns": [{"start": "2026-10-08T11:00:00Z"}]}',
        (
            '{"format": 1, "cooldowns": [{"start": "2026-10-08T11:00:00", "end": '
            '"2026-10-08T13:00:00", "set_at": "2026-10-08T11:00:00", "scope": "all", '
            '"source": "operator"}]}'
        ),
        (
            '{"format": 1, "cooldowns": [{"start": "2026-10-08T11:00:00Z", "end": '
            '"2026-10-08T13:00:00Z", "set_at": "2026-10-08T11:00:00Z", "scope": "opus", '
            '"source": "operator"}]}'
        ),
    ],
)
def test_an_unreadable_schedule_is_no_cooldown(tmp_path, content):
    target = codex_pool(tmp_path, "slot-1")
    directory = target.root / "slot-1"
    (directory / COOLDOWNS_FILE).write_text(content)
    assert read_schedule(directory, now=NOW) == []
    assert target.has_claimable_slot()
    with contextlib.ExitStack() as held:
        assert target.acquire(held, wait=False).name == "slot-1"


def test_a_schedule_that_cannot_even_be_opened_is_no_cooldown(tmp_path):
    target = codex_pool(tmp_path, "slot-1")
    directory = target.root / "slot-1"
    os.symlink(directory / "elsewhere.json", directory / COOLDOWNS_FILE)
    assert read_schedule(directory, now=NOW) == []
    (directory / COOLDOWNS_FILE).unlink()
    (directory / COOLDOWNS_FILE).mkdir()
    assert read_schedule(directory, now=NOW) == []
    with contextlib.ExitStack() as held:
        assert target.acquire(held, wait=False).name == "slot-1"


def test_a_write_replaces_an_unreadable_schedule(tmp_path):
    directory = codex_pool(tmp_path, "slot-1").root / "slot-1"
    (directory / COOLDOWNS_FILE).write_text("not json")
    hold(directory, NOW + timedelta(hours=1))
    assert held_until(directory, now=NOW) == NOW + timedelta(hours=1)


def test_extending_moves_the_last_window_in_force_or_starts_one(tmp_path):
    directory = claude_pool(tmp_path, "slot-1").root / "slot-1"
    assert extend_hold(directory, timedelta(hours=1), now=NOW) == NOW + timedelta(hours=1)
    assert extend_hold(directory, timedelta(hours=1), now=NOW) == NOW + timedelta(hours=2)
    hold(directory, NOW + timedelta(hours=5), start=NOW + timedelta(hours=4))
    assert extend_hold(directory, timedelta(hours=1), now=NOW) == NOW + timedelta(hours=3)
    # The window still to come is left where it was, and nothing was added beside it.
    assert [(c.start, c.end) for c in read_schedule(directory, now=NOW)] == [
        (NOW, NOW + timedelta(hours=3)),
        (NOW + timedelta(hours=4), NOW + timedelta(hours=5)),
    ]


def test_extending_a_fable_only_hold_adds_a_hold_on_every_run(tmp_path):
    directory = claude_pool(tmp_path, "slot-1").root / "slot-1"
    hold(directory, NOW + timedelta(hours=4), scope="fable")
    assert extend_hold(directory, timedelta(hours=1), now=NOW) == NOW + timedelta(hours=1)
    assert held_until(directory, model=OPUS, now=NOW) == NOW + timedelta(hours=1)
    assert held_until(directory, model=FABLE, now=NOW) == NOW + timedelta(hours=4)


def test_extending_past_a_year_is_refused_without_writing(tmp_path):
    directory = codex_pool(tmp_path, "slot-1").root / "slot-1"
    hold(directory, NOW + timedelta(days=365))
    before = (directory / COOLDOWNS_FILE).read_bytes()
    with pytest.raises(KarnError, match="cooldown_beyond_horizon"):
        extend_hold(directory, timedelta(hours=1), now=NOW)
    assert (directory / COOLDOWNS_FILE).read_bytes() == before


def test_ending_soon_ends_every_window_in_force_and_leaves_later_ones(tmp_path):
    directory = claude_pool(tmp_path, "slot-1").root / "slot-1"
    assert end_in_force_after(directory, timedelta(seconds=10), now=NOW) is None
    assert not (directory / COOLDOWNS_FILE).exists()
    hold(directory, NOW + timedelta(hours=3))
    hold(directory, NOW + timedelta(hours=2), scope="fable")
    hold(directory, NOW + timedelta(seconds=5))
    hold(directory, NOW + timedelta(hours=9), start=NOW + timedelta(hours=8))
    soon = NOW + timedelta(seconds=10)
    assert end_in_force_after(directory, timedelta(seconds=10), now=NOW) == soon
    assert [(c.start, c.end) for c in read_schedule(directory, now=NOW)] == [
        (NOW, NOW + timedelta(seconds=5)),
        (NOW, soon),
        (NOW, soon),
        (NOW + timedelta(hours=8), NOW + timedelta(hours=9)),
    ]


def test_removing_one_window_or_every_window(tmp_path):
    directory = codex_pool(tmp_path, "slot-1").root / "slot-1"
    first = hold(directory, NOW + timedelta(hours=1))
    hold(directory, NOW + timedelta(hours=9), start=NOW + timedelta(hours=8))
    assert remove_cooldown(directory, first, now=NOW)
    assert not remove_cooldown(directory, first, now=NOW)
    assert len(read_schedule(directory, now=NOW)) == 1
    assert clear_schedule(directory, now=NOW) == 1
    assert clear_schedule(directory, now=NOW) == 0
    assert read_schedule(directory, now=NOW) == []


def test_concurrent_writers_never_lose_each_others_windows(tmp_path):
    directory = codex_pool(tmp_path, "slot-1").root / "slot-1"
    starts = [NOW + timedelta(minutes=minute) for minute in range(1, 41)]

    def write(start):
        hold(directory, start + timedelta(hours=1), start=start)

    threads = [threading.Thread(target=write, args=(start,)) for start in starts]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert [c.start for c in read_schedule(directory, now=NOW)] == starts


# The cooldown file from before schedules ------------------------------------------


def legacy(directory, until, set_at=NOW - timedelta(hours=1)):
    document = {"format": 1, "set_at": set_at.isoformat(), "until": until.isoformat()}
    (directory / LEGACY_COOLDOWN_FILE).write_text(json.dumps(document))


def test_an_old_cooldown_still_holds_until_its_end(tmp_path):
    target = codex_pool(tmp_path, "slot-1")
    directory = target.root / "slot-1"
    legacy(directory, NOW + timedelta(hours=2))
    (window,) = read_schedule(directory, now=NOW)
    assert (window.start, window.end, window.source) == (
        NOW - timedelta(hours=1),
        NOW + timedelta(hours=2),
        "operator",
    )
    assert held_until(directory, now=NOW) == NOW + timedelta(hours=2)
    assert not (directory / COOLDOWNS_FILE).exists()  # reading never converts


def test_an_old_cooldown_without_a_readable_set_at_still_holds(tmp_path):
    directory = codex_pool(tmp_path, "slot-1").root / "slot-1"
    (directory / LEGACY_COOLDOWN_FILE).write_text(
        json.dumps({"until": (NOW + timedelta(hours=2)).isoformat()})
    )
    assert held_until(directory, now=NOW) == NOW + timedelta(hours=2)


def test_an_old_cooldown_written_ahead_of_the_clock_still_holds_now(tmp_path):
    directory = codex_pool(tmp_path, "slot-1").root / "slot-1"
    now = datetime.now(UTC)
    legacy(directory, now + timedelta(hours=2), set_at=now + timedelta(hours=1))
    assert held_until(directory, now=now) == now + timedelta(hours=2)


def test_the_first_write_converts_an_old_cooldown_and_removes_its_file(tmp_path):
    directory = codex_pool(tmp_path, "slot-1").root / "slot-1"
    legacy(directory, NOW + timedelta(hours=2))
    hold(directory, NOW + timedelta(hours=9), start=NOW + timedelta(hours=8))
    assert not (directory / LEGACY_COOLDOWN_FILE).exists()
    assert [entry["end"] for entry in schedule(directory)] == [
        "2026-10-08T14:00:00Z",
        "2026-10-08T21:00:00Z",
    ]


def test_an_old_file_a_crashed_conversion_left_is_never_revived(tmp_path):
    directory = codex_pool(tmp_path, "slot-1").root / "slot-1"
    legacy(directory, NOW + timedelta(hours=2))
    hold(directory, NOW + timedelta(hours=2))
    end_in_force_after(directory, timedelta(seconds=10), now=NOW)
    # As if the conversion had written the schedule and crashed before removing the file.
    legacy(directory, NOW + timedelta(hours=2))
    assert held_until(directory, now=NOW + timedelta(seconds=11)) is None


def test_an_unreadable_old_cooldown_is_no_cooldown(tmp_path):
    directory = codex_pool(tmp_path, "slot-1").root / "slot-1"
    for content in ("not json", "[]", '{"until": 5}', '{"until": "2026-10-08T13:00:00"}'):
        (directory / LEGACY_COOLDOWN_FILE).write_text(content)
        assert read_schedule(directory, now=NOW) == []


# The command -------------------------------------------------------------------


def test_cooldown_holds_named_slots_and_leaves_their_logins_alone(tmp_path):
    target = codex_pool(tmp_path, "slot-1", "slot-2", "slot-3")
    secret = (target.root / "slot-1" / "secret.json").read_bytes()
    result = run_cooldown(
        tmp_path, "--agent", "codex", "--duration", "5h", "--slots", "slot-1", "slot-2"
    )
    assert result.exit_code == 0, result.output
    assert "karn-codex-login/slot-1: cooling down until" in result.output
    for name in ("slot-1", "slot-2"):
        (entry,) = schedule(target.root / name)
        start, end = (datetime.fromisoformat(entry[key]) for key in ("start", "end"))
        assert end - start == timedelta(hours=5)
        assert (entry["scope"], entry["source"]) == ("all", "operator")
        assert held_until(target.root / name) == end
    assert not (target.root / "slot-3" / COOLDOWNS_FILE).exists()
    assert (target.root / "slot-1" / "secret.json").read_bytes() == secret
    assert not (target.root / "slot-1" / "runner.lock").exists()


def test_cooldown_schedules_a_window_with_its_scope_and_note(tmp_path):
    target = claude_pool(tmp_path, "slot-1")
    result = run_cooldown(
        tmp_path,
        "--agent",
        "claude",
        "--slots",
        "slot-1",
        "--from",
        "+2h",
        "--until",
        "+3h",
        "--fable-only",
        "--note",
        "reserved for review week",
    )
    assert result.exit_code == 0, result.output
    assert "Fable runs held from" in result.output
    (entry,) = schedule(target.root / "slot-1")
    start, end = (datetime.fromisoformat(entry[key]) for key in ("start", "end"))
    assert end - start == timedelta(hours=3)  # an end's offset counts from its start
    assert start - datetime.now(UTC) > timedelta(hours=1, minutes=59)
    assert (entry["scope"], entry["note"]) == ("fable", "reserved for review week")


def test_cooldown_takes_slots_as_arguments_too_and_all_takes_every_slot(tmp_path):
    target = codex_pool(tmp_path, "slot-1", "slot-2")
    result = run_cooldown(tmp_path, "--agent", "codex", "--duration", "1h", "slot-1", "slot-2")
    assert result.exit_code == 0, result.output
    assert run_cooldown(tmp_path, "--agent", "codex", "--clear", "--all").exit_code == 0
    assert all(held_until(target.root / name) is None for name in ("slot-1", "slot-2"))
    assert run_cooldown(tmp_path, "--agent", "codex", "--duration", "1h", "--all").exit_code == 0
    assert all(held_until(target.root / name) for name in ("slot-1", "slot-2"))


def test_clearing_removes_every_window_of_only_the_named_slots(tmp_path):
    target = codex_pool(tmp_path, "slot-1", "slot-2")
    run_cooldown(tmp_path, "--agent", "codex", "--duration", "1h", "--all")
    run_cooldown(tmp_path, "--agent", "codex", "--from", "+5h", "--duration", "1h", "--all")
    result = run_cooldown(tmp_path, "--agent", "codex", "--clear", "--slots", "slot-1")
    assert result.exit_code == 0, result.output
    assert "slot-1: 2 cooldown(s) removed" in result.output
    assert read_schedule(target.root / "slot-1") == []
    assert len(read_schedule(target.root / "slot-2")) == 2
    again = run_cooldown(tmp_path, "--agent", "codex", "--clear", "--slots", "slot-1")
    assert "slot-1: no cooldown" in again.output


def test_an_unknown_slot_is_refused_with_the_enrolled_ones_listed(tmp_path):
    target = codex_pool(tmp_path, "slot-1", "slot-2")
    result = run_cooldown(tmp_path, "--agent", "codex", "--duration", "1h", "--slots", "slot-9")
    assert result.exit_code == 2
    assert "slot-9" in result.output and "slot-1, slot-2" in result.output
    assert not (target.root / "slot-9").exists()
    # The other pool's slots are not this pool's.
    claude = run_cooldown(tmp_path, "--agent", "claude", "--duration", "1h", "--slots", "slot-1")
    assert claude.exit_code == 2 and "enrolled: none" in claude.output


@pytest.mark.parametrize(
    "args",
    [
        ["--agent", "codex", "--duration", "1h"],  # no slots
        ["--agent", "codex", "--duration", "1h", "--all", "--slots", "slot-1"],
        ["--agent", "codex", "--slots", "slot-1"],  # neither an end nor clear
        ["--agent", "codex", "--slots", "slot-1", "--from", "+1h"],
        ["--agent", "codex", "--duration", "1h", "--until", "+2h", "--slots", "slot-1"],
        ["--agent", "codex", "--duration", "1h", "--clear", "--slots", "slot-1"],
        ["--agent", "codex", "--clear", "--note", "x", "--slots", "slot-1"],
        ["--agent", "codex", "--clear", "--fable-only", "--slots", "slot-1"],
        ["--agent", "gemini", "--duration", "1h", "--slots", "slot-1"],
    ],
)
def test_cooldown_needs_one_choice_of_slots_and_of_action(tmp_path, args):
    codex_pool(tmp_path, "slot-1")
    assert run_cooldown(tmp_path, *args).exit_code == 2


@pytest.mark.parametrize(
    ("args", "error"),
    [
        (["--duration", "soon"], "invalid_cooldown_duration"),
        (["--until", "soon"], "invalid_cooldown_time"),
        (["--from", "+3h", "--until", "2020-01-01 09:00"], "cooldown_ends_before_it_starts"),
        (["--duration", "300d", "--from", "+100d"], "cooldown_beyond_horizon"),
    ],
)
def test_a_bad_time_is_reported_without_writing(tmp_path, args, error):
    target = codex_pool(tmp_path, "slot-1")
    result = run_cooldown(tmp_path, "--agent", "codex", "--slots", "slot-1", *args)
    assert result.exit_code == 1 and error in result.output
    assert not (target.root / "slot-1" / COOLDOWNS_FILE).exists()


def test_enrolling_still_needs_its_build_and_construct(tmp_path):
    result = CliRunner().invoke(main, ["login", "--state-root", str(tmp_path / "state")])
    assert result.exit_code == 2
    assert "--build-output" in result.output and "--construct" in result.output


# Acquisition -------------------------------------------------------------------


def test_acquisition_passes_over_a_slot_with_a_window_in_force(tmp_path):
    target = codex_pool(tmp_path, "slot-1", "slot-2")
    now = datetime.now(UTC)
    hold(target.root / "slot-1", now + timedelta(hours=1), now=now)
    with contextlib.ExitStack() as held:
        assert target.acquire(held, poll_seconds=0.01).name == "slot-2"


def test_a_window_still_to_come_holds_nothing_back_yet(tmp_path):
    target = codex_pool(tmp_path, "slot-1")
    now = datetime.now(UTC)
    hold(target.root / "slot-1", now + timedelta(hours=2), now=now, start=now + timedelta(hours=1))
    assert target.has_claimable_slot()
    with contextlib.ExitStack() as held:
        assert target.acquire(held, wait=False).name == "slot-1"


def test_a_fable_only_window_keeps_only_fable_runs_off_the_slot(tmp_path):
    target = claude_pool(tmp_path, "slot-1")
    now = datetime.now(UTC)
    hold(target.root / "slot-1", now + timedelta(hours=1), now=now, scope="fable")
    assert not target.has_claimable_slot(model=FABLE)
    assert target.has_claimable_slot(model=OPUS)
    assert target.has_claimable_slot()
    with contextlib.ExitStack() as held, pytest.raises(LoginPoolBusyError):
        target.acquire(held, wait=False, model=FABLE)
    with contextlib.ExitStack() as held:
        assert target.acquire(held, wait=False, model=OPUS).name == "slot-1"


def test_a_window_for_every_run_keeps_a_run_of_any_model_off(tmp_path):
    target = claude_pool(tmp_path, "slot-1")
    now = datetime.now(UTC)
    hold(target.root / "slot-1", now + timedelta(hours=1), now=now)
    for model in (FABLE, OPUS, None):
        assert not target.has_claimable_slot(model=model)
        with contextlib.ExitStack() as held, pytest.raises(LoginPoolBusyError):
            target.acquire(held, wait=False, model=model)


def test_a_run_waits_while_every_slot_cools_down_and_takes_one_when_it_ends(tmp_path):
    target = codex_pool(tmp_path, "slot-1")
    now = datetime.now(UTC)
    # Two seconds: the stored end is cut to whole seconds, so at least one is left to wait.
    hold(target.root / "slot-1", now + timedelta(seconds=2), now=now)
    waited: list[str] = []
    started = time.monotonic()
    with contextlib.ExitStack() as held:
        profile = target.acquire(held, poll_seconds=0.05, on_wait=waited.append)
    assert profile.name == "slot-1"
    assert time.monotonic() - started >= 0.5
    assert waited == [
        "waiting for a login slot: all 1 usable karn-codex-login slots are cooling down"
    ]


def test_a_cooldown_never_disturbs_the_run_already_holding_the_slot(tmp_path):
    target = codex_pool(tmp_path, "slot-1")
    profile = target.slot("slot-1")
    with held_elsewhere(profile):
        result = run_cooldown(tmp_path, "--agent", "codex", "--duration", "1h", "--slots", "slot-1")
        assert result.exit_code == 0, result.output
    assert held_until(target.root / "slot-1") is not None


def test_a_cooldown_removed_while_waiting_lets_the_run_through(tmp_path):
    target = codex_pool(tmp_path, "slot-1")
    now = datetime.now(UTC)
    hold(target.root / "slot-1", now + timedelta(hours=1), now=now)
    taken = threading.Event()

    def take():
        with contextlib.ExitStack() as held:
            target.acquire(held, poll_seconds=0.02, on_wait=lambda message: None)
            taken.set()

    worker = threading.Thread(target=take, daemon=True)
    worker.start()
    time.sleep(0.2)
    assert not taken.is_set()
    clear_schedule(target.root / "slot-1", now=datetime.now(UTC))
    assert taken.wait(timeout=5)


# The monitor -------------------------------------------------------------------


def test_the_monitor_reads_each_profiles_schedule_without_writing(tmp_path):
    target = claude_pool(tmp_path, "slot-1", "slot-2", "slot-3", "slot-4")
    hold(target.root / "slot-2", NOW + timedelta(hours=3))
    hold(target.root / "slot-3", NOW + timedelta(hours=2), scope="fable")
    hold(target.root / "slot-4", NOW + timedelta(hours=9), start=NOW + timedelta(hours=8))
    before = sorted(path.name for path in target.root.rglob("*"))
    profiles = {
        view.slot: view for view in login_profiles(tmp_path / "state", frozenset(), now=NOW)
    }
    assert profiles["slot-1"].cooldown_until is None and profiles["slot-1"].cooldowns == ()
    assert profiles["slot-2"].cooldown_until == NOW + timedelta(hours=3)
    assert profiles["slot-3"].cooldown_until is None
    assert profiles["slot-3"].fable_cooldown_until == NOW + timedelta(hours=2)
    assert profiles["slot-4"].next_cooldown == NOW + timedelta(hours=8)
    assert profiles["slot-4"].cooldown_until is None
    # A Fable-only window or one still to come leaves the profile free for a new run.
    assert [profiles[name].free for name in ("slot-1", "slot-2", "slot-3", "slot-4")] == [
        True,
        False,
        True,
        True,
    ]
    later = login_profiles(tmp_path / "state", frozenset(), now=NOW + timedelta(hours=8, minutes=1))
    assert [view.cooldown_until for view in later] == [None, None, None, NOW + timedelta(hours=9)]
    assert sorted(path.name for path in target.root.rglob("*")) == before


def _two_roots(tmp_path, monkeypatch, *names):
    """The same slot names enrolled under an explicit root and under the configured one."""
    explicit, configured = tmp_path / "explicit", tmp_path / "configured"
    for root in (explicit, configured):
        target = LoginPool.of(root, "karn-codex-login")
        for name in names:
            enroll(target.named_slot(name), target.plugin_id)
    config_home = tmp_path / "xdg"
    (config_home / "silverquillm").mkdir(parents=True)
    (config_home / "silverquillm" / "config.toml").write_text(f'state_root = "{configured}"\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    return explicit, configured


def _tree(root):
    return {
        path.relative_to(root): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _slot(root, name):
    return LoginPool.of(root, "karn-codex-login").root / name


def _invoke(group_root, sub_root, *args):
    group = ["--state-root", str(group_root)] if group_root else []
    sub = ["--state-root", str(sub_root)] if sub_root else []
    return CliRunner().invoke(main, ["login", *group, "cooldown", *sub, "--agent", "codex", *args])


@pytest.mark.parametrize("placement", ["before", "after", "both"])
@pytest.mark.parametrize("selection", [("--slots", "slot-1"), ("--all",)])
def test_an_explicit_state_root_chooses_the_pool_wherever_it_is_given(
    tmp_path, monkeypatch, placement, selection
):
    explicit, configured = _two_roots(tmp_path, monkeypatch, "slot-1", "slot-2")
    decoy = tmp_path / "decoy"
    group_root = {"before": explicit, "after": None, "both": decoy}[placement]
    sub_root = {"before": None, "after": explicit, "both": explicit}[placement]
    untouched = _tree(configured)

    result = _invoke(group_root, sub_root, "--duration", "1h", *selection)
    assert result.exit_code == 0, result.output
    assert held_until(_slot(explicit, "slot-1")) is not None
    assert _tree(configured) == untouched
    assert not decoy.exists()

    lift = _invoke(group_root, sub_root, "--clear", *selection)
    assert lift.exit_code == 0, lift.output
    assert "cooldown(s) removed" in lift.output
    assert held_until(_slot(explicit, "slot-1")) is None
    assert _tree(configured) == untouched


def test_without_a_flag_the_configured_state_root_holds_the_slot(tmp_path, monkeypatch):
    explicit, configured = _two_roots(tmp_path, monkeypatch, "slot-1")
    untouched = _tree(explicit)
    result = _invoke(None, None, "--duration", "1h", "--slots", "slot-1")
    assert result.exit_code == 0, result.output
    assert held_until(_slot(configured, "slot-1")) is not None
    assert _tree(explicit) == untouched


@pytest.mark.parametrize("placement", ["before", "after"])
def test_an_unknown_slot_in_the_chosen_root_never_falls_back_to_another_pool(
    tmp_path, monkeypatch, placement
):
    explicit, configured = _two_roots(tmp_path, monkeypatch, "slot-1")
    elsewhere = LoginPool.of(configured, "karn-codex-login")
    enroll(elsewhere.named_slot("slot-9"), elsewhere.plugin_id)
    before = (_tree(explicit), _tree(configured))
    group_root, sub_root = (explicit, None) if placement == "before" else (None, explicit)
    result = _invoke(group_root, sub_root, "--duration", "1h", "--slots", "slot-9")
    assert result.exit_code == 2
    assert "Not enrolled in the codex pool: slot-9 (enrolled: slot-1)" in result.output
    assert (_tree(explicit), _tree(configured)) == before
