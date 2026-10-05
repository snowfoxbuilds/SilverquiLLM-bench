"""The agent-visible grading support is the one grading uses.

A benchmark with a Test Interface (smoke onward) stages the very
``test_interface.py`` grading pairs with the candidate's engine
(TEST-INTERFACE.md); one without (hob-medium, fra-hard v1) stages a
``test_utils.py`` byte-identical to the grading copy (AUDITED-TEST-SUITE.md), so
an agent's own tests can use every helper, and the same activation semantics,
that the grading suites rely on.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from silverquillm.evaluator import resolve_eval_paths

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARKS = {"hob-medium": "hob", "smoke": "fdn", "fra-hard": "fra"}


@pytest.mark.parametrize("benchmark,target_set", BENCHMARKS.items())
def test_staged_grading_support_is_the_grading_copy(benchmark, target_set):
    root = REPO_ROOT / "benchmarks" / benchmark
    paths = resolve_eval_paths(root, target_set)
    if paths.test_interface is not None:
        staged, grading = root / "workspace" / "test_interface.py", paths.test_interface
    else:
        staged, grading = root / "workspace" / "test_utils.py", paths.test_utils
    assert staged.read_bytes() == grading.read_bytes()


def test_smoke_grades_with_its_test_interface():
    assert resolve_eval_paths(REPO_ROOT / "benchmarks" / "smoke", "fdn").test_interface is not None
    assert resolve_eval_paths(REPO_ROOT / "benchmarks" / "hob-medium", "hob").test_interface is None


@pytest.mark.parametrize("placement", ["activated", "mana"])
def test_activate_card_ability_finds_a_mana_ability_in_either_list(placement):
    probe = textwrap.dedent(
        f"""
        from engine.abilities import tap_cost
        from engine.card import Creature, ManaAbility
        from engine.types import ManaType
        from test_utils import activate_card_ability, create_game, put_on_battlefield

        class Dork(Creature):
            def _ability(self):
                return ManaAbility(
                    cost=tap_cost,
                    mana_produced=lambda g: self.controller.mana_pool.add(ManaType.GREEN, 1),
                )

            def get_activated_abilities(self):
                return [self._ability()] if {placement!r} == "activated" else []

            def get_mana_abilities(self):
                return [] if {placement!r} == "activated" else [self._ability()]

        game = create_game()
        player = game.players[0]
        dork = put_on_battlefield(game, player, Dork(name="Dork", base_power=1, base_toughness=1))
        dork.summoning_sick = False
        activate_card_ability(game, player, dork)
        assert dork.is_tapped and player.mana_pool.total() == 1 and game.stack.is_empty()
        """
    )
    workspace = REPO_ROOT / "benchmarks" / "hob-medium" / "workspace"
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-3000:]
