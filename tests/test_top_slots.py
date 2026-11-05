"""Slot management from the monitor: blocked profiles, and the LOGINS pane's ``a``, ``R``, ``D``."""

from __future__ import annotations

import contextlib
from dataclasses import replace

import pytest

pytest.importorskip("textual")

from silverquillm.karn.definition import KarnError
from silverquillm.top import slots
from silverquillm.top.dashboard import LoginsPane
from silverquillm.top.theme import MTG

from .test_top import _app, _settle, synchronous
from .test_top_cooldowns import _codex_slot, _host, _plain, _recorded
from .top_fixtures import FakeMonitor


def _suspended(app, monkeypatch, outcome="karn-codex-login/slot-2 enrolled"):
    """Stand in for the terminal hand-over, which a headless test driver cannot do."""
    calls = []
    app.suspend = contextlib.nullcontext
    monkeypatch.setattr(
        slots, "sign_in", lambda root, plugin, slot: calls.append((root, plugin, slot)) or outcome
    )
    return calls


def test_a_blocked_profile_reads_relogin_and_pools_order_by_number():
    snapshot = FakeMonitor().snapshot()
    codex = [view for view in snapshot.profiles if view.status.provider == "codex"]
    renamed = [
        replace(view, status=replace(view.status, slot=name))
        for view, name in zip(codex, ["slot-10", "slot-2", "slot-1"], strict=False)
    ]
    renamed[1] = replace(renamed[1], status=replace(renamed[1].status, blocked="relogin_needed"))
    snapshot = replace(snapshot, profiles=renamed)
    assert [view.status.slot for view in LoginsPane.views(snapshot, "codex")] == [
        "slot-1",
        "slot-2",
        "slot-10",
    ]
    text = _plain(LoginsPane.pool(snapshot, "codex", MTG))
    line = next(line for line in text.splitlines() if "slot-2" in line)
    assert MTG.glyph("blocked") in line and "relogin · R re-enroll" in line


@synchronous
async def test_r_signs_the_selected_profile_in_outside_the_tui(tmp_path, monkeypatch):
    monitor, _ = _host(tmp_path)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        notes = _recorded(app)
        calls = _suspended(app, monkeypatch)
        await _codex_slot(pilot, app, "slot-2")
        await pilot.press("R")
        await _settle(app, pilot)
    state_root = tmp_path / ".local/state/silverquillm"
    assert calls == [(state_root, "karn-codex-login", "slot-2")]
    assert notes == [("karn-codex-login/slot-2 enrolled", "information")]


@synchronous
async def test_a_adds_a_slot_to_the_focused_pool_and_a_failure_is_an_error(tmp_path, monkeypatch):
    monitor, _ = _host(tmp_path)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        notes = _recorded(app)
        calls = _suspended(app, monkeypatch, outcome="a new codex slot: sign-in cancelled")
        await _codex_slot(pilot, app, "slot-1")
        await pilot.press("a")
        await _settle(app, pilot)
    assert [call[1:] for call in calls] == [("karn-codex-login", None)]
    assert notes == [("a new codex slot: sign-in cancelled", "error")]


@synchronous
async def test_a_terminal_that_cannot_hand_over_says_to_use_the_cli(tmp_path):
    monitor, _ = _host(tmp_path)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        notes = _recorded(app)
        await _codex_slot(pilot, app, "slot-1")
        await pilot.press("R")
        await _settle(app, pilot)
    assert len(notes) == 1 and "silverquillm login" in notes[0][0] and notes[0][1] == "error"


@synchronous
async def test_d_removes_the_selected_slot_only_after_y(tmp_path):
    monitor, pool = _host(tmp_path)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        notes = _recorded(app)
        await _codex_slot(pilot, app, "slot-3")
        await pilot.press("D")
        await pilot.pause()
        assert isinstance(app.screen, slots.ConfirmRemove)
        await pilot.press("n")
        await _settle(app, pilot)
        assert "slot-3" in pool.enrolled() and notes == []
        await pilot.press("D")
        await pilot.pause()
        await pilot.press("y")
        await _settle(app, pilot)
    assert "slot-3" not in pool.enrolled()
    assert notes == [("karn-codex-login/slot-3 removed", None)]


@synchronous
async def test_a_slot_that_cannot_be_removed_is_a_notice(tmp_path):
    monitor, pool = _host(tmp_path)
    pool.slot("slot-1").journal({"run_id": "run-x", "plugin_artifact": "sha256:" + "a" * 64})
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        notes = _recorded(app)
        await _codex_slot(pilot, app, "slot-1")
        await pilot.press("D", "y")
        await _settle(app, pilot)
    assert "slot-1" in pool.enrolled()
    assert notes == [("karn-codex-login/slot-1: not removed (login_slot_pending)", "error")]


@pytest.mark.parametrize(
    ("enrolled", "outcome"),
    [
        (lambda *a: ("karn-claude-login/slot-4", 0), "karn-claude-login/slot-4 enrolled"),
        (
            lambda *a: ("karn-claude-login/slot-4", 1),
            "karn-claude-login/slot-4: sign-in failed (exit 1)",
        ),
        (
            lambda *a: (_ for _ in ()).throw(KarnError("login_plugin_not_cached:x")),
            "karn-claude-login/slot-4: not enrolled (login_plugin_not_cached:x)",
        ),
        (
            lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()),
            "karn-claude-login/slot-4: sign-in cancelled",
        ),
    ],
)
def test_signing_in_reports_its_outcome_and_waits_for_enter(
    tmp_path, monkeypatch, capsys, enrolled, outcome
):
    monkeypatch.setattr(slots, "enroll_slot", enrolled)
    prompts = []
    result = slots.sign_in(tmp_path, "karn-claude-login", "slot-4", read=prompts.append)
    assert result == outcome
    assert prompts == ["Press Enter to return to top. "]
    printed = capsys.readouterr().out
    assert "signing in karn-claude-login/slot-4" in printed and outcome in printed


@synchronous
async def test_a_slot_replaced_while_its_removal_is_confirmed_is_kept(tmp_path):
    from .test_karn_login_pool import enroll

    monitor, pool = _host(tmp_path)
    app = _app(monitor)
    async with app.run_test(size=(200, 50)) as pilot:
        await _settle(app, pilot)
        notes = _recorded(app)
        await _codex_slot(pilot, app, "slot-3")
        await pilot.press("D")
        await pilot.pause()
        pool.remove("slot-3")
        enroll(pool.named_slot("slot-3"), pool.plugin_id)
        await pilot.press("y")
        await _settle(app, pilot)
    assert "slot-3" in pool.enrolled()
    assert notes == [("karn-codex-login/slot-3: not removed (login_slot_replaced)", "error")]
