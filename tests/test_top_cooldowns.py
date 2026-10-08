"""Login Cooldowns from the monitor: the LOGINS pane's selection and its ``t`` and ``c`` keys."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import timedelta

import pytest

pytest.importorskip("textual")

from rich.text import Text

from silverquillm.karn.login_cooldown import (
    COOLDOWN_FILE,
    cooldown_until,
    set_cooldown,
)
from silverquillm.karn.login_pool import LoginPool
from silverquillm.monitor.candidates import CandidateDisplay
from silverquillm.top.dashboard import LoginsPane, PoolPanel, RunningPane
from silverquillm.top.details import Shown, header
from silverquillm.top.theme import MTG

from .test_karn_login_pool import enroll
from .test_top import _app, _settle, synchronous
from .top_fixtures import NOW, FakeMonitor, profiles, running_views

CODEX = ("bare-codex-luna", "slot-1", "slot-2", "slot-3", "slot-4", "slot-5")


def _plain(renderable) -> str:
    from rich.console import Console

    console = Console(width=200, record=True, color_system=None)
    console.print(renderable)
    return console.export_text()


def _host(tmp_path) -> tuple[FakeMonitor, LoginPool]:
    """A monitor whose state root holds the fixtures' Codex profiles, really enrolled."""
    monitor = FakeMonitor(root=tmp_path)
    pool = LoginPool.of(tmp_path / ".local/state/silverquillm", "karn-codex-login")
    for name in CODEX:
        enroll(pool.named_slot(name), pool.plugin_id)
    return monitor, pool


def _recorded(app) -> list[tuple[str, str | None]]:
    notes: list[tuple[str, str | None]] = []
    app.notify = lambda message, **options: notes.append((message, options.get("severity")))
    return notes


async def _codex_slot(pilot, app, slot: str) -> PoolPanel:
    """Reach the Codex pool from the running table by keyboard and select ``slot``."""
    await pilot.press("shift+tab")
    panel = app.query_one("#pool-codex", PoolPanel)
    assert app.focused is panel
    for _ in range(CODEX.index(slot)):
        await pilot.press("down")
    assert panel.selected == ("karn-codex-login", slot)
    return panel


@synchronous
async def test_t_holds_the_selected_profile_an_hour_and_each_press_adds_one(tmp_path):
    monitor, pool = _host(tmp_path)
    polls = []
    snapshot = monitor.snapshot
    monitor.snapshot = lambda: polls.append(1) or snapshot()
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        notes = _recorded(app)
        await _codex_slot(pilot, app, "slot-1")
        before = len(polls)
        await pilot.press("t")
        await _settle(app, pilot)
        assert cooldown_until(pool.root / "slot-1", now=NOW) == NOW + timedelta(hours=1)
        assert len(polls) > before, "a written cooldown refreshes at once"
        await pilot.press("t")
        await _settle(app, pilot)
        assert cooldown_until(pool.root / "slot-1", now=NOW) == NOW + timedelta(hours=2)
        assert [severity for _, severity in notes] == [None, None]
        assert "slot-1 cooldown until" in notes[-1][0] and notes[-1][0].endswith("(+1h)")
        assert not (pool.root / "slot-2" / COOLDOWN_FILE).exists()


@synchronous
async def test_c_ends_a_cooldown_ten_seconds_on_and_ignores_a_profile_without_one(tmp_path):
    monitor, pool = _host(tmp_path)
    set_cooldown(pool.root / "slot-3", NOW + timedelta(hours=4), now=NOW)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        notes = _recorded(app)
        await _codex_slot(pilot, app, "slot-3")
        await pilot.press("c")
        await _settle(app, pilot)
        assert cooldown_until(pool.root / "slot-3", now=NOW) == NOW + timedelta(seconds=10)
        assert "(in 10s)" in notes[-1][0]
        await pilot.press("down", "c")
        await _settle(app, pilot)
        assert not (pool.root / "slot-4" / COOLDOWN_FILE).exists()
        assert notes[-1] == ("slot-4 has no cooldown to end", None)


