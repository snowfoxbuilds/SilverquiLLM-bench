"""The capacity view: Login Pools and GPU Slots with their Cooldown Schedules and Usage
Limits, and the forms and keys that write them (RUN-MONITORING.md, Capacity view)."""

from __future__ import annotations

import fcntl
import os
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("textual")

from textual.widgets import Checkbox, DataTable, Input

from silverquillm.karn.cooldowns import add_cooldown, cooldown, held_until, read_schedule
from silverquillm.karn.login_pool import LoginPool, logins_root
from silverquillm.karn.model_server import gpu_schedule_dir, writable_gpu_schedule_dir
from silverquillm.karn.usage_limit import UsageLimit, read_limit, set_limit
from silverquillm.monitor.gpus import GpuSlotStatus, orphaned_gpu_schedules
from silverquillm.monitor.history import FABLE, WEEKLY, UsageReading
from silverquillm.top import cooldowns, slots
from silverquillm.top import format as fmt
from silverquillm.top.app import build_app
from silverquillm.top.capacity import CapacityView
from silverquillm.top.forms import ConfirmCooldownRemove, CooldownForm, LimitForm
from silverquillm.top.theme import MTG, PLAIN

from .test_karn_login_pool import enroll
from .test_monitor import NOW as RECORDS_NOW
from .test_monitor import make_run, publish, retain
from .test_monitor_records import PROFILE, Host, claude_usage
from .test_top import _app, _settle, synchronous
from .test_top_cooldowns import _host, _recorded
from .test_top_gpu_slots import h100
from .test_top_slots import _suspended
from .top_fixtures import NOW, FakeMonitor, profiles

STATE = ".local/state/silverquillm"


def _host_with_disk(tmp_path, monkeypatch, gpu_values=()):
    """The fixtures' monitor, with each profile's schedule and limit, and the GPU Slots,
    read from this host's state root as the real monitor reads them, so a write shows."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monitor, pool = _host(tmp_path)
    claude = LoginPool.of(tmp_path / STATE, "karn-claude-login")
    enroll(claude.named_slot("claude-5"), claude.plugin_id)
    state = tmp_path / STATE
    base = monitor.snapshot

    def snapshot():
        taken = base()
        profiles = []
        for view in taken.profiles:
            directory = logins_root(state) / view.status.plugin_id / view.status.slot
            schedule = tuple(read_schedule(directory, now=NOW)) if directory.is_dir() else ()
            limit = read_limit(directory) if directory.is_dir() else None
            held = held_until(directory, now=NOW) if directory.is_dir() else None
            status = replace(
                view.status, cooldowns=schedule, usage_limit=limit, cooldown_until=held
            )
            profiles.append(replace(view, status=status))
        gpus = [
            GpuSlotStatus(
                value,
                False,
                None,
                (h100(int(value)),),
                cooldowns=tuple(read_schedule(gpu_schedule_dir(state, value), now=NOW)),
            )
            for value in gpu_values
        ]
        orphans = orphaned_gpu_schedules(state, tuple(gpu_values), now=NOW)
        return replace(taken, profiles=profiles, gpu_slots=gpus, orphaned_gpu_schedules=orphans)

    monitor.snapshot = snapshot
    return monitor, pool, state


async def _select(pilot, app, table_id: str, name: str) -> CapacityView:
    """From the capacity view's first table, tab to ``table_id`` and arrow down to ``name``."""
    view = app.query_one(CapacityView)
    for _ in range(4):
        if app.focused is not None and app.focused.id == table_id:
            break
        await pilot.press("tab")
    assert app.focused.id == table_id
    names = [target.name for target in view._rows[table_id]]
    for _ in range(names.index(name)):
        await pilot.press("down")
    await pilot.pause()
    assert view.selected is not None and view.selected.name == name
    return view


def _fill(app, **values) -> None:
    for field, value in values.items():
        app.screen.query_one(f"#form-{field}", Input).value = value


