"""Tests for SOS 52 — Harmonized Trio // Brainstorm.

Harmonized Trio is a 1/1 Blue Merfolk Bard Wizard for {U} with an activated
ability: {T}, Tap two untapped creatures you control: This creature becomes
prepared. While prepared, you may cast a copy of Brainstorm (the spell side).
Doing so unprepares it.

Brainstorm: Draw three cards, then put two cards from your hand on top of
your library.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_52.card_impl import HarmonizedTrioBrainstorm
from engine.card import Creature, Instant, ActivatedAbility
from engine.types import CardType, Keyword, ManaCost, ManaType
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------


class TestHarmonizedTrioProperties:
    """The creature face should have correct static characteristics."""

    def test_is_creature(self) -> None:
        card = HarmonizedTrioBrainstorm(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = HarmonizedTrioBrainstorm(owner=None)
        assert card.name == "Harmonized Trio"

    def test_mana_cost(self) -> None:
        card = HarmonizedTrioBrainstorm(owner=None)
        assert card.mana_cost == ManaCost.parse("{U}")

    def test_power_toughness(self) -> None:
        card = HarmonizedTrioBrainstorm(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 1

    def test_subtypes_include_merfolk_bard_wizard(self) -> None:
        card = HarmonizedTrioBrainstorm(owner=None)
        assert "Merfolk" in card.subtypes
        assert "Bard" in card.subtypes
        assert "Wizard" in card.subtypes


# ---------------------------------------------------------------------------
# Activated ability — becoming prepared
# ---------------------------------------------------------------------------


class TestHarmonizedTrioActivatedAbility:
    """The tap ability should exist and prepare the creature."""

    def test_has_activated_ability(self) -> None:
        card = HarmonizedTrioBrainstorm(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_activated_ability_is_activated_ability_type(self) -> None:
        card = HarmonizedTrioBrainstorm(owner=None)
        abilities = card.get_activated_abilities()
        assert isinstance(abilities[0], ActivatedAbility)

    def test_activation_taps_self(self) -> None:
        """Activating the ability should tap Harmonized Trio."""
        game = create_game()
        card = HarmonizedTrioBrainstorm(owner=game.players[0])
        card.controller = game.players[0]
        card.summoning_sick = False
        helper1 = Creature(name="Helper A", owner=game.players[0],
                           controller=game.players[0], base_power=1, base_toughness=1)
        helper1.summoning_sick = False
        helper2 = Creature(name="Helper B", owner=game.players[0],
                           controller=game.players[0], base_power=1, base_toughness=1)
        helper2.summoning_sick = False
        set_board_state(game, 0, battlefield=[card, helper1, helper2])

        # Activate the ability
        abilities = card.get_activated_abilities()
        abilities[0].cost(game)

        assert card.is_tapped is True

    def test_activation_taps_two_other_creatures(self) -> None:
        """Activating should tap two other untapped creatures you control."""
        game = create_game()
        card = HarmonizedTrioBrainstorm(owner=game.players[0])
        card.controller = game.players[0]
        card.summoning_sick = False
        helper1 = Creature(name="Helper A", owner=game.players[0],
                           controller=game.players[0], base_power=1, base_toughness=1)
        helper1.summoning_sick = False
        helper2 = Creature(name="Helper B", owner=game.players[0],
                           controller=game.players[0], base_power=1, base_toughness=1)
        helper2.summoning_sick = False
        set_board_state(game, 0, battlefield=[card, helper1, helper2])

        abilities = card.get_activated_abilities()
        abilities[0].cost(game)

        assert helper1.is_tapped is True
        assert helper2.is_tapped is True

    def test_activation_makes_creature_prepared(self) -> None:
        """After activation resolves, the creature should be prepared."""
        game = create_game()
        card = HarmonizedTrioBrainstorm(owner=game.players[0])
        card.controller = game.players[0]
        card.summoning_sick = False
        helper1 = Creature(name="Helper A", owner=game.players[0],
                           controller=game.players[0], base_power=1, base_toughness=1)
        helper1.summoning_sick = False
        helper2 = Creature(name="Helper B", owner=game.players[0],
                           controller=game.players[0], base_power=1, base_toughness=1)
        helper2.summoning_sick = False
        set_board_state(game, 0, battlefield=[card, helper1, helper2])

        abilities = card.get_activated_abilities()
        abilities[0].cost(game)
        abilities[0].effect(game)

        assert card.is_prepared is True

    def test_cannot_activate_when_tapped(self) -> None:
        """Cannot activate the ability if Harmonized Trio is already tapped."""
        game = create_game()
        card = HarmonizedTrioBrainstorm(owner=game.players[0])
        card.controller = game.players[0]
        card.summoning_sick = False
        card.is_tapped = True
        helper1 = Creature(name="Helper A", owner=game.players[0],
                           controller=game.players[0], base_power=1, base_toughness=1)
        helper1.summoning_sick = False
        helper2 = Creature(name="Helper B", owner=game.players[0],
                           controller=game.players[0], base_power=1, base_toughness=1)
        helper2.summoning_sick = False
        set_board_state(game, 0, battlefield=[card, helper1, helper2])

        abilities = card.get_activated_abilities()
        # Cost should fail/return False when creature is already tapped
        result = abilities[0].cost(game)
        assert result is False or result is None

    def test_cannot_activate_without_two_other_untapped_creatures(self) -> None:
        """Need at least two other untapped creatures to activate."""
        game = create_game()
        card = HarmonizedTrioBrainstorm(owner=game.players[0])
        card.controller = game.players[0]
        card.summoning_sick = False
        helper1 = Creature(name="Helper A", owner=game.players[0],
                           controller=game.players[0], base_power=1, base_toughness=1)
        helper1.summoning_sick = False
        # Only one helper — not enough
        set_board_state(game, 0, battlefield=[card, helper1])

        abilities = card.get_activated_abilities()
        result = abilities[0].cost(game)
        assert result is False or result is None


# ---------------------------------------------------------------------------
# Prepared state and Brainstorm spell
# ---------------------------------------------------------------------------


class TestHarmonizedTrioPreparedSpell:
    """While prepared, casting the spell copy should work like Brainstorm."""

    def test_not_prepared_initially(self) -> None:
        """A freshly-played Harmonized Trio is not prepared."""
        card = HarmonizedTrioBrainstorm(owner=None)
        assert card.is_prepared is False

    def test_brainstorm_draws_three_cards(self) -> None:
        """Casting the Brainstorm spell should draw three cards."""
        game = create_game()
        card = HarmonizedTrioBrainstorm(owner=game.players[0])
        card.controller = game.players[0]
        card.summoning_sick = False
        helper1 = Creature(name="Helper A", owner=game.players[0],
                           controller=game.players[0], base_power=1, base_toughness=1)
        helper1.summoning_sick = False
        helper2 = Creature(name="Helper B", owner=game.players[0],
                           controller=game.players[0], base_power=1, base_toughness=1)
        helper2.summoning_sick = False

        # Create library cards
        lib_cards = [
            Creature(name=f"LibCard{i}", owner=game.players[0],
                     base_power=1, base_toughness=1)
            for i in range(5)
        ]
        set_board_state(game, 0, battlefield=[card, helper1, helper2], hand=[])

        # Put cards in library
        library = game.get_library(game.players[0])
        for c in lib_cards:
            library.add(c)

        # Activate to become prepared
        abilities = card.get_activated_abilities()
        abilities[0].cost(game)
        abilities[0].effect(game)

        # Cast the Brainstorm spell copy
        hand_before = len(game.get_zone("hand", game.players[0]))
        card.cast_prepared_spell(game)

        # Net result of Brainstorm: draw 3, put back 2 = net +1 card in hand
        # But we need to check that 3 were drawn first
        # After full resolution: hand should have 3 drawn - 2 put back = 1 net
        hand_after = len(game.get_zone("hand", game.players[0]))
        assert hand_after == hand_before + 1

    def test_brainstorm_puts_two_cards_on_top_of_library(self) -> None:
        """After drawing 3, two cards should be put back on top of library."""
        game = create_game()
        card = HarmonizedTrioBrainstorm(owner=game.players[0])
        card.controller = game.players[0]
        card.summoning_sick = False
        helper1 = Creature(name="Helper A", owner=game.players[0],
                           controller=game.players[0], base_power=1, base_toughness=1)
        helper1.summoning_sick = False
        helper2 = Creature(name="Helper B", owner=game.players[0],
                           controller=game.players[0], base_power=1, base_toughness=1)
        helper2.summoning_sick = False

        lib_cards = [
            Creature(name=f"LibCard{i}", owner=game.players[0],
                     base_power=1, base_toughness=1)
            for i in range(5)
        ]
        set_board_state(game, 0, battlefield=[card, helper1, helper2], hand=[])

        library = game.get_library(game.players[0])
        for c in lib_cards:
            library.add(c)
        lib_size_before = len(library)

        # Activate and cast
        abilities = card.get_activated_abilities()
        abilities[0].cost(game)
        abilities[0].effect(game)
        card.cast_prepared_spell(game)

        # Library should have lost 3 (drawn) but gained 2 (put back) = net -1
        lib_size_after = len(game.get_library(game.players[0]))
        assert lib_size_after == lib_size_before - 1

    def test_casting_spell_unprepares(self) -> None:
        """Casting the prepared spell should unprepare the creature."""
        game = create_game()
        card = HarmonizedTrioBrainstorm(owner=game.players[0])
        card.controller = game.players[0]
        card.summoning_sick = False
        helper1 = Creature(name="Helper A", owner=game.players[0],
                           controller=game.players[0], base_power=1, base_toughness=1)
        helper1.summoning_sick = False
        helper2 = Creature(name="Helper B", owner=game.players[0],
                           controller=game.players[0], base_power=1, base_toughness=1)
        helper2.summoning_sick = False

        lib_cards = [
            Creature(name=f"LibCard{i}", owner=game.players[0],
                     base_power=1, base_toughness=1)
            for i in range(5)
        ]
        set_board_state(game, 0, battlefield=[card, helper1, helper2], hand=[])
        library = game.get_library(game.players[0])
        for c in lib_cards:
            library.add(c)

        # Activate to prepare
        abilities = card.get_activated_abilities()
        abilities[0].cost(game)
        abilities[0].effect(game)
        assert card.is_prepared is True

        # Cast the spell
        card.cast_prepared_spell(game)

        # Should now be unprepared
        assert card.is_prepared is False

    def test_cannot_cast_spell_when_not_prepared(self) -> None:
        """Should not be able to cast the spell if not prepared."""
        game = create_game()
        card = HarmonizedTrioBrainstorm(owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])

        # Attempting to cast when not prepared should fail
        with pytest.raises((ValueError, RuntimeError, AttributeError)):
            card.cast_prepared_spell(game)