@synchronous
async def test_the_monitor_writes_the_same_file_the_cli_does(tmp_path):
    monitor, pool = _host(tmp_path)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        await _codex_slot(pilot, app, "slot-4")
        await pilot.press("t")
        await _settle(app, pilot)
    written = (pool.root / "slot-4" / COOLDOWN_FILE).read_bytes()
    set_cooldown(pool.root / "slot-5", NOW + timedelta(hours=1), now=NOW)
    assert written == (pool.root / "slot-5" / COOLDOWN_FILE).read_bytes()
    assert set(json.loads(written)) == {"format", "set_at", "until"}


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes through directory permissions")
@synchronous
async def test_a_cooldown_that_cannot_be_written_is_a_notice_not_a_crash(tmp_path):
    monitor, pool = _host(tmp_path)
    (pool.root / "slot-1").chmod(0o500)
    app = _app(monitor)
    try:
        async with app.run_test(size=(200, 50)) as pilot:
            await _settle(app, pilot)
            notes = _recorded(app)
            await _codex_slot(pilot, app, "slot-1")
            await pilot.press("t")
            await _settle(app, pilot)
            assert notes and notes[-1][1] == "error"
            assert "slot-1: cooldown not written" in notes[-1][0]
            await pilot.press("2")
            assert app.query_one("#switcher").current == "history"
    finally:
        (pool.root / "slot-1").chmod(0o700)
    assert not (pool.root / "slot-1" / COOLDOWN_FILE).exists()


@synchronous
async def test_a_profile_no_longer_enrolled_is_never_written(tmp_path):
    monitor = FakeMonitor(root=tmp_path)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        notes = _recorded(app)
        await _codex_slot(pilot, app, "slot-1")
        await pilot.press("t")
        await _settle(app, pilot)
    assert notes[-1][1] == "error"
    assert not (tmp_path / ".local").exists()


@synchronous
async def test_a_click_selects_a_profile_and_focuses_its_pool(tmp_path):
    app = _app(FakeMonitor(root=tmp_path))
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        # The header is the pool's first line; slot-2 is its third profile.
        await pilot.click("#pool-codex", offset=(3, 3))
        panel = app.query_one("#pool-codex", PoolPanel)
        assert app.focused is panel
        assert panel.selected == ("karn-codex-login", "slot-2")
        assert "t cooldown" in str(app.query_one("#keys").render())


@synchronous
async def test_a_long_pool_scrolls_to_keep_the_selection_in_view(tmp_path):
    monitor = FakeMonitor(root=tmp_path)
    many = [
        replace(view, status=replace(view.status, slot=f"slot-{index:02d}"))
        for index, view in enumerate(
            [view for view in profiles() if view.status.provider == "codex"] * 4
        )
    ]
    claude = [view for view in profiles() if view.status.provider == "claude"]
    snapshot = monitor.snapshot
    monitor.snapshot = lambda: replace(snapshot(), profiles=claude + many)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        logins = app.query_one(LoginsPane)
        await pilot.press("shift+tab")
        for _ in range(len(many) - 1):
            await pilot.press("down")
        await pilot.pause()
        panel = app.query_one("#pool-codex", PoolPanel)
        assert panel.selected == ("karn-codex-login", f"slot-{len(many) - 1:02d}")
        assert logins.scroll_y > 0
        line = panel.region.y + len(many)  # the last profile, under the header
        assert logins.content_region.y <= line < logins.content_region.bottom


def test_lists_show_the_recipe_revision_cut_like_hash8_and_details_show_it_whole():
    commit = "c68bbe729f93c95f22b3cd6acd5ff30263adf773"
    candidate = CandidateDisplay(
        "bare-codex-sol61-xhigh", "gpt-6.1-sol", "xhigh", "d4d4d4d4", commit
    )
    assert candidate.secondary == ("d4d4d4d4", commit[:8])
    view = running_views()[1]
    view = replace(view, run=replace(view.run, candidate=candidate))
    cells = RunningPane._cells(view, NOW, MTG)
    text = cells[2].plain if isinstance(cells[2], Text) else str(cells[2])
    assert "bare-codex-sol61-xhigh · gpt-6.1-sol · xhigh" in text
    assert commit[:8] in text and commit not in text
    assert commit in _plain(header(Shown(view.run.run_id, live=view), NOW, MTG))