async def _wait_for(pilot, app, predicate, timeout=10.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "the background write never reported back"
        await pilot.pause(0.05)
    await _settle(app, pilot)


@synchronous
async def test_4_opens_the_capacity_view_with_one_table_per_pool(tmp_path, monkeypatch):
    monitor, _, _ = _host_with_disk(tmp_path, monkeypatch)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        await pilot.press("4")
        await pilot.pause()
        assert app.query_one("#switcher").current == "capacity"
        assert app.focused.id == "capacity-claude"
        claude = app.query_one("#capacity-claude", DataTable)
        codex = app.query_one("#capacity-codex", DataTable)
        assert (claude.row_count, codex.row_count) == (6, 6)
        assert not app.query_one("#capacity-gpus", DataTable).display
        footer = str(app.query_one("#keys").render())
        assert "1/2/3/4 views" in footer and "n add" in footer and "L limit" in footer
        names = [target.name for target in app.query_one(CapacityView)._rows["capacity-codex"]]
        row = [cell.plain for cell in codex.get_row_at(names.index("slot-1"))]
        assert "slot-1" in row[0] and row[1] == "busy" and "47%" in row[3]
        await pilot.press("1")
        assert app.query_one("#switcher").current == "dashboard"


@synchronous
async def test_selecting_a_row_lists_its_schedule_soonest_first(tmp_path, monkeypatch):
    monitor, pool, _ = _host_with_disk(tmp_path, monkeypatch)
    later = cooldown(NOW + timedelta(days=1), NOW + timedelta(days=2), now=NOW, note="maintenance")
    current = cooldown(NOW - timedelta(hours=1), NOW + timedelta(hours=2), now=NOW)
    add_cooldown(pool.root / "slot-3", later, now=NOW)
    add_cooldown(pool.root / "slot-3", current, now=NOW)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        await pilot.press("4")
        view = await _select(pilot, app, "capacity-codex", "slot-3")
        schedule = app.query_one("#schedule-table", DataTable)
        assert schedule.row_count == 2
        first, second = ([cell.plain for cell in schedule.get_row_at(i)] for i in range(2))
        assert first[0] == MTG_COOLDOWN and first[1] == fmt.stamp(current.start)
        assert second[0] != MTG_COOLDOWN and second[6] == "maintenance"
        assert app.query_one("#capacity-schedule").border_subtitle == "karn-codex-login/slot-3"
        await pilot.press("down")
        await pilot.pause()
        assert view.selected.name == "slot-4"
        assert not schedule.display


MTG_COOLDOWN = "❄"


@synchronous
async def test_n_adds_a_cooldown_typed_in_the_form(tmp_path, monkeypatch):
    monitor, pool, _ = _host_with_disk(tmp_path, monkeypatch)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        notes = _recorded(app)
        await pilot.press("4")
        await _select(pilot, app, "capacity-codex", "slot-1")
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, CooldownForm)
        assert not app.screen.query(Checkbox), "a Codex profile has no Fable-only scope"
        # Typed by keyboard: start, tab to the end, tab to the note, enter.
        await pilot.press("plus", "1", "h", "tab", "plus", "2", "h", "tab", "o", "k", "enter")
        await _settle(app, pilot)
        assert not isinstance(app.screen, CooldownForm)
        (window,) = read_schedule(pool.root / "slot-1", now=NOW)
        assert (window.start, window.end) == (NOW + timedelta(hours=1), NOW + timedelta(hours=3))
        assert (window.note, window.source, window.scope) == ("ok", "operator", "all")
        assert notes[-1][1] is None and "cooldown added" in notes[-1][0]
        assert app.query_one("#schedule-table", DataTable).row_count == 1


@synchronous
async def test_a_form_refuses_what_it_cannot_read_and_stays_open(tmp_path, monkeypatch):
    monitor, pool, _ = _host_with_disk(tmp_path, monkeypatch)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        await pilot.press("4")
        await _select(pilot, app, "capacity-codex", "slot-2")
        await pilot.press("n")
        await pilot.pause()
        _fill(app, start="", end="whenever")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, CooldownForm)
        assert "invalid_cooldown_time" in str(app.screen.query_one("#form-error").render())
        _fill(app, end="")
        await pilot.press("enter")
        await pilot.pause()
        assert "cooldown_end_needed" in str(app.screen.query_one("#form-error").render())
        await pilot.press("escape")
        await _settle(app, pilot)
        assert not isinstance(app.screen, CooldownForm)
    assert read_schedule(pool.root / "slot-2", now=NOW) == []


@synchronous
async def test_e_changes_a_cooldown_keeping_its_source_and_untouched_times(tmp_path, monkeypatch):
    monitor, pool, _ = _host_with_disk(tmp_path, monkeypatch)
    start = NOW - timedelta(minutes=17, seconds=41)
    tripped = cooldown(
        start,
        NOW + timedelta(days=2, seconds=13),
        now=NOW - timedelta(hours=1),
        source="usage-limit",
    )
    add_cooldown(pool.root / "slot-4", tripped, now=NOW)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        await pilot.press("4")
        await _select(pilot, app, "capacity-codex", "slot-4")
        await pilot.press("e")
        await pilot.pause()
        form = app.screen
        assert isinstance(form, CooldownForm)
        assert form.query_one("#form-start", Input).value == fmt.stamp(tripped.start)
        _fill(app, note="reserved for review")
        await pilot.press("enter")
        await _settle(app, pilot)
    (changed,) = read_schedule(pool.root / "slot-4", now=NOW)
    assert (changed.start, changed.end) == (tripped.start, tripped.end)
    assert (changed.source, changed.note) == ("usage-limit", "reserved for review")


