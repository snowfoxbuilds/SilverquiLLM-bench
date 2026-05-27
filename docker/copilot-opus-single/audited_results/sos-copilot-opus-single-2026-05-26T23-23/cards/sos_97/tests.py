"""Tests for SOS 97 — Ral Zarek, Guest Lecturer.

Legendary Planeswalker — Ral
{1}{B}{B}, Loyalty 3.

+1: Surveil 2.
−1: Any number of target players each discard a card.
−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.
−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Planeswalker, LoyaltyAbility
from engine.types import CardType, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


class TestRalZarekProperties:
    """Static card data should match the SOS 97 spec."""

    def test_is_planeswalker(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert isinstance(card, Planeswalker)

    def test_name(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_starting_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.starting_loyalty == 3

    def test_loyalty_starts_at_starting_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.loyalty == 3

    def test_is_legendary(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_ral_subtype(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert "Ral" in card.subtypes

    def test_card_type_planeswalker(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert CardType.PLANESWALKER in card.card_types


class TestRalZarekLoyaltyAbilities:
    """Ral Zarek should expose four loyalty abilities with correct costs."""

    def test_has_four_loyalty_abilities(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert len(abilities) == 4

    def test_plus_one_ability_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert abilities[0].loyalty_cost == 1

    def test_minus_one_ability_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert abilities[1].loyalty_cost == -1

    def test_minus_two_ability_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert abilities[2].loyalty_cost == -2

    def test_minus_seven_ability_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert abilities[3].loyalty_cost == -7


class TestRalZarekSurveil:
    """+1: Surveil 2 — look at top 2, put any number into graveyard."""

    def test_surveil_moves_cards_from_library_top(self) -> None:
        """After +1, up to 2 cards should move from library to graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 3

        # Put known cards on top of library
        dummy1 = Creature(name="Dummy A", base_power=1, base_toughness=1, owner=p1)
        dummy2 = Creature(name="Dummy B", base_power=1, base_toughness=1, owner=p1)
        game.get_library(p1).add(dummy1, position="top")
        game.get_library(p1).add(dummy2, position="top")

        abilities = card.get_loyalty_abilities()
        # Activate +1 (surveil 2 — put both to graveyard)
        abilities[0].effect(game, card, choices={"put_to_graveyard": [dummy2, dummy1]})

        # Loyalty should increase
        assert card.loyalty == 4

        # At least one card should have moved to graveyard
        gy_cards = game.get_graveyard(p1).get_all()
        assert len(gy_cards) >= 1


class TestRalZarekDiscard:
    """−1: Any number of target players each discard a card."""

    def test_target_player_discards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 3

        # Give opponent a card in hand
        dummy = Creature(name="Victim", base_power=2, base_toughness=2, owner=p2)
        game.get_hand(p2).add(dummy)

        abilities = card.get_loyalty_abilities()
        abilities[1].effect(game, card, targets=[p2])

        # Loyalty should decrease
        assert card.loyalty == 2

        # Opponent's hand should be reduced
        assert len(game.get_hand(p2).get_all()) == 0

    def test_multiple_players_discard(self) -> None:
        """Both players can be targeted to each discard."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 3

        d1 = Creature(name="Card A", base_power=1, base_toughness=1, owner=p1)
        d2 = Creature(name="Card B", base_power=1, base_toughness=1, owner=p2)
        game.get_hand(p1).add(d1)
        game.get_hand(p2).add(d2)

        abilities = card.get_loyalty_abilities()
        abilities[1].effect(game, card, targets=[p1, p2])

        assert len(game.get_hand(p1).get_all()) == 0
        assert len(game.get_hand(p2).get_all()) == 0


class TestRalZarekReanimate:
    """−2: Return target creature card with mana value 3 or less from graveyard to battlefield."""

    def test_returns_creature_to_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 3

        # Put a creature with mana value <= 3 in graveyard
        target = Creature(
            name="Small Zombie", base_power=2, base_toughness=2,
            owner=p1, mana_cost=ManaCost.parse("{1}{B}")
        )
        game.get_graveyard(p1).add(target)

        abilities = card.get_loyalty_abilities()
        abilities[2].effect(game, card, targets=[target])

        # Loyalty should decrease by 2
        assert card.loyalty == 1

        # Creature should be on battlefield
        bf = game.get_battlefield(p1).get_all()
        assert target in bf

        # Creature should no longer be in graveyard
        assert target not in game.get_graveyard(p1).get_all()

    def test_rejects_creature_with_mana_value_above_3(self) -> None:
        """Cannot target a creature with mana value > 3."""
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 3

        expensive = Creature(
            name="Big Demon", base_power=6, base_toughness=6,
            owner=p1, mana_cost=ManaCost.parse("{4}{B}{B}")
        )
        game.get_graveyard(p1).add(expensive)

        abilities = card.get_loyalty_abilities()
        # The targeting should be invalid — either raises or returns False
        # Implementation should validate mana value restriction
        valid_targets = card.get_valid_targets_for_ability(game, 2)
        assert expensive not in valid_targets


class TestRalZarekUltimate:
    """−7: Flip five coins. Target opponent skips X turns (heads count)."""

    def test_ultimate_requires_7_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert abilities[3].loyalty_cost == -7

    def test_ultimate_skips_turns_based_on_coin_flips(self) -> None:
        """With all heads, opponent skips 5 turns."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 7

        abilities = card.get_loyalty_abilities()
        # Force all heads (5 heads = skip 5 turns)
        abilities[3].effect(game, card, targets=[p2], coin_results=[True, True, True, True, True])

        assert card.loyalty == 0
        # Opponent should have turns to skip
        assert getattr(p2, "turns_to_skip", 0) == 5

    def test_ultimate_zero_heads_skips_no_turns(self) -> None:
        """With all tails, opponent skips 0 turns."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        card.loyalty = 7

        abilities = card.get_loyalty_abilities()
        abilities[3].effect(game, card, targets=[p2], coin_results=[False, False, False, False, False])

        assert getattr(p2, "turns_to_skip", 0) == 0
