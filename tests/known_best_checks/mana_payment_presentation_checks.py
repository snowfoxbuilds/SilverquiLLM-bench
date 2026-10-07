"""Known-Best's Audited Tests hold however an engine lets a player pay mana:
Known-Best pays from the mana pool alone, but a player may activate mana
abilities while a cost is paid (CR 601.2g, 602.2b), and an engine may ask
whether to (``mana_during_payment.py``).

- Every FDN and engine Audited case passes when the engine asks: the question
  is optional, and a handle in a script names its permanent, not one of that
  permanent's mana abilities, so a script declines it.
- No Audited case calls an action illegal that the player could pay for by
  tapping a source they have: with every source on offer tapped
  (``mana_greedy_tapping.py``), every such action is still rejected.

Run inside ``known_best/workspace`` by
``tests/test_known_best_gameplay_regressions.py``.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from cards.fdn.fdn_272.card_impl import Plains, PlainsAbility1
from cards.fdn.fdn_669.card_impl import BasiliskCollar
from test_interface import ManaType, Phase, PlayDiverged, Side, Zone, ability, card, create_game

from table import Table, moves, taps

REPO = Path(__file__).resolve().parents[2]
WORKSPACE = REPO / "known_best/workspace"
AUDITED = REPO / "known_best/data/tests/audited"
MAIN = (Phase.PRECOMBAT_MAIN, 0)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mana_during_payment = _load(Path(__file__).parent / "mana_during_payment.py", "mana_during_payment")


def _audited(plugin: str, tmp_path: Path, *extra: str) -> subprocess.CompletedProcess:
    # Staged as a workspace stages them, beside the engine rather than inside it.
    staged = tmp_path / "engine_tests"
    shutil.copytree(AUDITED / "engine", staged, ignore=shutil.ignore_patterns("test_card_impl_ast_guard.py"))
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(staged), str(AUDITED / "fdn"), "-q", "-p", "no:cacheprovider",
         "-p", "no:xdist", "-p", plugin, "-c", str(WORKSPACE / "pytest.ini"), "--rootdir", str(WORKSPACE), *extra],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=900, check=False,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(map(str, (Path(__file__).parent, WORKSPACE, REPO))),
             "PYTHONDONTWRITEBYTECODE": "1"},
    )


def test_every_audited_case_holds_when_mana_abilities_are_offered_during_payment(tmp_path):
    result = _audited("mana_during_payment", tmp_path)
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-2000:]


def test_no_audited_case_calls_an_action_illegal_that_tapping_a_source_could_pay(tmp_path):
    report = tmp_path / "report.xml"
    _audited("mana_greedy_tapping", tmp_path, f"--junitxml={report}")
    paid = [
        f"{case.get('classname')}::{case.get('name')}"
        for case in ET.parse(report).getroot().iter("testcase")
        for failure in case.findall("failure")
        if "took effect" in (failure.get("message", "") + (failure.text or ""))
    ]
    assert not paid, paid


@pytest.fixture
def offered(monkeypatch):
    mana_during_payment.offer_mana_abilities(monkeypatch)
    asked = []
    from test_interface import ScriptedPlayer

    original = ScriptedPlayer.answer

    def answer(self, query):
        asked.append(query.prompt)
        return original(self, query)

    monkeypatch.setattr(ScriptedPlayer, "answer", answer)
    yield asked
    mana_during_payment._GAMES.clear()


def _collar(**act):
    collar, plains = card(BasiliskCollar), card(Plains)
    game = create_game(Side(hand=[collar], battlefield=[plains], mana={ManaType.WHITE: 1}), Side(), start=MAIN)
    return Table(game), collar, plains


def test_a_handle_in_a_script_does_not_tap_its_land_while_a_cost_is_paid(offered):
    t, collar, plains = _collar()
    t.act(0, collar, choices=[plains], then=[moves(collar, Zone.STACK)], note="the pool's {W} pays; the Plains stays")
    t.run()
    assert "Activate a mana ability" in offered


def test_naming_the_mana_ability_taps_the_land_while_a_cost_is_paid(offered):
    t, collar, plains = _collar()
    t.act(0, collar, choices=[ability(plains, PlainsAbility1)], then=[taps(plains), moves(collar, Zone.STACK)])
    t.run()


def test_tapping_the_land_unasked_shows_as_a_different_view(offered):
    t, collar, plains = _collar()
    t.act(0, collar, choices=[ability(plains, PlainsAbility1)], then=[moves(collar, Zone.STACK)])
    with pytest.raises(PlayDiverged):
        t.run()
