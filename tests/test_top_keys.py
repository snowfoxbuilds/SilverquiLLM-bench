"""The monitor's stacked dashboard, history-based progress, cooldowns, and keyboard-only use."""

from __future__ import annotations

import asyncio
import functools
import sys
import time

import pytest
from rich.console import Console

from silverquillm.top import format as fmt
from silverquillm.top.theme import MTG, PLAIN

from .top_fixtures import COOLING, NOW, FakeMonitor, running_views

pytest.importorskip("textual")

from textual.widgets import DataTable, TabbedContent, Tree

from silverquillm.top import _driver
from silverquillm.top.app import build_app
from silverquillm.top.dashboard import LoginsPane, RunningPane
from silverquillm.top.details import TAB_FOCUS, DetailsView
from silverquillm.top.historic import HistoryView
from silverquillm.top.keys import KEYS, HelpScreen, help_table


def synchronous(test):
    @functools.wraps(test)
    def run(*args, **kwargs):
        asyncio.run(test(*args, **kwargs))

    return run


def _app(monitor=None, theme=MTG):
    return build_app(monitor or FakeMonitor(), theme, interval=60, clock=lambda: NOW)


async def _settle(app, pilot, timeout=5.0):
    deadline = time.monotonic() + timeout
    await pilot.pause()
    while any(app.busy.values()):
        assert time.monotonic() < deadline, "the app's jobs never finished"
        await pilot.pause(0.01)
    await pilot.pause()


def _plain(renderable, width=200) -> str:
    console = Console(width=width, record=True, color_system=None)
    console.print(renderable)
    return console.export_text()


# Progress ----------------------------------------------------------------------


def test_progress_follows_past_durations_and_the_budget_is_only_context():
    with_history = next(view for view in running_views() if view.estimated_percent == 61.0)
    cells = RunningPane._cells(with_history, NOW, MTG)
    progress = cells[3].plain
    assert "≈61%" in progress and MTG.glyph("bar_full") in progress
    assert "47m elapsed · 4h budget" in progress
    # 47 minutes of a 4 hour budget is about 20%; the bar must not show that.
    filled = progress.split("\n")[0].count(MTG.glyph("bar_full"))
    assert filled == round(0.61 * 12)


def test_a_run_without_history_shows_no_bar():
    recording = next(view for view in running_views() if view.run.run_id.startswith("dddd"))
    assert recording.estimated_percent is None
    progress = RunningPane._cells(recording, NOW, MTG)[3].plain
    first, second = progress.split("\n")
    assert first.strip() == ""
    assert MTG.glyph("bar_full") not in progress and MTG.glyph("bar_empty") not in progress
    assert second == "31m elapsed · 4h budget"


def test_the_progress_bar_does_not_warm_like_a_limit():
    near = fmt.progress(95.0, 10, MTG)
    assert MTG.style("bar_hot") not in {span.style for span in near.spans}


# Cooldowns ---------------------------------------------------------------------


def test_a_cooled_down_profile_shows_its_hold_and_is_not_untapped():
    snapshot = FakeMonitor().snapshot()
    text = _plain(LoginsPane.pool(snapshot, "codex", MTG))
    line = next(row for row in text.splitlines() if "slot-2" in row)
    assert MTG.glyph("cooldown") in line
    assert "cooldown until" in line and "(3h12m00s)" not in line
    assert "(3h12m)" in line
    codex = next(row for row in text.splitlines() if "CODEX pool" in row)
    # slot-1, slot-3 and slot-5 are busy and slot-2 cools down; luna and slot-4 are free.
    assert "2/6 untapped" in codex
    plain = _plain(LoginsPane.pool(snapshot, "codex", PLAIN))
    assert any("z slot-2" in row for row in plain.splitlines())


def test_a_cooldown_reads_its_end_and_what_is_left():
    ends = COOLING["slot-2"]
    text = fmt.cooldown(ends, NOW, MTG).plain
    assert text.startswith(MTG.glyph("cooldown") + " cooldown until ")
    assert text.endswith("(3h12m)")


# Layout ------------------------------------------------------------------------


@pytest.mark.parametrize("width", [200, 160, 120])
@synchronous
async def test_status_and_logins_share_the_top_above_the_full_width_panes(width):
    app = _app()
    async with app.run_test(size=(width, 50)) as pilot:
        await _settle(app, pilot)
        status, logins = (app.query_one(name).region for name in ("#status", "#logins"))
        assert status.x == 0 and status.y == logins.y and status.right <= logins.x
        assert logins.right == width and logins.width > status.width
        below = [app.query_one(name).region for name in ("#running", "#queued")]
        assert all(region.x == 0 and region.width == width for region in below)
        assert max(status.bottom, logins.bottom) <= below[0].y
        assert below[0].bottom <= below[1].y


