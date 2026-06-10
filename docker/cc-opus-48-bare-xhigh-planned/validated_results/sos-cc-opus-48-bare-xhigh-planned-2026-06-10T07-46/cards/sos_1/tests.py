"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from engine.zones import move_to_zone
from test_utils import create_game, set_board_state, cast_spell


def _resolve_stack(game) -> None:
    """Resolve the whole stack the way test_utils.cast_spell does."""
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class _LifeGainInstant(Instant):
    """A no-target probe instant: on resolve, its controller gains 5 life."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Probe Gain")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game) -> None:
        if self.controller is not None:
            self.controller.life += 5


class TestProperties:
    def test_static_data(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")
        assert card.base_power == 7 and card.base_toughness == 7
        assert Keyword.REACH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes


class TestCostReduction:
    def test_reduced_by_graveyard_instants(self) -> None:
        """3 instant/sorcery in graveyard → {10} becomes {7}."""
        game = create_game()
        p0 = game.players[0]
        gy = [Instant(name=f"I{i}", mana_cost=ManaCost.parse("{1}")) for i in range(3)]
        card = TheDawningArchaic(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[card], graveyard=gy,
                        mana={ManaType.COLORLESS: 7})
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.get_battlefield(p0).contains(card)

    def test_not_enough_mana_without_graveyard(self) -> None:
        """Empty graveyard → no reduction; 7 mana can't pay {10}."""
        from test_utils import TestSetupError

        game = create_game()
        p0 = game.players[0]
        card = TheDawningArchaic(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[card], graveyard=[],
                        mana={ManaType.COLORLESS: 7})
        try:
            cast_spell(game, 0, "The Dawning Archaic")
            assert False, "should not have been castable"
        except TestSetupError:
            pass
        assert game.get_hand(p0).contains(card)

    def test_reduction_clamped_at_generic(self) -> None:
        """Many graveyard spells can't reduce below 0 generic; {10} → free-ish.

        With 12 instant/sorcery in the graveyard the reduction (12) is clamped
        to the generic cost (10), so 0 mana is required.
        """
        game = create_game()
        p0 = game.players[0]
        gy = [Instant(name=f"I{i}", mana_cost=ManaCost.parse("{1}")) for i in range(12)]
        card = TheDawningArchaic(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[card], graveyard=gy, mana={})
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.get_battlefield(p0).contains(card)


class TestAttackTrigger:
    def _setup_on_battlefield(self, game) -> TheDawningArchaic:
        p0 = game.players[0]
        card = TheDawningArchaic(owner=p0, controller=p0)
        # Enter via the real ETB path so register_triggers runs.
        set_board_state(game, 0, hand=[card])
        move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)
        card.summoning_sick = False
        return card

    def test_attack_casts_graveyard_spell_for_free_then_exiles(self) -> None:
        from test_utils import declare_attackers

        game = create_game()
        p0 = game.players[0]
        archaic = self._setup_on_battlefield(game)
        probe = _LifeGainInstant(owner=p0, controller=p0)
        set_board_state(game, 0, graveyard=[probe])

        before = p0.life
        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_stack(game)

        # The free spell resolved (controller gained 5 life)...
        assert p0.life == before + 5
        # ...and was exiled instead of going to the graveyard.
        assert game.get_exile(p0).contains(probe)
        assert not game.get_graveyard(p0).contains(probe)

    def test_no_instant_in_graveyard_is_noop(self) -> None:
        from test_utils import declare_attackers

        game = create_game()
        p0 = game.players[0]
        archaic = self._setup_on_battlefield(game)
        # Only a creature card in the graveyard — not a legal target.
        creature_card = Creature(name="Dead Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[creature_card])

        before = p0.life
        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_stack(game)
        assert p0.life == before
        assert game.get_graveyard(p0).contains(creature_card)
