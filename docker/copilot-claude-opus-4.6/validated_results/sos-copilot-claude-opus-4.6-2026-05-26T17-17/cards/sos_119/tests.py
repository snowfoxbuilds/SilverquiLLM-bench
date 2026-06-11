"""Tests for SOS 119 — Impractical Joke.

{R} Sorcery.
Damage can't be prevented this turn.
Deals 3 damage to up to one target creature or planeswalker.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_119.card_impl import ImpracticalJoke
from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestImpracticalJokeProperties:
    """Static card data should match the SOS 119 spec."""

    def test_is_sorcery(self) -> None:
        card = ImpracticalJoke(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        assert ImpracticalJoke(owner=None).name == "Impractical Joke"

    def test_mana_cost(self) -> None:
        assert ImpracticalJoke(owner=None).mana_cost == ManaCost.parse("{R}")


class TestImpracticalJokeResolution:
    """Damage prevention disabled and 3 damage to target."""

    def test_deals_3_damage_to_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="Tough Guy", owner=p2, controller=p2,
            base_power=2, base_toughness=5
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        spell = ImpracticalJoke(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.damage_taken >= 3

    def test_can_be_cast_with_no_target(self) -> None:
        """'Up to one' means zero targets is legal."""
        game = create_game()
        p1 = game.players[0]

        spell = ImpracticalJoke(owner=p1, controller=p1)
        spell.chosen_targets = []
        # Should not raise even with no targets
        spell.on_resolve(game)

    def test_damage_prevention_disabled_this_turn(self) -> None:
        """After resolution, damage cannot be prevented this turn."""
        game = create_game()
        p1 = game.players[0]

        spell = ImpracticalJoke(owner=p1, controller=p1)
        spell.chosen_targets = []
        spell.on_resolve(game)

        # The game state should reflect that damage prevention is off
        assert game.damage_prevention_disabled is True