@synchronous
async def test_the_two_pools_sit_side_by_side_and_stack_when_too_narrow():
    app = _app()
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        claude, codex = (app.query_one(f"#pool-{name}").region for name in ("claude", "codex"))
        assert claude.y == codex.y and claude.right <= codex.x
        # Six profiles a pool, under one header: the top row stays about as tall as status.
        assert claude.height == 7
        assert not app.query_one("#pool-row").has_class("stacked")
        await pilot.resize_terminal(110, 50)
        await _settle(app, pilot)
        assert app.query_one("#pool-row").has_class("stacked")
        claude, codex = (app.query_one(f"#pool-{name}").region for name in ("claude", "codex"))
        assert claude.x == codex.x and claude.bottom <= codex.y


# Keyboard ----------------------------------------------------------------------


@synchronous
async def test_question_mark_lists_every_key_and_closes_again():
    app = _app()
    async with app.run_test(size=(140, 50)) as pilot:
        await _settle(app, pilot)
        await pilot.press("question_mark")
        assert isinstance(app.screen, HelpScreen)
        listed = _plain(help_table(MTG))
        assert app.screen.query_one("#help").region.width > 0
        for _section, rows in KEYS:
            for keys, _action in rows:
                assert keys in listed
        await pilot.press("escape")
        assert not isinstance(app.screen, HelpScreen)
        await pilot.press("question_mark", "question_mark")
        assert not isinstance(app.screen, HelpScreen)
        footer = str(app.query_one("#keys").render())
        assert "? keys" in footer


@synchronous
async def test_every_view_is_usable_from_the_keyboard_alone():
    monitor = FakeMonitor()
    app = _app(monitor)
    async with app.run_test(size=(160, 50)) as pilot:
        await _settle(app, pilot)
        switcher = app.query_one("#switcher")

        # Dashboard: the running table has the keys; enter opens the selected run.
        assert app.focused is app.query_one("#running-table")
        await pilot.press("down", "enter")
        await _settle(app, pilot)
        details = app.query_one(DetailsView)
        assert switcher.current == "details"
        assert details.shown.run_id == app.query_one(RunningPane)._order[1]

        # Run details: brackets walk the tabs and hand the keys to each tab's content.
        tabs = app.query_one("#detail-tabs", TabbedContent)
        seen = [tabs.active]
        for _ in TAB_FOCUS:
            await pilot.press("right_square_bracket")
            seen.append(tabs.active)
            assert app.focused is app.query_one(TAB_FOCUS[tabs.active])
        assert set(seen) == set(TAB_FOCUS)
        await pilot.press("left_square_bracket")
        assert tabs.active == "tab-raw"
        await pilot.press("pagedown", "end", "home")
        await pilot.press("escape")
        assert switcher.current == "dashboard"

        # History: browse tree and list, sorting both ways, hiding exclusions, opening.
        await pilot.press("2")
        history = app.query_one(HistoryView)
        assert switcher.current == "history"
        await pilot.press("b")
        tree = app.query_one(Tree)
        assert app.focused is tree
        benchmark = next(
            node for node in _nodes(tree.root) if node.data and node.data[0] == "benchmark"
        )
        tree.move_cursor(benchmark)
        await pilot.press("enter")
        assert history.selection == benchmark.data
        name = next(
            node
            for node in _nodes(tree.root)
            if node.data
            and node.data[0] == "group"
            and node.data[1] not in ("benchmarks", "candidates")
        )
        tree.move_cursor(name)
        await pilot.press("space")
        assert name.is_expanded
        await pilot.press("down", "enter")
        assert history.selection == name.children[0].data
        assert history.selection[0] == "candidate" and name.children[0].is_expanded
        await pilot.press("l")
        table = app.query_one("#runs-table", DataTable)
        assert app.focused is table
        start = history.sort_key
        await pilot.press("greater_than_sign")
        assert history.sort_key != start
        await pilot.press("less_than_sign")
        assert history.sort_key == start
        reverse = history.sort_reverse
        await pilot.press("S")
        assert history.sort_reverse is not reverse
        await pilot.press("x")
        assert history.hide_excluded
        await pilot.press("enter")
        await _settle(app, pilot)
        assert switcher.current == "details" and details.shown.pinned

        # Back, refresh, and the view keys.
        await pilot.press("escape")
        assert switcher.current == "history"
        await pilot.press("r")
        await _settle(app, pilot)
        await pilot.press("3")
        assert switcher.current == "details"
        await pilot.press("1")
        assert switcher.current == "dashboard"
        await pilot.press("q")
    assert monitor.closed


def _nodes(node):
    yield node
    for child in node.children:
        yield from _nodes(child)


# Mouse -------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="the cell-mouse driver is POSIX only")
def test_the_driver_keeps_mouse_reports_in_character_cells():
    from textual.drivers.linux_driver import LinuxDriver

    driver = _driver()
    assert issubclass(driver, LinuxDriver)
    written: list[str] = []
    stand_in = driver.__new__(driver)
    stand_in.write = written.append
    stand_in._mouse = True
    stand_in._query_in_band_window_resize()
    stand_in._enable_mouse_pixels()
    assert written == [], "no in-band resize query, so no switch to pixel coordinates"
