"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant
from engine.casting import get_cost_reduction
from engine.state_based_actions import resolve_state_based_actions
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import cast_spell, create_game, declare_attackers, set_board_state


class _LifeGainInstant(Instant):
    """Test instant: controller gains 5 life. No targets."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bless")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 5


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class TestProperties:
    def test_reach_and_stats(self):
        c = TheDawningArchaic(owner=None)
        assert Keyword.REACH in c.keywords
        assert c.base_power == 7 and c.base_toughness == 7
        assert Supertype.LEGENDARY in c.supertypes
        assert c.mana_cost == ManaCost.parse("{10}")


class TestCostReduction:
    def test_reduction_counts_instants_sorceries(self):
        game = create_game()
        p0 = game.players[0]
        archaic = TheDawningArchaic(owner=p0, controller=p0)
        gy = [_LifeGainInstant(owner=p0), _LifeGainInstant(owner=p0),
              Creature(name="Bear", base_power=2, base_toughness=2, owner=p0)]
        set_board_state(game, 0, graveyard=gy)
        # 2 instants in graveyard → {2} reduction (clamped to generic 10).
        assert get_cost_reduction(game, archaic, p0) == 2

    def test_castable_with_reduced_mana(self):
        game = create_game()
        p0 = game.players[0]
        set_board_state(game, 0, graveyard=[_LifeGainInstant(owner=p0),
                                            _LifeGainInstant(owner=p0),
                                            _LifeGainInstant(owner=p0)])
        set_board_state(game, 0, hand=[TheDawningArchaic(owner=None)],
                        mana={ManaType.COLORLESS: 7})
        # cost {10} - 3 = {7}; exactly 7 mana available.
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.get_battlefield(p0).contains(
            next(c for c in game.get_battlefield(p0).get_all()
                 if c.name == "The Dawning Archaic"))


class TestAttackTrigger:
    def test_cast_from_graveyard_then_exiled(self):
        spell = _LifeGainInstant(owner=None)
        game = create_game(scripts=([True, spell], []))
        p0 = game.players[0]
        archaic = TheDawningArchaic(owner=p0, controller=p0)
        archaic.summoning_sick = False
        archaic.is_tapped = False
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell], life=20)
        archaic.register_triggers(game)

        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_stack(game)

        # The instant resolved (life gained) and was exiled, not binned.
        assert p0.life == 25
        assert game.get_exile(p0).contains(spell)
        assert not game.get_graveyard(p0).contains(spell)

    def test_may_decline(self):
        spell = _LifeGainInstant(owner=None)
        game = create_game(scripts=([False], []))
        p0 = game.players[0]
        archaic = TheDawningArchaic(owner=p0, controller=p0)
        archaic.summoning_sick = False
        archaic.is_tapped = False
        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell], life=20)
        archaic.register_triggers(game)

        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_stack(game)

        # Declined: spell stays in graveyard, no life gained.
        assert p0.life == 20
        assert game.get_graveyard(p0).contains(spell)

    def test_no_legal_target_empty_graveyard(self):
        game = create_game(scripts=([], []))
        p0 = game.players[0]
        archaic = TheDawningArchaic(owner=p0, controller=p0)
        archaic.summoning_sick = False
        archaic.is_tapped = False
        set_board_state(game, 0, battlefield=[archaic], graveyard=[], life=20)
        archaic.register_triggers(game)

        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_stack(game)  # must not raise / not consume choices
        assert p0.life == 20
