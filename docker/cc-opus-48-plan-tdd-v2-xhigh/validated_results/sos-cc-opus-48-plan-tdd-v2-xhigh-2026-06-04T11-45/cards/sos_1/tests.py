"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Sorcery
from engine.types import Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, declare_attackers, set_board_state


class _QuickStudy(Sorcery):
    def __init__(self, **kw: Any) -> None:
        kw.setdefault("name", "Quick Study")
        kw.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        super().__init__(**kw)
        self.resolved = False

    def on_resolve(self, game: Any) -> None:
        self.resolved = True


def _drain_stack(game: Any) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class TestArchaicProperties:
    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_pt(self) -> None:
        c = TheDawningArchaic(owner=None)
        assert c.base_power == 7 and c.base_toughness == 7

    def test_reach_legendary(self) -> None:
        c = TheDawningArchaic(owner=None)
        assert Keyword.REACH in c.keywords
        assert Supertype.LEGENDARY in c.supertypes


class TestArchaicCostReduction:
    def test_reduces_per_instant_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        arch = TheDawningArchaic(owner=p1, controller=p1)
        gy = [_QuickStudy(), _QuickStudy(), _QuickStudy()]
        set_board_state(game, 0, graveyard=gy)
        assert arch.cost_reduction(game) == 3


class TestArchaicAttackTrigger:
    def test_free_cast_from_graveyard_then_exile(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = _QuickStudy()
        set_board_state(game, 0, graveyard=[spell])
        arch = TheDawningArchaic(owner=p1, controller=p1)
        arch.summoning_sick = False
        set_board_state(game, 0, battlefield=[arch])
        # Re-register triggers (set_board_state bypasses ETB).
        arch.register_triggers(game)

        # Script: choose_yes_no(True) then choose(spell) for the trigger effect.
        p1._script.append(True)
        p1._script.append(spell)

        declare_attackers(game, ["The Dawning Archaic"])
        _drain_stack(game)

        assert spell.resolved is True
        assert game.get_exile(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)
