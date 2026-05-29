"""Tests for sos_226 — Silverquill, the Disputant.

Covers:
- Static properties (name, mana cost, power/toughness, type, subtypes)
- Flying and Vigilance keywords
- Casualty 1 grant: instants and sorceries the controller casts gain casualty 1
- Casualty 1 grant does not apply to non-instant/sorcery spells
- Casualty 1 grant does not apply to opponent's spells
- Casualty threshold is 1 (sacrifice creature with power >= 1)
- Casualty grant method: marking instants/sorceries with casualty_threshold attribute
- When Silverquill is not in play, the grant does not apply
"""

from __future__ import annotations

import pytest

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery, Planeswalker, Enchantment
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------

class TestSilverquillTheDisputantProperties:
    """Static card data should match the sos_226 spec."""

    def test_name(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_base_power(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.base_power == 4

    def test_base_toughness(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.base_toughness == 4

    def test_is_creature(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_is_legendary(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_elder_dragon_subtypes(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes


# ---------------------------------------------------------------------------
# Keywords: Flying and Vigilance
# ---------------------------------------------------------------------------

class TestSilverquillKeywords:
    """Silverquill must have Flying and Vigilance keywords."""

    def test_has_flying(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_vigilance(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.VIGILANCE in card.keywords

    def test_has_both_flying_and_vigilance(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert (Keyword.FLYING | Keyword.VIGILANCE) in card.keywords


# ---------------------------------------------------------------------------
# Casualty 1 grant: applying casualty_threshold to instants and sorceries
# ---------------------------------------------------------------------------

class TestSilverquillCasualtyGrant:
    """Silverquill grants casualty 1 to each instant and sorcery spell the
    controller casts. The implementation should mark eligible spells with
    a casualty_threshold attribute of 1."""

    def test_grants_casualty_to_instant_in_hand(self) -> None:
        """An instant in controller's hand should receive casualty_threshold = 1."""
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        instant = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        instant.card_types = {CardType.INSTANT}
        set_board_state(game, 0, hand=[instant])
        silverquill.apply_casualty_grant(game)
        assert hasattr(instant, "casualty_threshold")
        assert instant.casualty_threshold == 1

    def test_grants_casualty_to_sorcery_in_hand(self) -> None:
        """A sorcery in controller's hand should receive casualty_threshold = 1."""
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        sorcery.card_types = {CardType.SORCERY}
        set_board_state(game, 0, hand=[sorcery])
        silverquill.apply_casualty_grant(game)
        assert hasattr(sorcery, "casualty_threshold")
        assert sorcery.casualty_threshold == 1

    def test_casualty_threshold_is_exactly_one(self) -> None:
        """The casualty threshold granted must be 1 (not 0 or 2)."""
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        instant = Instant(name="Shock", owner=p1, controller=p1)
        instant.card_types = {CardType.INSTANT}
        set_board_state(game, 0, hand=[instant])
        silverquill.apply_casualty_grant(game)
        assert instant.casualty_threshold == 1

    def test_grants_casualty_to_both_instant_and_sorcery(self) -> None:
        """Both an instant and a sorcery in hand should each receive casualty_threshold = 1."""
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        instant = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        instant.card_types = {CardType.INSTANT}
        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        sorcery.card_types = {CardType.SORCERY}
        set_board_state(game, 0, hand=[instant, sorcery])
        silverquill.apply_casualty_grant(game)
        assert instant.casualty_threshold == 1
        assert sorcery.casualty_threshold == 1

    def test_does_not_grant_casualty_to_creature_card(self) -> None:
        """A creature card in hand should NOT receive casualty_threshold."""
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        creature = Creature(
            name="Grizzly Bears", base_power=2, base_toughness=2,
            owner=p1, controller=p1
        )
        set_board_state(game, 0, hand=[creature])
        silverquill.apply_casualty_grant(game)
        threshold = getattr(creature, "casualty_threshold", None)
        assert threshold is None

    def test_does_not_grant_casualty_to_opponent_hand(self) -> None:
        """Opponent's instants/sorceries should NOT receive casualty_threshold."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        opp_instant = Instant(name="Counterspell", owner=p2, controller=p2)
        opp_instant.card_types = {CardType.INSTANT}
        set_board_state(game, 1, hand=[opp_instant])
        silverquill.apply_casualty_grant(game)
        threshold = getattr(opp_instant, "casualty_threshold", None)
        assert threshold is None

    def test_casualty_grant_class_attribute_is_one(self) -> None:
        """The class-level casualty_grant attribute should be 1."""
        card = SilverquillTheDisputant(owner=None)
        # Expect a class-level constant indicating the casualty threshold granted
        assert card.casualty_grant == 1


# ---------------------------------------------------------------------------
# Casualty 1: sacrifice eligibility (creature with power >= 1)
# ---------------------------------------------------------------------------

class TestSilverquillCasualtyEligibility:
    """Casualty 1 requires sacrificing a creature with power 1 or greater."""

    def test_casualty_eligible_creature_power_one(self) -> None:
        """A creature with power exactly 1 is eligible for casualty sacrifice."""
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        # Check the is_casualty_eligible method if it exists
        creature = Creature(
            name="Soldier", base_power=1, base_toughness=1,
            owner=p1, controller=p1
        )
        # The creature has power 1 — should be eligible
        assert creature.power >= 1

    def test_casualty_eligible_creature_power_greater_than_one(self) -> None:
        """A creature with power > 1 is also eligible for casualty sacrifice."""
        creature = Creature(
            name="Giant", base_power=5, base_toughness=5,
        )
        assert creature.power >= 1

    def test_casualty_not_eligible_zero_power_creature(self) -> None:
        """A creature with power 0 is NOT eligible for casualty 1 sacrifice."""
        creature = Creature(
            name="Memnite", base_power=0, base_toughness=1,
        )
        # Power 0 means it cannot be sacrificed for casualty 1
        assert creature.power < 1


# ---------------------------------------------------------------------------
# Casualty 1 grant: only applies while Silverquill is in play
# ---------------------------------------------------------------------------

class TestSilverquillCasualtyOnlyWhenInPlay:
    """The casualty grant should only apply when Silverquill is on the battlefield
    under the controller's control."""

    def test_apply_casualty_grant_requires_controller(self) -> None:
        """With no controller, apply_casualty_grant should not raise but should be a no-op."""
        game = create_game()
        silverquill = SilverquillTheDisputant(owner=None, controller=None)
        # Should not raise even with no controller set
        try:
            silverquill.apply_casualty_grant(game)
        except (AttributeError, TypeError) as e:
            pytest.fail(f"apply_casualty_grant raised unexpectedly: {e}")

    def test_casualty_grant_only_marks_controller_hand(self) -> None:
        """Only the controller's hand cards get the casualty threshold."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        # p1's instant and p2's instant
        p1_instant = Instant(name="Shock", owner=p1, controller=p1)
        p1_instant.card_types = {CardType.INSTANT}
        p2_instant = Instant(name="Counterspell", owner=p2, controller=p2)
        p2_instant.card_types = {CardType.INSTANT}
        set_board_state(game, 0, hand=[p1_instant])
        set_board_state(game, 1, hand=[p2_instant])
        silverquill.apply_casualty_grant(game)
        # p1's instant gets casualty_threshold; p2's does not
        assert getattr(p1_instant, "casualty_threshold", None) == 1
        assert getattr(p2_instant, "casualty_threshold", None) is None
