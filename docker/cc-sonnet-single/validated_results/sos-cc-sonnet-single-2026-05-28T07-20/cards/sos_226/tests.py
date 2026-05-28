"""Tests for sos_226 — Silverquill, the Disputant.

Tests cover:
- Static card properties (name, mana cost, P/T, keywords, supertypes, subtypes)
- Card type (CREATURE), legendary supertype, colors (W/B)
- Flying and Vigilance keywords
- Elder Dragon subtype
- Casualty grant: get_casualty_value(card) returns 1 for instants and sorceries
- Casualty grant does NOT apply to non-instant/sorcery cards
- Casualty grant does NOT apply to opponent's cards
- Casualty mechanic: when player sacrifices a creature with power >= 1, a copy
  of the spell is created on the stack
- Original spell still resolves after casualty copy is created
- No casualty triggered when no eligible creature (power >= 1) is on battlefield
- Casualty mechanic: creature with power < 1 is ineligible as sacrifice
"""

from __future__ import annotations

import pytest

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestSilverquillStaticProperties:
    """Static card data must match the sos_226 spec."""

    def test_name(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"

    def test_is_creature(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_mana_cost_contains_white_pip(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert ManaType.WHITE in card.mana_cost.pips

    def test_mana_cost_contains_black_pip(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert ManaType.BLACK in card.mana_cost.pips

    def test_base_power(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.base_power == 4

    def test_base_toughness(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.base_toughness == 4

    def test_has_flying(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_vigilance(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.VIGILANCE in card.keywords

    def test_is_legendary(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_is_elder_dragon(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes


# ---------------------------------------------------------------------------
# Casualty grant — method existence and API
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyGrantAPI:
    """Silverquill must expose a get_casualty_value(card) method."""

    def test_has_get_casualty_value_method(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert hasattr(card, "get_casualty_value"), (
            "SilverquillTheDisputant must implement get_casualty_value(card)"
        )

    def test_get_casualty_value_callable(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert callable(card.get_casualty_value)


# ---------------------------------------------------------------------------
# Casualty grant — instant and sorcery cards get casualty 1
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyGrantValue:
    """Each instant and sorcery you cast has casualty 1 while Silverquill is on the battlefield."""

    def test_instant_gets_casualty_value_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        instant = Instant(name="Test Shock", owner=p1, controller=p1)
        game.get_battlefield(p1).add(silverquill)
        game.get_hand(p1).add(instant)
        silverquill.register_triggers(game)

        value = silverquill.get_casualty_value(instant)
        assert value == 1, (
            f"Expected casualty value 1 for instant, got {value!r}"
        )

    def test_sorcery_gets_casualty_value_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        sorcery = Sorcery(name="Test Divination", owner=p1, controller=p1)
        game.get_battlefield(p1).add(silverquill)
        game.get_hand(p1).add(sorcery)
        silverquill.register_triggers(game)

        value = silverquill.get_casualty_value(sorcery)
        assert value == 1, (
            f"Expected casualty value 1 for sorcery, got {value!r}"
        )

    def test_creature_does_not_get_casualty(self) -> None:
        """A creature card is not an instant or sorcery — should return None or 0."""
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        creature = Creature(name="Test Bear", base_power=2, base_toughness=2,
                            owner=p1, controller=p1)
        game.get_battlefield(p1).add(silverquill)

        value = silverquill.get_casualty_value(creature)
        assert not value, (
            f"Expected no casualty value for creature card, got {value!r}"
        )

    def test_opponent_instant_does_not_get_casualty(self) -> None:
        """Casualty should only grant to spells cast by this card's controller."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        opponent_instant = Instant(name="Opponent Shock", owner=p2, controller=p2)
        game.get_battlefield(p1).add(silverquill)
        game.get_hand(p2).add(opponent_instant)
        silverquill.register_triggers(game)

        value = silverquill.get_casualty_value(opponent_instant)
        assert not value, (
            "Casualty 1 should not apply to opponent's spells"
        )

    def test_uncontrolled_silverquill_returns_none(self) -> None:
        """When Silverquill has no controller set, get_casualty_value returns None/falsy."""
        card = SilverquillTheDisputant(owner=None)
        # No controller set
        card.controller = None
        instant = Instant(name="Test Instant", owner=None)
        value = card.get_casualty_value(instant)
        assert not value, (
            "Uncontrolled Silverquill should not grant casualty"
        )


# ---------------------------------------------------------------------------
# Casualty mechanic — sacrifice to copy the spell
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyCopyMechanic:
    """When controller sacrifices a creature with power >= 1, the spell is copied."""

    def test_casting_instant_with_casualty_creates_copy_on_stack(self) -> None:
        """Sacrificing a power-1 creature when casting an instant puts a copy on the stack."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Sacrifice Me", base_power=1, base_toughness=1,
            owner=p1, controller=p1
        )
        # A simple instant that the controller will cast
        instant = Instant(name="Test Instant Spell", owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[silverquill, fodder])
        game.get_hand(p1).add(instant)
        silverquill.register_triggers(game)

        # Script p1: yes to using casualty, then choose fodder as the sacrifice
        from collections import deque
        p1._script = deque([True, fodder])

        # Place instant on the stack manually and invoke the casualty hook
        # (simulating what the casting pipeline would do via on_cast)
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN
        game.active_player_index = 0

        # Directly invoke on_cast on the instant with Silverquill on the field
        instant.controller = p1
        instant.owner = p1

        stack_before = game.stack.size()
        silverquill._apply_casualty_for_spell(game, instant)
        stack_after = game.stack.size()

        assert stack_after > stack_before, (
            "Sacrificing a creature for casualty must push a copy onto the stack"
        )

    def test_casualty_creature_leaves_battlefield(self) -> None:
        """The sacrificed creature must leave the battlefield (go to graveyard)."""
        game = create_game()
        p1 = game.players[0]

        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Sacrifice Target", base_power=2, base_toughness=2,
            owner=p1, controller=p1
        )
        instant = Instant(name="Bolt", owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[silverquill, fodder])

        from collections import deque
        p1._script = deque([True, fodder])

        instant.controller = p1
        instant.owner = p1
        silverquill._apply_casualty_for_spell(game, instant)

        bf_cards = game.get_battlefield(p1).get_all()
        assert fodder not in bf_cards, (
            "Sacrificed creature must no longer be on the battlefield"
        )

    def test_casualty_sacrificed_creature_goes_to_graveyard(self) -> None:
        """The creature sacrificed for casualty goes to the graveyard."""
        game = create_game()
        p1 = game.players[0]

        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Sacrifice Me", base_power=1, base_toughness=1,
            owner=p1, controller=p1
        )
        instant = Instant(name="Test Instant", owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[silverquill, fodder])

        from collections import deque
        p1._script = deque([True, fodder])

        instant.controller = p1
        instant.owner = p1
        silverquill._apply_casualty_for_spell(game, instant)

        graveyard = game.get_graveyard(p1).get_all()
        assert fodder in graveyard, (
            "The casualty-sacrificed creature must end up in the graveyard"
        )

    def test_declining_casualty_does_not_create_copy(self) -> None:
        """If the player declines to sacrifice, no copy is created."""
        game = create_game()
        p1 = game.players[0]

        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Spare Me", base_power=1, base_toughness=1,
            owner=p1, controller=p1
        )
        instant = Instant(name="Test Instant", owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[silverquill, fodder])

        from collections import deque
        p1._script = deque([False])  # Decline casualty

        instant.controller = p1
        instant.owner = p1
        stack_before = game.stack.size()
        silverquill._apply_casualty_for_spell(game, instant)
        stack_after = game.stack.size()

        assert stack_after == stack_before, (
            "Declining casualty must not push a copy onto the stack"
        )

    def test_no_casualty_when_no_eligible_creature(self) -> None:
        """If the controller has no creatures with power >= 1, no copy should be created."""
        game = create_game()
        p1 = game.players[0]

        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        # A 0/1 creature has power 0 — not eligible for casualty 1
        zero_power = Creature(
            name="Wall Token", base_power=0, base_toughness=1,
            owner=p1, controller=p1
        )
        instant = Instant(name="Test Instant", owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[silverquill, zero_power])

        instant.controller = p1
        instant.owner = p1
        stack_before = game.stack.size()
        # Even if scripted to say yes, no eligible creatures exist
        from collections import deque
        p1._script = deque([True])
        silverquill._apply_casualty_for_spell(game, instant)
        stack_after = game.stack.size()

        assert stack_after == stack_before, (
            "No copy should be created when no creature with power >= 1 is available"
        )

    def test_creature_with_power_ge_1_is_eligible_for_casualty(self) -> None:
        """A creature with power exactly 1 is eligible to be sacrificed for casualty 1."""
        game = create_game()
        p1 = game.players[0]

        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        eligible = Creature(
            name="Hawk", base_power=1, base_toughness=1,
            owner=p1, controller=p1
        )
        instant = Instant(name="Test Instant", owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[silverquill, eligible])

        from collections import deque
        p1._script = deque([True, eligible])

        instant.controller = p1
        instant.owner = p1
        stack_before = game.stack.size()
        silverquill._apply_casualty_for_spell(game, instant)
        stack_after = game.stack.size()

        assert stack_after > stack_before, (
            "A creature with power 1 must be an eligible casualty sacrifice"
        )

    def test_casualty_does_not_fire_for_non_instant_sorcery(self) -> None:
        """Casualty only applies to instants and sorceries — not creatures or enchantments."""
        game = create_game()
        p1 = game.players[0]

        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        fodder = Creature(
            name="Spare Me", base_power=2, base_toughness=2,
            owner=p1, controller=p1
        )
        non_spell = Creature(name="Another Bear", base_power=2, base_toughness=2,
                             owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[silverquill, fodder])

        from collections import deque
        p1._script = deque([True, fodder])

        non_spell.controller = p1
        non_spell.owner = p1
        stack_before = game.stack.size()
        # _apply_casualty_for_spell should be a no-op for non-instant/sorcery
        silverquill._apply_casualty_for_spell(game, non_spell)
        stack_after = game.stack.size()

        assert stack_after == stack_before, (
            "Casualty must not trigger for creature cards — only instants and sorceries"
        )
