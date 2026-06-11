"""Tests for SOS 53 — Homesickness."""

from __future__ import annotations

import pytest

from cards.sos.sos_53.card_impl import Homesickness
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestHomesicknessProperties:
    """Static card data should match the SOS 53 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(Homesickness(owner=None), Instant)

    def test_name(self) -> None:
        assert Homesickness(owner=None).name == "Homesickness"

    def test_mana_cost(self) -> None:
        assert Homesickness(owner=None).mana_cost == ManaCost.parse("{4}{U}{U}")


class TestHomesicknessTargeting:
    """Targets: one player and up to two creatures."""

    def test_returns_target_requirements(self) -> None:
        game = create_game()
        reqs = Homesickness(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        # Should have requirements for player target and creature targets
        assert len(reqs) >= 1


class TestHomesicknessResolution:
    """on_resolve draws cards, taps creatures, and adds stun counters."""

    def test_target_player_draws_two_cards(self) -> None:
        """Target player draws two cards."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Give p2 some cards in library to draw
        from engine.card import CardImpl
        lib_cards = [CardImpl(name=f"Card {i}", owner=p2) for i in range(5)]
        set_board_state(game, 1, hand=[])
        for card in lib_cards:
            game.get_library(p2).append(card)

        spell = Homesickness(owner=p1, controller=p1)
        spell.chosen_targets = [p2]  # player target
        spell.creature_targets = []   # no creature targets
        spell.on_resolve(game)

        # p2 should have drawn 2 cards
        assert len(game.get_hand(p2)) == 2

    def test_taps_target_creatures(self) -> None:
        """Up to two target creatures are tapped."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        creature1 = Creature(name="Bear 1", owner=p2, controller=p2, base_power=2, base_toughness=2)
        creature1.is_tapped = False
        creature2 = Creature(name="Bear 2", owner=p2, controller=p2, base_power=2, base_toughness=2)
        creature2.is_tapped = False

        set_board_state(game, 1, battlefield=[creature1, creature2])

        spell = Homesickness(owner=p1, controller=p1)
        spell.chosen_targets = [p1, creature1, creature2]
        spell.on_resolve(game)

        assert creature1.is_tapped is True
        assert creature2.is_tapped is True

    def test_adds_stun_counters_to_tapped_creatures(self) -> None:
        """Each targeted creature gets a stun counter."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        creature1 = Creature(name="Bear 1", owner=p2, controller=p2, base_power=2, base_toughness=2)
        creature1.is_tapped = False
        creature1.stun_counters = 0

        set_board_state(game, 1, battlefield=[creature1])

        spell = Homesickness(owner=p1, controller=p1)
        spell.chosen_targets = [p1, creature1]
        spell.on_resolve(game)

        assert getattr(creature1, "stun_counters", 0) == 1

    def test_works_with_zero_creature_targets(self) -> None:
        """Can be cast targeting only a player (zero creatures)."""
        game = create_game()
        p1 = game.players[0]

        from engine.card import CardImpl
        lib_cards = [CardImpl(name=f"Card {i}", owner=p1) for i in range(5)]
        set_board_state(game, 0, hand=[])
        for card in lib_cards:
            game.get_library(p1).append(card)

        spell = Homesickness(owner=p1, controller=p1)
        spell.chosen_targets = [p1]
        spell.on_resolve(game)

        assert len(game.get_hand(p1)) == 2

    def test_already_tapped_creature_gets_stun_counter(self) -> None:
        """A creature that's already tapped still gets a stun counter."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        creature = Creature(name="Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        creature.is_tapped = True
        creature.stun_counters = 0

        set_board_state(game, 1, battlefield=[creature])

        spell = Homesickness(owner=p1, controller=p1)
        spell.chosen_targets = [p1, creature]
        spell.on_resolve(game)

        assert getattr(creature, "stun_counters", 0) == 1