@synchronous
async def test_x_removes_a_cooldown_only_after_y(tmp_path, monkeypatch):
    monitor, pool, _ = _host_with_disk(tmp_path, monkeypatch)
    tripped = cooldown(NOW, NOW + timedelta(days=1), now=NOW, source="usage-limit")
    add_cooldown(pool.root / "slot-5", tripped, now=NOW)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        notes = _recorded(app)
        await pilot.press("4")
        await _select(pilot, app, "capacity-codex", "slot-5")
        await pilot.press("x")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmCooldownRemove)
        assert "next run's release checks" in str(app.screen.query_one("#confirm Static").render())
        await pilot.press("n")
        await _settle(app, pilot)
        assert read_schedule(pool.root / "slot-5", now=NOW) == [tripped]
        await pilot.press("x")
        await pilot.pause()
        await pilot.press("y")
        await _settle(app, pilot)
        assert read_schedule(pool.root / "slot-5", now=NOW) == []
        assert "cooldown removed" in notes[-1][0]


@synchronous
async def test_l_sets_checks_and_clears_a_usage_limit(tmp_path, monkeypatch):
    monitor, pool, state = _host_with_disk(tmp_path, monkeypatch)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        notes = _recorded(app)
        await pilot.press("4")
        await _select(pilot, app, "capacity-codex", "slot-2")
        await pilot.press("L")
        await pilot.pause()
        assert isinstance(app.screen, LimitForm)
        assert not app.screen.query("#form-fable-limit"), "only Claude has a Fable limit"
        _fill(app, weekly="150")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, LimitForm)
        assert "invalid_usage_limit" in str(app.screen.query_one("#form-error").render())
        _fill(app, weekly="80%")
        await pilot.press("enter")
        await _wait_for(pilot, app, lambda: any("limit set" in note for note, _ in notes))
        assert read_limit(pool.root / "slot-2") == UsageLimit(80.0, None)
        view = app.query_one(CapacityView)
        row = [target.name for target in view._rows["capacity-codex"]].index("slot-2")
        assert "weekly 80%" in app.query_one("#capacity-codex", DataTable).get_row_at(row)[5].plain
        await pilot.press("L")
        await pilot.pause()
        assert app.screen.query_one("#form-weekly", Input).value == "80"
        _fill(app, weekly="")
        await pilot.press("enter")
        await _settle(app, pilot)
        assert read_limit(pool.root / "slot-2") is None
        assert notes[-1] == ("karn-codex-login/slot-2: limit removed", None)
        claude = logins_root(state) / "karn-claude-login" / "claude-5"
        await pilot.press("shift+tab")
        await _select(pilot, app, "capacity-claude", "claude-5")
        await pilot.press("L")
        await pilot.pause()
        _fill(app, weekly="", **{"fable-limit": "90"})
        await pilot.press("enter")
        await _wait_for(pilot, app, lambda: read_limit(claude) is not None)
    assert read_limit(claude) == UsageLimit(None, 90.0)


@synchronous
async def test_a_claude_profile_takes_a_fable_only_cooldown(tmp_path, monkeypatch):
    monitor, _, state = _host_with_disk(tmp_path, monkeypatch)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        await pilot.press("4")
        await _select(pilot, app, "capacity-claude", "claude-5")
        await pilot.press("n")
        await pilot.pause()
        _fill(app, start="", end="+4h")
        app.screen.query_one("#form-fable", Checkbox).value = True
        await pilot.press("enter")
        await _settle(app, pilot)
    (window,) = read_schedule(logins_root(state) / "karn-claude-login" / "claude-5", now=NOW)
    assert (window.scope, window.start, window.end) == ("fable", NOW, NOW + timedelta(hours=4))


@synchronous
async def test_n_on_a_gpu_slot_writes_its_own_schedule(tmp_path, monkeypatch):
    monitor, _, state = _host_with_disk(tmp_path, monkeypatch, gpu_values=("0", "1"))
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        await pilot.press("4")
        gpus = app.query_one("#capacity-gpus", DataTable)
        assert gpus.display and gpus.row_count == 2
        await _select(pilot, app, "capacity-gpus", "1")
        await pilot.press("n")
        await pilot.pause()
        assert not app.screen.query("#form-fable"), "a GPU Slot's Cooldowns hold back every run"
        assert app.screen.query_one("#form-extend", Checkbox).value, "extending is the default"
        _fill(app, start="+1h", end="+3h", note="training")
        await pilot.press("enter")
        await _settle(app, pilot)
        assert app.query_one("#schedule-table", DataTable).row_count == 1
    (window,) = read_schedule(gpu_schedule_dir(state, "1"), now=NOW)
    # An offset end counts from the start, as ``gpu cooldown --until +3h`` does.
    assert (window.start, window.end, window.note) == (
        NOW + timedelta(hours=1),
        NOW + timedelta(hours=4),
        "training",
    )
    assert window.extend, "a GPU Cooldown extends while its GPUs are used outside the bench"
    assert read_schedule(gpu_schedule_dir(state, "0"), now=NOW) == []


