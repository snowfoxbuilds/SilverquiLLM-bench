"""Tests for sos_201 — Lorehold, the Historian.

A Legendary Creature — Elder Dragon with mana cost {3}{R}{W}, 5/5.
  Flying, Haste
  Each instant and sorcery card in your hand has miracle {2}.
  At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.

Test categories:
  1. Static card properties (name, mana cost, P/T, type, subtypes, supertypes, keywords)
  2. Upkeep trigger registration
  3. Upkeep trigger effect — discard enables a draw (looting)
  4. Upkeep trigger effect — skipping discard means no draw (optional)
  5. Upkeep trigger only fires on opponent's upkeep, not controller's
  6. Miracle mechanic — miracle cost constant is {2}
  7. Miracle mechanic — card exposes a method to check miracle eligibility
  8. Miracle mechanic — instants/sorceries are eligible, creatures are not
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_instant(name: str = "TestInstant", owner: Any = None) -> Instant:
    """Return a minimal instant card."""
    c = Instant(name=name, owner=owner, controller=owner)
    return c


def _make_sorcery(name: str = "TestSorcery", owner: Any = None) -> Sorcery:
    """Return a minimal sorcery card."""
    c = Sorcery(name=name, owner=owner, controller=owner)
    return c


def _make_creature(name: str = "TestCreature", owner: Any = None) -> Creature:
    """Return a minimal creature card."""
    c = Creature(name=name, owner=owner, controller=owner, base_power=1, base_toughness=1)
    return c


# ---------------------------------------------------------------------------
# 1. Static card properties
# ---------------------------------------------------------------------------


class TestLoreholdProperties:
    """Static card data must match the sos_201 spec."""

    def test_is_creature_subclass(self) -> None:
        """LoreholdTheHistorian must be a Creature instance."""
        card = LoreholdTheHistorian(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"

    def test_mana_cost(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_power(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_power == 5

    def test_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_toughness == 5

    def test_card_type_creature(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_legendary_supertype(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_elder_dragon_subtypes(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_flying_keyword(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_haste_keyword(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.HASTE in card.keywords


# ---------------------------------------------------------------------------
# 2. Upkeep trigger registration
# ---------------------------------------------------------------------------


class TestLoreholdUpkeepTriggerRegistration:
    """register_triggers() must wire a trigger for BeginningOfUpkeepTriggeredEvent."""

    def test_registers_at_least_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        before = len(game.trigger_manager._triggers)
        card.register_triggers(game)
        after = len(game.trigger_manager._triggers)
        assert after > before

    def test_registered_trigger_uses_upkeep_event(self) -> None:
        """The registered trigger must watch BeginningOfUpkeepTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)
        upkeep_triggers = [
            t for t in game.trigger_manager._triggers
            if t.source is card
            and t.event_type is BeginningOfUpkeepTriggeredEvent
        ]
        assert len(upkeep_triggers) >= 1

    def test_registered_trigger_is_trigger_registration_instance(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)
        card_triggers = [t for t in game.trigger_manager._triggers if t.source is card]
        assert len(card_triggers) >= 1, "At least one trigger must be registered by Lorehold"
        for t in card_triggers:
            assert isinstance(t, TriggerRegistration)


# ---------------------------------------------------------------------------
# 3. Upkeep trigger: discard enables draw (looting)
# ---------------------------------------------------------------------------


