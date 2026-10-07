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


def _pytest(plugin: str, tmp_path: Path, *paths: Path) -> tuple[subprocess.CompletedProcess, ET.Element]:
    """Run ``paths`` in a child pytest with ``plugin``; return it and its JUnit
    report's root."""
    report = tmp_path / f"{plugin}-report.xml"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *map(str, paths), "-q", "-p", "no:cacheprovider",
         "-p", "no:xdist", "-p", plugin, "-c", str(WORKSPACE / "pytest.ini"), "--rootdir", str(WORKSPACE),
         f"--junitxml={report}"],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=900, check=False,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(map(str, (Path(__file__).parent, WORKSPACE, REPO))),
             "PYTHONDONTWRITEBYTECODE": "1"},
    )
    root = ET.parse(report).getroot() if report.exists() else ET.Element("testsuites")
    return result, root


def _audited(plugin: str, tmp_path: Path) -> tuple[subprocess.CompletedProcess, ET.Element]:
    # Staged as a workspace stages them, beside the engine rather than inside it.
    staged = tmp_path / "engine_tests"
    shutil.copytree(AUDITED / "engine", staged, ignore=shutil.ignore_patterns("test_card_impl_ast_guard.py"))
    return _pytest(plugin, tmp_path, staged, AUDITED / "fdn")


def _assert_completed(result: subprocess.CompletedProcess, root: ET.Element) -> None:
    """Every collected case ran to a pass: the child exited cleanly, ran at
    least one case, and reported no failure or error."""
    cases = list(root.iter("testcase"))
    broken = [
        f"{case.get('classname')}::{case.get('name')}"
        for case in cases
        if case.find("failure") is not None or case.find("error") is not None
    ]
    output = result.stdout[-6000:] + result.stderr[-2000:]
    assert result.returncode == 0, output
    assert cases, f"no case completed\n{output}"
    assert not broken, broken


def test_every_audited_case_holds_when_mana_abilities_are_offered_during_payment(tmp_path):
    _assert_completed(*_audited("mana_during_payment", tmp_path))


def test_no_audited_case_calls_an_action_illegal_that_tapping_a_source_could_pay(tmp_path):
    _assert_completed(*_audited("mana_greedy_tapping", tmp_path))


_PROBE_IMPORTS = """
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_165.card_impl import ThinkTwice
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_669.card_impl import BasiliskCollar
from test_interface import ManaType, Phase, Side, Zone, card, create_game
from table import Table, moves

MAIN = (Phase.PRECOMBAT_MAIN, 0)
"""

_PAYABLE_AFTER_SPENDING = _PROBE_IMPORTS + """

def test_payable_illegal_attempt_after_legal_spending():
    lions, collar, plains = card(SavannahLions), card(BasiliskCollar), card(Plains)
    t = Table(create_game(Side(hand=[lions, collar], battlefield=[plains], mana={ManaType.WHITE: 1}), Side(), start=MAIN))
    t.act(0, lions, then=[moves(lions, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(lions, Zone.BATTLEFIELD)])
    t.act_illegal(0, collar, note="the untapped Plains could pay the {1}")
    t.run()
"""

_UNPAYABLE_THEN_LEGAL = _PROBE_IMPORTS + """

def test_unpayable_rejection_then_legal_play():
    think, lions = card(ThinkTwice), card(SavannahLions)
    t = Table(create_game(Side(hand=[think, lions], mana={ManaType.WHITE: 1}), Side(), start=MAIN))
    t.act_illegal(0, think, note="no source makes {U}")
    t.act(0, lions, then=[moves(lions, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(lions, Zone.BATTLEFIELD)])
    t.run()
"""


def _probe(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "probe" / "test_probe.py"
    path.parent.mkdir(exist_ok=True)
    path.write_text(source)
    return path


def test_the_sweep_reaches_a_payable_illegal_attempt_after_legal_spending(tmp_path):
    """Legal play before the attempt is scripted as usual, so the sweep reaches
    the attempt, taps the Plains, and fails the child for it."""
    probe = _probe(tmp_path, _PAYABLE_AFTER_SPENDING)
    _assert_completed(*_pytest("mana_during_payment", tmp_path, probe))
    result, root = _pytest("mana_greedy_tapping", tmp_path, probe)
    assert "took effect" in result.stdout, result.stdout[-4000:]
    with pytest.raises(AssertionError):
        _assert_completed(result, root)


def test_the_sweep_passes_an_unpayable_rejection_and_the_play_after_it(tmp_path):
    _assert_completed(*_pytest("mana_greedy_tapping", tmp_path, _probe(tmp_path, _UNPAYABLE_THEN_LEGAL)))


@pytest.mark.parametrize("source", [
    "import no_such_module\n\ndef test_never_runs():\n    pass\n",
    "def test_breaks():\n    raise RuntimeError('boom')\n",
    "# no tests\n",
])
def test_a_child_that_does_not_complete_fails_the_sweep(tmp_path, source):
    with pytest.raises(AssertionError):
        _assert_completed(*_pytest("mana_greedy_tapping", tmp_path, _probe(tmp_path, source)))


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