@synchronous
async def test_an_unchecked_extend_box_writes_a_gpu_cooldown_that_ends_on_time(
    tmp_path, monkeypatch
):
    monitor, _, state = _host_with_disk(tmp_path, monkeypatch, gpu_values=("0",))
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        notes = _recorded(app)
        await pilot.press("4")
        await _select(pilot, app, "capacity-gpus", "0")
        await pilot.press("n")
        await pilot.pause()
        app.screen.query_one("#form-extend", Checkbox).value = False
        _fill(app, end="+2h")
        await pilot.press("enter")
        await _settle(app, pilot)
        assert "ends on time" in notes[-1][0]
        scope = app.query_one("#schedule-table", DataTable).get_row_at(0)[3].plain
        assert "ends on time" in scope
    (window,) = read_schedule(gpu_schedule_dir(state, "0"), now=NOW)
    assert not window.extend, "an unchecked box is --no-extend"


@synchronous
async def test_a_login_profiles_form_offers_no_extend_box(tmp_path, monkeypatch):
    monitor, _, _ = _host_with_disk(tmp_path, monkeypatch)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        await pilot.press("4")
        await _select(pilot, app, "capacity-codex", "slot-4")
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, CooldownForm)
        assert not app.screen.query("#form-extend")


@synchronous
async def test_an_extended_gpu_cooldown_shows_its_count_and_an_edit_stops_extending_it(
    tmp_path, monkeypatch
):
    monitor, _, state = _host_with_disk(tmp_path, monkeypatch, gpu_values=("0",))
    held = replace(
        cooldown(NOW - timedelta(hours=2), NOW + timedelta(minutes=20), now=NOW, extend=True),
        extensions=2,
    )
    add_cooldown(writable_gpu_schedule_dir(state, "0"), held, now=NOW)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        notes = _recorded(app)
        await pilot.press("4")
        await _select(pilot, app, "capacity-gpus", "0")
        schedule = app.query_one("#schedule-table", DataTable)
        assert "busy +2" in schedule.get_row_at(0)[3].plain
        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, CooldownForm)
        assert not app.screen.query("#form-extend"), "an edit always stops extending"
        # An offset end counts from the kept start, two hours ago.
        _fill(app, end="+3h")
        await pilot.press("enter")
        await _settle(app, pilot)
        assert "ends on time" in notes[-1][0]
    (edited,) = read_schedule(gpu_schedule_dir(state, "0"), now=NOW)
    assert not edited.extend, "the operator's edit overrides extension"
    assert edited.extensions == 2, "the count of extensions so far is kept"
    assert edited.end == NOW + timedelta(hours=1)


@synchronous
async def test_x_removes_an_extending_gpu_cooldown_outright(tmp_path, monkeypatch):
    monitor, _, state = _host_with_disk(tmp_path, monkeypatch, gpu_values=("0",))
    held = cooldown(NOW - timedelta(hours=1), NOW + timedelta(hours=1), now=NOW, extend=True)
    add_cooldown(writable_gpu_schedule_dir(state, "0"), held, now=NOW)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        await pilot.press("4")
        await _select(pilot, app, "capacity-gpus", "0")
        await pilot.press("x")
        await pilot.pause()
        await pilot.press("y")
        await _settle(app, pilot)
    assert read_schedule(gpu_schedule_dir(state, "0"), now=NOW) == []


@synchronous
async def test_an_orphaned_schedule_is_listed_and_removable_but_takes_no_cooldown(
    tmp_path, monkeypatch
):
    monitor, _, state = _host_with_disk(tmp_path, monkeypatch, gpu_values=("0",))
    left = cooldown(NOW, NOW + timedelta(hours=5), now=NOW, note="old slot")
    add_cooldown(writable_gpu_schedule_dir(state, "7"), left, now=NOW)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        notes = _recorded(app)
        await pilot.press("4")
        gpus = app.query_one("#capacity-gpus", DataTable)
        assert gpus.get_row_at(1)[1].plain == "orphaned"
        await _select(pilot, app, "capacity-gpus", "7")
        await pilot.press("n")
        await pilot.pause()
        assert not isinstance(app.screen, CooldownForm)
        assert "not in gpu_slots" in notes[-1][0]
        await pilot.press("x")
        await pilot.pause()
        await pilot.press("y")
        await _settle(app, pilot)
        assert gpus.row_count == 1, "an emptied orphaned schedule is no longer listed"
    assert read_schedule(gpu_schedule_dir(state, "7"), now=NOW) == []