class TestLoreholdLootEffect:
    """When the trigger fires and the controller discards a card, they draw one."""

    def test_discard_then_draw_net_zero_hand_size(self) -> None:
        """Discarding one and drawing one should leave hand size unchanged."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        # Put a known card in p1's hand and some cards in library.
        hand_card = _make_instant("HandCard", owner=p1)
        p1.zones[Zone.HAND].add(hand_card)

        # Put a card in library for the draw.
        library_card = _make_sorcery("LibCard", owner=p1)
        p1.zones[Zone.LIBRARY].add(library_card)

        hand_before = len(p1.zones[Zone.HAND].get_all())

        # Simulate: player chooses to discard (yes) and picks hand_card.
        # The implementation will call choose_yes_no (or similar) and choose_card.
        # We directly invoke the trigger effect as a unit test.
        loot_trigger = None
        for t in game.trigger_manager._triggers:
            if (t.source is card and
                    t.event_type is BeginningOfUpkeepTriggeredEvent):
                loot_trigger = t
                break
        assert loot_trigger is not None, "Loot trigger not registered"

        # Set p2 as active player (opponent's upkeep).
        game.active_player_index = 1

        # Supply scripted choices: yes (discard), then pick hand_card.
        from engine.player import DeterministicPlayer
        p1_scripted = DeterministicPlayer("P1", script=[True, hand_card])
        p1_scripted.zones = p1.zones
        p1_scripted.life = p1.life
        loot_trigger.controller = p1_scripted
        # Patch controller on the card.
        card.controller = p1_scripted

        loot_trigger.effect(game)

        hand_after = len(p1_scripted.zones[Zone.HAND].get_all())
        # Net effect: -1 (discard) +1 (draw) == 0 change.
        assert hand_after == hand_before

    def test_discard_moves_card_to_graveyard(self) -> None:
        """The discarded card must end up in the graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        hand_card = _make_instant("Discard_Target", owner=p1)
        p1.zones[Zone.HAND].add(hand_card)

        # Library card to draw.
        library_card = _make_sorcery("LibCard2", owner=p1)
        p1.zones[Zone.LIBRARY].add(library_card)

        loot_trigger = next(
            (t for t in game.trigger_manager._triggers
             if t.source is card and t.event_type is BeginningOfUpkeepTriggeredEvent),
            None,
        )
        assert loot_trigger is not None

        game.active_player_index = 1  # Opponent's turn.

        from engine.player import DeterministicPlayer
        p1_scripted = DeterministicPlayer("P1", script=[True, hand_card])
        p1_scripted.zones = p1.zones
        p1_scripted.life = p1.life
        loot_trigger.controller = p1_scripted
        card.controller = p1_scripted

        graveyard_before = len(p1_scripted.zones[Zone.GRAVEYARD].get_all())
        loot_trigger.effect(game)
        graveyard_after = len(p1_scripted.zones[Zone.GRAVEYARD].get_all())
        assert graveyard_after > graveyard_before

    def test_draw_card_added_to_hand(self) -> None:
        """After discarding, the drawn card should be in hand."""
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        # Clear hand and library for clean state.
        for c in p1.zones[Zone.HAND].get_all():
            p1.zones[Zone.HAND].remove(c)
        for c in p1.zones[Zone.LIBRARY].get_all():
            p1.zones[Zone.LIBRARY].remove(c)

        hand_card = _make_instant("ToDiscard", owner=p1)
        library_card = _make_sorcery("ToDraw", owner=p1)
        p1.zones[Zone.HAND].add(hand_card)
        p1.zones[Zone.LIBRARY].add(library_card)

        loot_trigger = next(
            (t for t in game.trigger_manager._triggers
             if t.source is card and t.event_type is BeginningOfUpkeepTriggeredEvent),
            None,
        )
        assert loot_trigger is not None

        game.active_player_index = 1

        from engine.player import DeterministicPlayer
        p1_scripted = DeterministicPlayer("P1", script=[True, hand_card])
        p1_scripted.zones = p1.zones
        p1_scripted.life = p1.life
        loot_trigger.controller = p1_scripted
        card.controller = p1_scripted

        loot_trigger.effect(game)
        # The library_card should now be in hand.
        assert p1_scripted.zones[Zone.HAND].contains(library_card)


# ---------------------------------------------------------------------------
# 4. Upkeep trigger: optional — no discard means no draw
# ---------------------------------------------------------------------------


class TestLoreholdNoLoot:
    """When the controller declines to discard, no card is drawn."""

    def test_decline_to_discard_no_draw(self) -> None:
        """If the controller says no, hand size should decrease by 0 (unchanged)."""
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        # Put a card in hand and library.
        hand_card = _make_instant("HoldCard", owner=p1)
        p1.zones[Zone.HAND].add(hand_card)

        library_card = _make_sorcery("LibCard3", owner=p1)
        p1.zones[Zone.LIBRARY].add(library_card)

        hand_before = len(p1.zones[Zone.HAND].get_all())

        loot_trigger = next(
            (t for t in game.trigger_manager._triggers
             if t.source is card and t.event_type is BeginningOfUpkeepTriggeredEvent),
            None,
        )
        assert loot_trigger is not None

        game.active_player_index = 1

        # Player says "no" to discarding.
        from engine.player import DeterministicPlayer
        p1_scripted = DeterministicPlayer("P1", script=[False])
        p1_scripted.zones = p1.zones
        p1_scripted.life = p1.life
        loot_trigger.controller = p1_scripted
        card.controller = p1_scripted

        loot_trigger.effect(game)

        hand_after = len(p1_scripted.zones[Zone.HAND].get_all())
        assert hand_after == hand_before  # No change — optional not taken.

    def test_decline_means_no_library_depletion(self) -> None:
        """Declining the discard should not draw from the library."""
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        for c in p1.zones[Zone.LIBRARY].get_all():
            p1.zones[Zone.LIBRARY].remove(c)

        library_card = _make_sorcery("OnlyLibCard", owner=p1)
        p1.zones[Zone.LIBRARY].add(library_card)
        lib_before = len(p1.zones[Zone.LIBRARY].get_all())

        loot_trigger = next(
            (t for t in game.trigger_manager._triggers
             if t.source is card and t.event_type is BeginningOfUpkeepTriggeredEvent),
            None,
        )
        assert loot_trigger is not None

        game.active_player_index = 1

        from engine.player import DeterministicPlayer
        p1_scripted = DeterministicPlayer("P1", script=[False])
        p1_scripted.zones = p1.zones
        p1_scripted.life = p1.life
        loot_trigger.controller = p1_scripted
        card.controller = p1_scripted

        loot_trigger.effect(game)

        lib_after = len(p1_scripted.zones[Zone.LIBRARY].get_all())
        assert lib_after == lib_before  # Library untouched.


