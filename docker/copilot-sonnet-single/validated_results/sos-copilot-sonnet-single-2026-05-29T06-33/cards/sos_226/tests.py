"""Tests for SOS 226 — Silverquill, the Disputant.

Oracle text:
  Flying, vigilance
  Each instant and sorcery spell you cast has casualty 1. (As you cast that
  spell, you may sacrifice a creature with power 1 or greater. When you do,
  copy the spell and you may choose new targets for the copy.)

Tests cover:
- Static card properties (name, mana_cost, P/T, legendary, subtypes, card type)
- Flying and Vigilance keywords
- Continuous effect: instants in controller's hand get casualty = 1 when on battlefield
- Continuous effect: sorceries in controller's hand get casualty = 1 when on battlefield
- Continuous effect: value of casualty is exactly 1
- Continuous effect: non-instant/sorcery cards are NOT granted casualty
- Continuous effect: opponent's instants/sorceries are NOT granted casualty
- Continuous effect: effect is NOT active when Silverquill is not on the battlefield
- register_triggers registers a continuous effect into effect_manager
"""

from __future__ import annotations

import pytest

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static property tests
# ---------------------------------------------------------------------------


class TestSilverquillTheDisputantProperties:
    """Static card data must match the SOS 226 spec."""

    def test_is_creature(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert isinstance(card, Creature)

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

    def test_has_creature_card_type(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_is_legendary(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_elder_subtype(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert "Elder" in card.subtypes

    def test_has_dragon_subtype(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert "Dragon" in card.subtypes


# ---------------------------------------------------------------------------
# Keyword tests — Flying and Vigilance
# ---------------------------------------------------------------------------


class TestSilverquillTheDisputantKeywords:
    """Silverquill must have both Flying and Vigilance."""

    def test_has_flying(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_vigilance(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.VIGILANCE in card.keywords

    def test_does_not_have_haste(self) -> None:
        """Vigilance, not haste — sanity check the keywords are correct."""
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.HASTE not in card.keywords


# ---------------------------------------------------------------------------
# Casualty 1 continuous grant tests
# ---------------------------------------------------------------------------


class TestSilverquillTheDisputantCasualtyGrant:
    """While on the battlefield, Silverquill grants casualty 1 to each instant
    and sorcery spell the controller casts.  The implementation is expected to
    mark cards in the controller's hand (or at cast time) with a ``casualty``
    attribute equal to 1, mirroring the miracle-grant pattern.
    """

    def _setup_silverquill_on_battlefield(self, game, player_index: int = 0):
        """Place Silverquill on player's battlefield and register its triggers."""
        player = game.players[player_index]
        silverquill = SilverquillTheDisputant(owner=player, controller=player)
        set_board_state(game, player_index, battlefield=[silverquill])
        silverquill.register_triggers(game)
        return silverquill

    def test_instant_in_hand_gets_casualty_cost(self) -> None:
        """An instant in the controller's hand acquires casualty == 1."""
        game = create_game()
        p1 = game.players[0]
        self._setup_silverquill_on_battlefield(game, 0)

        lightning = Instant(
            name="Lightning Bolt",
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[lightning])

        # Apply continuous effects registered by Silverquill
        game.effect_manager.apply_all(game)

        assert hasattr(lightning, "casualty"), (
            "Instant in controller's hand should have casualty attribute set by Silverquill"
        )
        assert lightning.casualty == 1, (
            f"casualty should be 1, got {lightning.casualty!r}"
        )

    def test_sorcery_in_hand_gets_casualty_cost(self) -> None:
        """A sorcery in the controller's hand acquires casualty == 1."""
        game = create_game()
        p1 = game.players[0]
        self._setup_silverquill_on_battlefield(game, 0)

        divination = Sorcery(
            name="Divination",
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[divination])

        game.effect_manager.apply_all(game)

        assert hasattr(divination, "casualty"), (
            "Sorcery in controller's hand should have casualty attribute set by Silverquill"
        )
        assert divination.casualty == 1, (
            f"casualty should be 1, got {divination.casualty!r}"
        )

    def test_casualty_value_is_exactly_one(self) -> None:
        """The casualty cost granted must be 1 (not 0, not 2)."""
        game = create_game()
        p1 = game.players[0]
        self._setup_silverquill_on_battlefield(game, 0)

        shock = Instant(name="Shock", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[shock])

        game.effect_manager.apply_all(game)

        casualty = getattr(shock, "casualty", None)
        assert casualty == 1, (
            f"Expected casualty == 1 (casualty 1 from card text), got {casualty!r}"
        )

    def test_creature_in_hand_does_not_get_casualty(self) -> None:
        """A creature card in hand must NOT receive the casualty 1 grant."""
        game = create_game()
        p1 = game.players[0]
        self._setup_silverquill_on_battlefield(game, 0)

        bear = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, hand=[bear])

        game.effect_manager.apply_all(game)

        casualty = getattr(bear, "casualty", None)
        assert casualty != 1, (
            "Creature in hand must not receive casualty 1 from Silverquill"
        )

    def test_casualty_grant_not_applied_when_silverquill_not_on_battlefield(self) -> None:
        """Without Silverquill on the battlefield, instants in hand have no casualty grant."""
        game = create_game()
        p1 = game.players[0]

        # Silverquill is NOT on the battlefield — no register_triggers call
        counterspell = Instant(
            name="Counterspell",
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, hand=[counterspell])

        game.effect_manager.apply_all(game)

        casualty = getattr(counterspell, "casualty", None)
        assert casualty != 1, (
            "Instant should NOT have casualty 1 without Silverquill on the battlefield"
        )

    def test_opponent_instant_does_not_get_casualty(self) -> None:
        """Opponent's instants in hand must NOT receive Silverquill's casualty grant."""
        game = create_game()
        self._setup_silverquill_on_battlefield(game, 0)  # player 0's battlefield

        p2 = game.players[1]
        opponent_instant = Instant(
            name="Negate",
            owner=p2,
            controller=p2,
        )
        set_board_state(game, 1, hand=[opponent_instant])

        game.effect_manager.apply_all(game)

        casualty = getattr(opponent_instant, "casualty", None)
        assert casualty != 1, (
            "Opponent's instant in hand must not receive Silverquill's casualty grant"
        )

    def test_opponent_sorcery_does_not_get_casualty(self) -> None:
        """Opponent's sorceries in hand must NOT receive Silverquill's casualty grant."""
        game = create_game()
        self._setup_silverquill_on_battlefield(game, 0)

        p2 = game.players[1]
        opponent_sorcery = Sorcery(
            name="Mind Rot",
            owner=p2,
            controller=p2,
        )
        set_board_state(game, 1, hand=[opponent_sorcery])

        game.effect_manager.apply_all(game)

        casualty = getattr(opponent_sorcery, "casualty", None)
        assert casualty != 1, (
            "Opponent's sorcery in hand must not receive Silverquill's casualty grant"
        )

    def test_register_triggers_adds_continuous_effect(self) -> None:
        """register_triggers must register at least one continuous effect
        into the game's effect_manager when called."""
        game = create_game()
        p1 = game.players[0]

        effects_before = len(game.effect_manager.get_all())

        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        silverquill.register_triggers(game)

        effects_after = len(game.effect_manager.get_all())
        assert effects_after > effects_before, (
            "register_triggers should add at least one continuous effect to effect_manager"
        )

    def test_casualty_grant_is_idempotent_after_multiple_apply_all(self) -> None:
        """Calling effect_manager.apply_all multiple times should not accumulate
        the casualty value beyond 1."""
        game = create_game()
        p1 = game.players[0]
        self._setup_silverquill_on_battlefield(game, 0)

        shock = Instant(name="Shock", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[shock])

        game.effect_manager.apply_all(game)
        game.effect_manager.apply_all(game)
        game.effect_manager.apply_all(game)

        casualty = getattr(shock, "casualty", None)
        assert casualty == 1, (
            f"Casualty should still be exactly 1 after multiple apply_all calls, got {casualty!r}"
        )

    def test_multiple_instants_in_hand_all_get_casualty(self) -> None:
        """All instants in the controller's hand should receive casualty 1."""
        game = create_game()
        p1 = game.players[0]
        self._setup_silverquill_on_battlefield(game, 0)

        shock = Instant(name="Shock", owner=p1, controller=p1)
        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        negate = Instant(name="Negate", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[shock, bolt, negate])

        game.effect_manager.apply_all(game)

        for spell in [shock, bolt, negate]:
            casualty = getattr(spell, "casualty", None)
            assert casualty == 1, (
                f"{spell.name} should have casualty == 1, got {casualty!r}"
            )