@synchronous
async def test_a_r_and_d_manage_slots_from_the_capacity_view(tmp_path, monkeypatch):
    monitor, pool, _ = _host_with_disk(tmp_path, monkeypatch)
    app = _app(monitor)
    calls = _suspended(app, monkeypatch)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        await pilot.press("4")
        await _select(pilot, app, "capacity-codex", "slot-3")
        await pilot.press("R")
        await _settle(app, pilot)
        await pilot.press("a")
        await _settle(app, pilot)
        await pilot.press("D")
        await pilot.pause()
        assert isinstance(app.screen, slots.ConfirmRemove)
        await pilot.press("n")
        await _settle(app, pilot)
    root = tmp_path / STATE
    assert calls == [(root, "karn-codex-login", "slot-3"), (root, "karn-codex-login", None)]
    assert "slot-3" in pool.enrolled()


@synchronous
async def test_the_plain_theme_draws_the_capacity_view(tmp_path, monkeypatch):
    monitor, pool, _ = _host_with_disk(tmp_path, monkeypatch, gpu_values=("0",))
    add_cooldown(pool.root / "slot-1", cooldown(NOW, NOW + timedelta(hours=1), now=NOW), now=NOW)
    set_limit(pool.root / "slot-1", UsageLimit(75.0, None), now=NOW)
    app = _app(monitor, theme=PLAIN)
    async with app.run_test(size=(120, 40)) as pilot:
        await _settle(app, pilot)
        await pilot.press("4")
        view = await _select(pilot, app, "capacity-codex", "slot-1")
        index = [target.name for target in view._rows["capacity-codex"]].index("slot-1")
        table = app.query_one("#capacity-codex", DataTable)
        row = [cell.plain for cell in table.get_row_at(index)]
        assert row[5] == "weekly 75%" and "until" in row[6]
        mark = app.query_one("#schedule-table", DataTable).get_row_at(0)[0].plain
        assert mark == PLAIN.glyph("cooldown")


# Keeping the selected row on screen --------------------------------------------------


def _tall(*, claude=30, codex=6, gpus=4):
    """A monitor with more rows than the CAPACITY pane holds at 120×40. Each profile and GPU
    Slot has two Cooldowns noting its own name, so the schedule shown tells whose it is;
    ``extra`` profiles, when set, enrol ahead of every other in the Claude pool, and
    ``claude`` is how many follow them."""
    monitor = FakeMonitor()
    base = monitor.snapshot
    template = {view.status.provider: view for view in profiles()}
    monitor.extra = 0
    monitor.claude = claude

    def noted(name):
        return tuple(
            cooldown(later, later + timedelta(hours=1), now=NOW, note=name)
            for later in (NOW + timedelta(days=1), NOW + timedelta(days=2))
        )

    def view(provider, slot):
        model = template[provider]
        status = replace(model.status, slot=slot, cooldowns=noted(slot), busy=False)
        return replace(model, status=status, run_id=None)

    def snapshot():
        views = [view("claude", f"a-{n:02d}") for n in range(monitor.extra)]
        views += [view("claude", f"c-{n:02d}") for n in range(monitor.claude)]
        views += [view("codex", f"x-{n:02d}") for n in range(codex)]
        slots_ = [
            GpuSlotStatus(str(n), False, None, (h100(n),), cooldowns=noted(f"gpu {n}"))
            for n in range(gpus)
        ]
        return replace(base(), profiles=views, gpu_slots=slots_)

    monitor.snapshot = snapshot
    return monitor


def _on_screen(app) -> None:
    """The focused table's cursor row is drawn inside the CAPACITY pane, it is the selected
    target's row, and the schedule shown is that target's."""
    table = app.focused
    view = app.query_one(CapacityView)
    pane = app.query_one("#capacity-tables")
    y = table.region.y + table.header_height + table.cursor_row - round(table.scroll_y)
    visible = pane.scrollable_content_region
    assert visible.y <= y < visible.bottom, (y, visible, pane.scroll_y)
    assert app.screen.get_widget_at(table.region.x + 2, y)[0] is table
    target = view._rows[table.id][table.cursor_row]
    assert view.selected == target
    drawn = app.screen._compositor.render_strips()[y].text
    assert target.name in drawn
    schedule = app.query_one("#schedule-table", DataTable)
    assert [cell.plain for cell in schedule.get_row_at(0)][6] == (
        target.label if target.gpu else target.name
    )
    assert app.query_one("#capacity-schedule").border_subtitle == target.label


@synchronous
async def test_moving_down_a_pool_taller_than_the_pane_keeps_the_row_in_view():
    app = _app(_tall())
    async with app.run_test(size=(120, 40)) as pilot:
        await _settle(app, pilot)
        await pilot.press("4")
        await pilot.pause()
        assert app.focused.id == "capacity-claude"
        for index in range(1, 30):
            await pilot.press("down")
            await pilot.pause()
            assert app.focused.cursor_row == index
            _on_screen(app)
        assert app.query_one("#capacity-tables").scroll_y > 0
        for index in reversed(range(29)):
            await pilot.press("up")
            await pilot.pause()
            assert app.focused.cursor_row == index
            _on_screen(app)