# ---------------------------------------------------------------------------
# 5. Upkeep trigger condition — fires only on opponent's upkeep
# ---------------------------------------------------------------------------


class TestLoreholdUpkeepCondition:
    """The loot trigger's condition must evaluate to True on opponent's turn
    and False on the controller's own turn."""

    def test_trigger_condition_false_on_own_upkeep(self) -> None:
        """Trigger must NOT fire when active player is the controller."""
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)

        loot_trigger = next(
            (t for t in game.trigger_manager._triggers
             if t.source is card and t.event_type is BeginningOfUpkeepTriggeredEvent),
            None,
        )
        assert loot_trigger is not None, "Upkeep trigger not found"

        # Controller is p1 at index 0; active player is also p1 (own upkeep).
        game.active_player_index = 0
        event = BeginningOfUpkeepTriggeredEvent()

        if loot_trigger.condition is not None:
            result = loot_trigger.condition(game, event)
            assert result is False, "Trigger should not fire on controller's own upkeep"

    def test_trigger_condition_true_on_opponent_upkeep(self) -> None:
        """Trigger MUST fire when active player is an opponent."""
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)

        loot_trigger = next(
            (t for t in game.trigger_manager._triggers
             if t.source is card and t.event_type is BeginningOfUpkeepTriggeredEvent),
            None,
        )
        assert loot_trigger is not None

        # Active player is p2 (opponent of p1 who controls Lorehold).
        game.active_player_index = 1
        event = BeginningOfUpkeepTriggeredEvent()

        if loot_trigger.condition is not None:
            result = loot_trigger.condition(game, event)
            assert result is True, "Trigger should fire on opponent's upkeep"


# ---------------------------------------------------------------------------
# 6. Miracle cost constant
# ---------------------------------------------------------------------------


class TestLoreholdMiracleCost:
    """Lorehold grants miracle {2} — the implementation must expose this cost."""

    def test_miracle_cost_attribute_is_two_generic(self) -> None:
        """The card should have a miracle_cost equal to ManaCost.parse('{2}')."""
        card = LoreholdTheHistorian(owner=None)
        assert hasattr(card, "miracle_cost"), (
            "LoreholdTheHistorian must have a 'miracle_cost' attribute"
        )
        assert card.miracle_cost == ManaCost.parse("{2}")

    def test_miracle_cost_cmc_is_two(self) -> None:
        """The miracle cost CMC should be 2."""
        card = LoreholdTheHistorian(owner=None)
        assert card.miracle_cost.cmc == 2


# ---------------------------------------------------------------------------
# 7 & 8. Miracle eligibility — instants/sorceries yes, others no
# ---------------------------------------------------------------------------


class TestLoreholdMiracleEligibility:
    """The card must expose a way to determine which cards in hand get miracle {2}.

    The expected API is a method `is_miracle_eligible(card)` that returns True
    for instant and sorcery cards and False for all others.
    """

    def test_instant_is_miracle_eligible(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        instant = _make_instant("Lightning Bolt", owner=p1)
        assert lorehold.is_miracle_eligible(instant) is True

    def test_sorcery_is_miracle_eligible(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        sorcery = _make_sorcery("Ponder", owner=p1)
        assert lorehold.is_miracle_eligible(sorcery) is True

    def test_creature_is_not_miracle_eligible(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        creature = _make_creature("Grizzly Bears", owner=p1)
        assert lorehold.is_miracle_eligible(creature) is False

    def test_non_spell_card_types_not_eligible(self) -> None:
        """Enchantments, artifacts, lands should not be miracle eligible."""
        from engine.card import Enchantment, Artifact, Land
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        enchantment = Enchantment(owner=p1, name="TestEnchant")
        artifact = Artifact(owner=p1, name="TestArtifact")

        assert lorehold.is_miracle_eligible(enchantment) is False
        assert lorehold.is_miracle_eligible(artifact) is False

    def test_miracle_eligible_checks_card_types_not_class(self) -> None:
        """A CardImpl with INSTANT card_type should be eligible, even without Instant base."""
        from engine.card import CardImpl
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        # Manually assign card type.
        raw_instant = CardImpl(name="RawInstant", owner=p1)
        raw_instant.card_types = {CardType.INSTANT}
        assert lorehold.is_miracle_eligible(raw_instant) is True

        raw_sorcery = CardImpl(name="RawSorcery", owner=p1)
        raw_sorcery.card_types = {CardType.SORCERY}
        assert lorehold.is_miracle_eligible(raw_sorcery) is True

        raw_creature = CardImpl(name="RawCreature", owner=p1)
        raw_creature.card_types = {CardType.CREATURE}
        assert lorehold.is_miracle_eligible(raw_creature) is False
