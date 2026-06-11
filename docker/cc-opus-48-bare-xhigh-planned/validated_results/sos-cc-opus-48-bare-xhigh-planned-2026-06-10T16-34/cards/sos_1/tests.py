"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.types import Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state, declare_attackers


class GainFiveSorcery(Sorcery):
    """Test spell: on resolve, controller gains 5 life. No targets."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Gain Five")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game) -> None:
        if self.controller is not None:
            self.controller.life += 5


def _resolve_all(game) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class TestProperties:
    def test_name_cost_pt(self):
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")
        assert card.base_power == 7 and card.base_toughness == 7

    def test_reach_and_legendary(self):
        card = TheDawningArchaic(owner=None)
        assert Keyword.REACH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes


class TestCostReduction:
    def test_empty_graveyard_no_reduction(self):
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_counts_instants_and_sorceries_only(self):
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        gy = [
            Instant(name="I1", mana_cost=ManaCost.parse("{R}")),
            Sorcery(name="S1", mana_cost=ManaCost.parse("{G}")),
            Creature(name="Bear", base_power=2, base_toughness=2),
        ]
        set_board_state(game, 0, graveyard=gy)
        assert card.cost_reduction(game) == 2

    def test_reduction_clamped_to_generic(self):
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        gy = [Instant(name=f"I{i}", mana_cost=ManaCost.parse("{R}")) for i in range(12)]
        set_board_state(game, 0, graveyard=gy)
        # raw 12, generic 10 → clamp to 10
        assert get_cost_reduction(game, card, p1) == 10


class TestAttackTrigger:
    def _setup(self, graveyard):
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[archaic], graveyard=graveyard)
        archaic.summoning_sick = False
        archaic.is_tapped = False
        archaic.register_triggers(game)
        return game, p1, archaic

    def test_single_target_auto_cast_and_exiled(self):
        spell = GainFiveSorcery(owner=None)
        game, p1, archaic = self._setup([spell])
        life_before = p1.life
        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_all(game)
        # Spell was cast for free → +5 life; and exiled instead of graveyard.
        assert p1.life == life_before + 5
        assert game.get_exile(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)

    def test_no_legal_target_does_nothing(self):
        bear = Creature(name="DeadBear", base_power=2, base_toughness=2)
        game, p1, archaic = self._setup([bear])
        life_before = p1.life
        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_all(game)
        assert p1.life == life_before
        assert game.get_graveyard(p1).contains(bear)

    def test_multiple_candidates_decline(self):
        s1 = GainFiveSorcery(owner=None)
        s2 = GainFiveSorcery(owner=None)
        game, p1, archaic = self._setup([s1, s2])
        life_before = p1.life
        declare_attackers(game, ["The Dawning Archaic"])
        # Decline by scripting None for the choose_card call.
        p1._script.append(None)
        _resolve_all(game)
        assert p1.life == life_before
        assert game.get_graveyard(p1).contains(s1)
        assert game.get_graveyard(p1).contains(s2)

    def test_multiple_candidates_choose_one(self):
        s1 = GainFiveSorcery(owner=None, name="Gain Five A")
        s2 = GainFiveSorcery(owner=None, name="Gain Five B")
        game, p1, archaic = self._setup([s1, s2])
        life_before = p1.life
        declare_attackers(game, ["The Dawning Archaic"])
        p1._script.append(s2)  # choose s2
        _resolve_all(game)
        assert p1.life == life_before + 5
        assert game.get_exile(p1).contains(s2)
        assert game.get_graveyard(p1).contains(s1)