@synchronous
async def test_a_lower_pool_and_the_gpu_table_keep_their_rows_in_view_both_ways():
    app = _app(_tall(claude=30, codex=30, gpus=26))
    async with app.run_test(size=(120, 40)) as pilot:
        await _settle(app, pilot)
        await pilot.press("4")
        await pilot.pause()
        for table_id, rows in (("capacity-codex", 30), ("capacity-gpus", 26)):
            await pilot.press("tab")
            await pilot.pause()
            assert app.focused.id == table_id
            _on_screen(app)
            for index in range(1, rows):
                await pilot.press("down")
                await pilot.pause()
                assert app.focused.cursor_row == index
                _on_screen(app)
        assert app.query_one(CapacityView).selected.label == "gpu 25"
        # Back to the Codex pool, whose cursor rests on its last row, then up it.
        await pilot.press("shift+tab")
        await pilot.pause()
        assert (app.focused.id, app.focused.cursor_row) == ("capacity-codex", 29)
        _on_screen(app)
        for index in reversed(range(29)):
            await pilot.press("up")
            await pilot.pause()
            _on_screen(app)


@synchronous
async def test_a_smaller_terminal_and_a_poll_while_scrolled_keep_the_row_in_view():
    monitor = _tall()
    app = _app(monitor)
    async with app.run_test(size=(120, 40)) as pilot:
        await _settle(app, pilot)
        await pilot.press("4")
        await pilot.pause()
        for _ in range(20):
            await pilot.press("down")
        await pilot.pause()
        _on_screen(app)
        await pilot.resize_terminal(120, 28)
        await pilot.pause()
        await pilot.pause()
        _on_screen(app)
        await pilot.press("r")
        await _settle(app, pilot)
        _on_screen(app)
        # Profiles enrolled ahead of the selection move it down the pane; a poll follows it.
        monitor.extra = 10
        await pilot.press("r")
        await _settle(app, pilot)
        assert app.query_one(CapacityView).selected.name == "c-20"
        assert app.focused.cursor_row == 30
        _on_screen(app)


async def _gpu_25_schedule(pilot, app):
    """GPU 25 selected by keyboard, then its schedule focused on its second Cooldown."""
    await _settle(app, pilot)
    await pilot.press("4")
    view = await _select(pilot, app, "capacity-gpus", "25")
    await pilot.press("tab")
    await pilot.press("down")
    await pilot.pause()
    assert app.focused.id == "schedule-table"
    chosen = view.selected_cooldown
    assert chosen is not None and chosen.start == NOW + timedelta(days=2)
    _selected_on_screen(app, "gpu 25", chosen)
    return chosen


def _selected_on_screen(app, label: str, chosen) -> None:
    """With the schedule focused on ``chosen``, the selected resource is still ``label``, its
    row is drawn inside the CAPACITY pane, and the schedule shown is still its own."""
    view = app.query_one(CapacityView)
    assert view.selected is not None and view.selected.label == label
    assert app.focused.id == "schedule-table"
    assert view.selected_cooldown == chosen
    table_id, index = next(
        (table_id, targets.index(view.selected))
        for table_id, targets in view._rows.items()
        if view.selected in targets
    )
    table = app.query_one(f"#{table_id}", DataTable)
    pane = app.query_one("#capacity-tables")
    y = table.region.y + table.header_height + index - round(table.scroll_y)
    visible = pane.scrollable_content_region
    assert visible.y <= y < visible.bottom, (y, visible, pane.scroll_y)
    assert app.screen.get_widget_at(table.region.x + 2, y)[0] is table
    assert table.get_row_at(index)[0].plain.strip().endswith(view.selected.name)
    assert view.selected.name in app.screen._compositor.render_strips()[y].text
    schedule = app.query_one("#schedule-table", DataTable)
    notes = [schedule.get_row_at(row)[6].plain for row in range(schedule.row_count)]
    assert notes == [label, label]
    assert app.query_one("#capacity-schedule").border_subtitle == label


@synchronous
@pytest.mark.parametrize("claude", [40, 20], ids=["enrolled-above", "removed-above"])
async def test_a_poll_moving_the_resource_keeps_it_in_view_while_its_schedule_has_focus(claude):
    monitor = _tall(claude=30, codex=30, gpus=26)
    app = _app(monitor)
    async with app.run_test(size=(120, 40)) as pilot:
        chosen = await _gpu_25_schedule(pilot, app)
        if claude > 30:
            monitor.extra = claude - 30
        else:
            monitor.claude = claude
        await pilot.press("r")
        await _settle(app, pilot)
        assert len(app.query_one(CapacityView)._rows["capacity-claude"]) == claude
        _selected_on_screen(app, "gpu 25", chosen)


@synchronous
async def test_a_smaller_terminal_keeps_the_resource_in_view_while_its_schedule_has_focus():
    app = _app(_tall(claude=30, codex=30, gpus=26))
    async with app.run_test(size=(120, 40)) as pilot:
        chosen = await _gpu_25_schedule(pilot, app)
        await pilot.resize_terminal(120, 28)
        await pilot.pause()
        await pilot.pause()
        _selected_on_screen(app, "gpu 25", chosen)


@synchronous
async def test_a_removed_selection_while_its_schedule_has_focus_writes_to_no_other_target(
    tmp_path, monkeypatch
):
    values = [str(n) for n in range(26)]
    monitor, _, state = _host_with_disk(tmp_path, monkeypatch, gpu_values=values)
    for value in ("24", "25"):
        later = NOW + timedelta(days=1)
        for start in (later, later + timedelta(days=1)):
            window = cooldown(start, start + timedelta(hours=1), now=NOW, note=f"gpu {value}")
            add_cooldown(writable_gpu_schedule_dir(state, value), window, now=NOW)
    before = {value: read_schedule(gpu_schedule_dir(state, value), now=NOW) for value in values}
    app = _app(monitor)
    async with app.run_test(size=(120, 40)) as pilot:
        chosen = await _gpu_25_schedule(pilot, app)
        assert chosen.note == "gpu 25"
        notes = _recorded(app)
        values.remove("25")
        await pilot.press("r")
        await _settle(app, pilot)
        view = app.query_one(CapacityView)
        assert view.selected is None, "an orphaned schedule is another target"
        assert view.selected_cooldown is None
        assert app.query_one("#capacity-schedule").border_subtitle == ""
        for key in ("x", "e", "n", "L"):
            await pilot.press(key)
            await pilot.pause()
            assert not isinstance(app.screen, CooldownForm | ConfirmCooldownRemove | LimitForm)
        assert all("first" in note[0] for note in notes[-4:]), notes
        await pilot.resize_terminal(120, 28)
        await pilot.pause()
        await pilot.pause()
        await pilot.press("r")
        await _settle(app, pilot)
    assert {
        value: read_schedule(gpu_schedule_dir(state, value), now=NOW) for value in (*values, "25")
    } == before


# `L` checks the estimate the monitor shows ----------------------------------------------

RECORD_RESET = datetime(2026, 10, 9, tzinfo=UTC)
"""Where ``claude_usage`` readings reset."""


def _limit_host(tmp_path, monkeypatch) -> Host:
    """A real monitor given its locations by flag, in a process whose environment names
    another Results Repo, holding a low reading, and another host label, and no runs dir."""
    host = Host(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    publish(elsewhere, "r9", usage=claude_usage(10.0), requests=[])
    monkeypatch.setenv("SILVERQUILLM_RESULTS_REPO", str(elsewhere))
    monkeypatch.setenv("SILVERQUILLM_HOST_LABEL", "host-b")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no-config"))
    return host


def _seen(percent, resets, window=WEEKLY) -> UsageReading:
    observed = RECORDS_NOW - timedelta(minutes=30)
    return UsageReading("claude", percent, 10080, resets, observed, window=window)


async def _set_limit(pilot, app, **ceilings) -> list:
    """Open the only Claude profile's ``L`` form and submit ``ceilings``; the notes so far."""
    notes = _recorded(app)
    await pilot.press("4")
    await pilot.pause()
    view = app.query_one(CapacityView)
    assert view.selected.name == "bare-claude-opus"
    await pilot.press("L")
    await pilot.pause()
    _fill(app, **ceilings)
    await pilot.press("enter")
    return notes


@synchronous
@pytest.mark.parametrize("where", ["results_repo", "runs_dir"])
async def test_l_checks_records_where_the_monitors_flags_point(tmp_path, monkeypatch, where):
    host = _limit_host(tmp_path, monkeypatch)
    if where == "results_repo":
        publish(host.repo, "r1", usage=claude_usage(85.0), requests=[])
    else:
        run = make_run(host.runs, "r1")
        retain(run / "run-record.json", "r1", host=None, usage=claude_usage(85.0), requests=[])
    app = build_app(host.monitor, MTG, interval=60, clock=lambda: host.now)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        [shown] = app.snapshot.profiles
        assert shown.weekly.percent == pytest.approx(85.0)
        notes = await _set_limit(pilot, app, weekly="80")
        await _wait_for(pilot, app, lambda: any("limit set" in note for note, _ in notes))
        [held] = read_schedule(host.login, now=host.now)
        assert (held.source, held.scope, held.end) == ("usage-limit", "all", RECORD_RESET)
        assert any("limit reached" in note for note, _ in notes)
        [shown] = app.snapshot.profiles
        assert shown.status.cooldown_until == RECORD_RESET, "the next poll shows the hold"


@synchronous
async def test_l_counts_a_newer_reading_the_monitor_keeps_over_an_older_record(
    tmp_path, monkeypatch
):
    host = _limit_host(tmp_path, monkeypatch)
    publish(host.repo, "r1", usage=claude_usage(10.0), requests=[])
    later = RECORD_RESET + timedelta(hours=5)
    host.monitor._observe(PROFILE, _seen(85.0, later))
    app = build_app(host.monitor, MTG, interval=60, clock=lambda: host.now)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        assert app.snapshot.profiles[0].weekly.percent == pytest.approx(85.0)
        notes = await _set_limit(pilot, app, weekly="80")
        await _wait_for(pilot, app, lambda: any("limit set" in note for note, _ in notes))
    [held] = read_schedule(host.login, now=host.now)
    assert (held.scope, held.end) == ("all", later), "the reading's own reset"


@synchronous
async def test_l_holds_back_only_fable_runs_on_a_fable_reading_alone(tmp_path, monkeypatch):
    host = _limit_host(tmp_path, monkeypatch)
    publish(host.repo, "r1", usage=claude_usage(10.0), requests=[])
    fable_reset = RECORD_RESET + timedelta(hours=3)
    host.monitor._observe(PROFILE, _seen(95.0, fable_reset, FABLE))
    app = build_app(host.monitor, MTG, interval=60, clock=lambda: host.now)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        notes = await _set_limit(pilot, app, weekly="80", **{"fable-limit": "90"})
        await _wait_for(pilot, app, lambda: any("limit set" in note for note, _ in notes))
        assert any("Fable runs held" in note for note, _ in notes)
    [held] = read_schedule(host.login, now=host.now)
    assert (held.scope, held.end) == ("fable", fable_reset)


@synchronous
@pytest.mark.parametrize("seen", [None, 79.0])
async def test_l_below_the_ceiling_or_without_a_reading_writes_nothing(tmp_path, monkeypatch, seen):
    host = _limit_host(tmp_path, monkeypatch)
    if seen is not None:
        host.monitor._observe(PROFILE, _seen(seen, RECORD_RESET))
    app = build_app(host.monitor, MTG, interval=60, clock=lambda: host.now)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        notes = await _set_limit(pilot, app, weekly="80")
        await _wait_for(pilot, app, lambda: any("limit set" in note for note, _ in notes))
        assert not any("limit reached" in note for note, _ in notes)
    assert read_schedule(host.login, now=host.now) == []
    assert read_limit(host.login) == UsageLimit(80.0, None)


@synchronous
async def test_l_on_a_held_schedule_reports_the_saved_limit_unchecked_and_a_retry_checks_it(
    tmp_path, monkeypatch
):
    host = _limit_host(tmp_path, monkeypatch)
    publish(host.repo, "r1", usage=claude_usage(85.0), requests=[])
    kept = cooldown(RECORD_RESET, RECORD_RESET + timedelta(days=1), now=host.now, note="kept")
    add_cooldown(host.login, kept, now=host.now)
    monkeypatch.setattr(cooldowns, "WRITE_WAIT", 0.5)
    stalled = os.open(host.login / ".cooldowns.lock", os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(stalled, fcntl.LOCK_EX)
    app = build_app(host.monitor, MTG, interval=60, clock=lambda: host.now)
    try:
        async with app.run_test(size=(200, 50)) as pilot:
            await _settle(app, pilot)
            started = time.monotonic()
            notes = await _set_limit(pilot, app, weekly="80")
            await _wait_for(pilot, app, lambda: any(level for _, level in notes), timeout=5)
            assert time.monotonic() - started < 3, "the check waits no longer than the bound"
            [(note, level)] = notes
            assert level == "error"
            assert "limit saved, but its check could not complete" in note
            assert "cooldown_schedule_busy" in note
            assert read_limit(host.login) == UsageLimit(80.0, None)
            # Released after the worker gave up: nothing it left behind writes late.
            os.close(stalled)
            stalled = None
            await pilot.pause(1.0)
            assert read_schedule(host.login, now=host.now) == [kept]
            # The view still answers the keyboard.
            await pilot.press("2")
            assert app.query_one("#switcher").current == "history"
            await pilot.press("4")
            await pilot.pause()
            assert app.query_one(CapacityView).selected.name == "bare-claude-opus"
            # Setting it again checks it.
            await pilot.press("L")
            await pilot.pause()
            assert app.screen.query_one("#form-weekly", Input).value == "80"
            await pilot.press("enter")
            await _wait_for(pilot, app, lambda: any("limit set" in note for note, _ in notes))
            schedule = read_schedule(host.login, now=host.now)
            assert kept in schedule
            assert [c.source for c in schedule if c != kept] == ["usage-limit"]
            await pilot.press("q")
            await pilot.pause()
            assert app.return_code == 0
    finally:
        if stalled is not None:
            os.close(stalled)
