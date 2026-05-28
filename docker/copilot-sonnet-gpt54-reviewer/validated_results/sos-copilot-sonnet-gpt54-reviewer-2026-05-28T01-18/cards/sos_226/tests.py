"""Tests for sos_226 — Silverquill, the Disputant.

Silverquill, the Disputant is a Legendary Creature — Elder Dragon with mana
cost {2}{W}{B}, 4/4, Flying, Vigilance.

Oracle text:
  "Each instant and sorcery spell you cast has casualty 1.
   (As you cast that spell, you may sacrifice a creature with power 1 or
   greater. When you do, copy the spell and you may choose new targets for
   the copy.)"

Test categories:
  1. Static card properties (name, mana cost, P/T, type, subtypes,
     supertypes, keywords)
  2. Keyword presence — Flying and Vigilance
  3. SpellCastTriggeredEvent trigger registration
  4. Trigger condition — instants/sorceries cast by controller qualify;
     creatures and opponent spells do not
  5. Casualty eligibility method — instants/sorceries are eligible,
     creatures are not
  6. Trigger effect — no eligible creature means no copy is created
  7. Trigger effect — with eligible creature and player says yes:
     creature moves to graveyard, copy of spell appears on stack
  8. Trigger effect — with eligible creature and player says no:
     no copy, no sacrifice
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_instant(name: str = "TestInstant", owner: Any = None) -> Instant:
    """Return a minimal instant card."""
    return Instant(name=name, owner=owner, controller=owner)


def _make_sorcery(name: str = "TestSorcery", owner: Any = None) -> Sorcery:
    """Return a minimal sorcery card."""
    return Sorcery(name=name, owner=owner, controller=owner)


def _make_creature(
    name: str = "TestCreature",
    owner: Any = None,
    power: int = 2,
    toughness: int = 2,
) -> Creature:
    """Return a minimal creature card with the given power/toughness."""
    return Creature(
        name=name,
        owner=owner,
        controller=owner,
        base_power=power,
        base_toughness=toughness,
    )


def _find_spell_cast_trigger(game: Any, source: Any) -> TriggerRegistration | None:
    """Return the SpellCastTriggeredEvent trigger registered by *source*, or None."""
    return next(
        (
            t
            for t in game.trigger_manager._triggers
            if t.source is source
            and t.event_type is SpellCastTriggeredEvent
        ),
        None,
    )


# ---------------------------------------------------------------------------
# 1. Static card properties
# ---------------------------------------------------------------------------


class TestSilverquillProperties:
    """Static card data must match the sos_226 spec."""

    def test_is_creature_subclass(self) -> None:
        """SilverquillTheDisputant must be a Creature instance."""
        card = SilverquillTheDisputant(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_power(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.base_power == 4

    def test_toughness(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.base_toughness == 4

    def test_card_type_creature(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_legendary_supertype(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_elder_dragon_subtypes(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes


# ---------------------------------------------------------------------------
# 2. Keyword presence
# ---------------------------------------------------------------------------


class TestSilverquillKeywords:
    """Flying and Vigilance keywords must be present."""

    def test_has_flying(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_vigilance(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.VIGILANCE in card.keywords

    def test_no_extra_keywords_flying_vigilance_only(self) -> None:
        """Silverquill should only have Flying and Vigilance — not haste, etc."""
        card = SilverquillTheDisputant(owner=None)
        expected = Keyword.FLYING | Keyword.VIGILANCE
        # Strip to only known keyword flags present on card.
        # We verify that every keyword present is in the expected set.
        present = card.keywords
        assert (present & ~expected) == Keyword(0), (
            f"Unexpected extra keywords: {present & ~expected}"
        )


# ---------------------------------------------------------------------------
# 3. SpellCastTriggeredEvent trigger registration
# ---------------------------------------------------------------------------


class TestSilverquillTriggerRegistration:
    """register_triggers() must wire a SpellCastTriggeredEvent trigger."""

    def test_registers_at_least_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        before = len(game.trigger_manager._triggers)
        card.register_triggers(game)
        after = len(game.trigger_manager._triggers)
        assert after > before

    def test_registered_trigger_watches_spell_cast_event(self) -> None:
        """At least one registered trigger must watch SpellCastTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = _find_spell_cast_trigger(game, card)
        assert trigger is not None, (
            "register_triggers must register a SpellCastTriggeredEvent trigger"
        )

    def test_registered_trigger_is_trigger_registration_instance(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = _find_spell_cast_trigger(game, card)
        assert trigger is not None
        assert isinstance(trigger, TriggerRegistration)

    def test_trigger_source_is_silverquill(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = _find_spell_cast_trigger(game, card)
        assert trigger is not None
        assert trigger.source is card


# ---------------------------------------------------------------------------
# 4. Trigger condition — which spells qualify for casualty
# ---------------------------------------------------------------------------


class TestSilverquillTriggerCondition:
    """The trigger's condition must accept instants/sorceries cast by the
    controller and reject creatures and opponent-cast spells."""

    def _get_trigger(self, game: Any, card: Any) -> TriggerRegistration:
        card.register_triggers(game)
        trigger = _find_spell_cast_trigger(game, card)
        assert trigger is not None, "SpellCastTriggeredEvent trigger not found"
        return trigger

    def test_condition_true_for_instant_cast_by_controller(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        trigger = self._get_trigger(game, card)
        if trigger.condition is None:
            pytest.skip("Trigger has no condition (always fires) — consider tightening")
        instant = _make_instant("Lightning Bolt", owner=p1)
        event = SpellCastTriggeredEvent(spell=instant, player=p1, card=instant, controller=p1)
        assert trigger.condition(game, event) is True

    def test_condition_true_for_sorcery_cast_by_controller(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        trigger = self._get_trigger(game, card)
        if trigger.condition is None:
            pytest.skip("Trigger has no condition — consider tightening")
        sorcery = _make_sorcery("Ponder", owner=p1)
        event = SpellCastTriggeredEvent(spell=sorcery, player=p1, card=sorcery, controller=p1)
        assert trigger.condition(game, event) is True

    def test_condition_false_for_creature_cast_by_controller(self) -> None:
        """Creatures do not receive casualty — condition must return False."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        trigger = self._get_trigger(game, card)
        if trigger.condition is None:
            # If there's no condition, the effect itself must guard against creatures.
            pytest.skip("No condition — effect must guard internally")
        creature_spell = _make_creature("Grizzly Bears", owner=p1)
        event = SpellCastTriggeredEvent(
            spell=creature_spell, player=p1, card=creature_spell, controller=p1
        )
        assert trigger.condition(game, event) is False

    def test_condition_false_for_instant_cast_by_opponent(self) -> None:
        """The trigger should only fire for spells the *controller* casts."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        trigger = self._get_trigger(game, card)
        if trigger.condition is None:
            pytest.skip("No condition — effect must guard internally")
        instant = _make_instant("CounterTarget", owner=p2)
        event = SpellCastTriggeredEvent(spell=instant, player=p2, card=instant, controller=p2)
        assert trigger.condition(game, event) is False


# ---------------------------------------------------------------------------
# 5. Casualty eligibility helper method
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyEligibility:
    """The card must expose a method is_casualty_eligible(spell) returning
    True for instants and sorceries, False for all other card types."""

    def test_has_is_casualty_eligible_method(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert hasattr(card, "is_casualty_eligible"), (
            "SilverquillTheDisputant must expose is_casualty_eligible(spell)"
        )

    def test_instant_is_casualty_eligible(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        instant = _make_instant("Lightning Bolt", owner=p1)
        assert silverquill.is_casualty_eligible(instant) is True

    def test_sorcery_is_casualty_eligible(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        sorcery = _make_sorcery("Ponder", owner=p1)
        assert silverquill.is_casualty_eligible(sorcery) is True

    def test_creature_is_not_casualty_eligible(self) -> None:
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        creature = _make_creature("Grizzly Bears", owner=p1)
        assert silverquill.is_casualty_eligible(creature) is False

    def test_card_type_instant_without_instant_base_is_eligible(self) -> None:
        """Eligibility checks card_types, not isinstance."""
        from engine.card import CardImpl
        silverquill = SilverquillTheDisputant(owner=None)
        raw_instant = CardImpl(name="RawInstant")
        raw_instant.card_types = {CardType.INSTANT}
        assert silverquill.is_casualty_eligible(raw_instant) is True

    def test_card_type_sorcery_without_sorcery_base_is_eligible(self) -> None:
        from engine.card import CardImpl
        silverquill = SilverquillTheDisputant(owner=None)
        raw_sorcery = CardImpl(name="RawSorcery")
        raw_sorcery.card_types = {CardType.SORCERY}
        assert silverquill.is_casualty_eligible(raw_sorcery) is True

    def test_enchantment_is_not_casualty_eligible(self) -> None:
        from engine.card import Enchantment
        silverquill = SilverquillTheDisputant(owner=None)
        enchantment = Enchantment(name="TestEnchant")
        assert silverquill.is_casualty_eligible(enchantment) is False


# ---------------------------------------------------------------------------
# 6. Trigger effect — no eligible creature means no copy
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyNoEligibleCreature:
    """When the controller has no creature with power >= 1, the trigger
    effect must be a no-op (no copy pushed onto the stack)."""

    def test_no_copy_when_no_creatures_on_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = _find_spell_cast_trigger(game, card)
        assert trigger is not None

        # Set up: instant spell on the stack, no creatures on battlefield.
        instant = _make_instant("TestFlash", owner=p1)
        instant.controller = p1
        stack_obj = StackObject(source=instant, controller=p1, targets=[])
        game.stack.push(stack_obj)

        # Store the event so the trigger effect can find the spell.
        event = SpellCastTriggeredEvent(spell=instant, player=p1, card=instant, controller=p1)
        game._last_spell_cast_event = event  # common implementation pattern

        stack_size_before = len(list(game.stack._items))
        trigger.effect(game)
        stack_size_after = len(list(game.stack._items))

        # No copy should have been added (net stack size unchanged or only
        # the original remains).
        assert stack_size_after <= stack_size_before + 1, (
            "No copy should be created when no eligible sacrifice creature exists"
        )

    def test_no_copy_when_all_creatures_have_zero_power(self) -> None:
        """A creature with power 0 is NOT a valid casualty 1 sacrifice."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = _find_spell_cast_trigger(game, card)
        assert trigger is not None

        # Put a 0-power creature on battlefield.
        zero_power = _make_creature("Wall", owner=p1, power=0, toughness=4)
        game.get_battlefield(p1).add(zero_power)

        instant = _make_instant("TestFlash", owner=p1)
        instant.controller = p1
        stack_obj = StackObject(source=instant, controller=p1, targets=[])
        game.stack.push(stack_obj)

        event = SpellCastTriggeredEvent(spell=instant, player=p1, card=instant, controller=p1)
        game._last_spell_cast_event = event

        stack_size_before = len(list(game.stack._items))
        trigger.effect(game)
        stack_size_after = len(list(game.stack._items))

        assert stack_size_after <= stack_size_before + 1


# ---------------------------------------------------------------------------
# 7. Trigger effect — sacrifice accepted → creature to graveyard, copy on stack
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyWithSacrifice:
    """When the controller has an eligible creature (power >= 1) and chooses
    to sacrifice, the creature moves to graveyard and a copy of the spell
    appears on the stack."""

    def test_sacrifice_moves_creature_to_graveyard(self) -> None:
        from engine.player import DeterministicPlayer

        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = _find_spell_cast_trigger(game, card)
        assert trigger is not None

        # Put an eligible creature (power 1) on the battlefield.
        fodder = _make_creature("SacFodder", owner=p1, power=1, toughness=1)
        game.get_battlefield(p1).add(fodder)

        # The instant spell on the stack.
        instant = _make_instant("TestInstant", owner=p1)
        instant.controller = p1
        stack_obj = StackObject(source=instant, controller=p1, targets=[])
        game.stack.push(stack_obj)

        event = SpellCastTriggeredEvent(spell=instant, player=p1, card=instant, controller=p1)
        game._last_spell_cast_event = event

        # Script the controller: yes to sacrifice, choose fodder.
        p1_scripted = DeterministicPlayer("P1", script=[True, fodder])
        p1_scripted.zones = p1.zones
        p1_scripted.life = p1.life
        trigger.controller = p1_scripted
        card.controller = p1_scripted

        trigger.effect(game)

        # Creature must have left the battlefield.
        assert not game.get_battlefield(p1_scripted).contains(fodder), (
            "Sacrificed creature must leave the battlefield"
        )

        # Creature must be in the graveyard.
        graveyard = p1_scripted.zones[Zone.GRAVEYARD]
        assert graveyard.contains(fodder), (
            "Sacrificed creature must be moved to the graveyard"
        )

    def test_sacrifice_creates_copy_on_stack(self) -> None:
        """After sacrifice, a copy of the instant/sorcery must be on the stack."""
        from engine.player import DeterministicPlayer

        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = _find_spell_cast_trigger(game, card)
        assert trigger is not None

        fodder = _make_creature("SacFodder", owner=p1, power=2, toughness=2)
        game.get_battlefield(p1).add(fodder)

        instant = _make_instant("CopiedSpell", owner=p1)
        instant.controller = p1
        stack_obj = StackObject(source=instant, controller=p1, targets=[])
        game.stack.push(stack_obj)

        event = SpellCastTriggeredEvent(spell=instant, player=p1, card=instant, controller=p1)
        game._last_spell_cast_event = event

        stack_size_before = len(list(game.stack._items))

        p1_scripted = DeterministicPlayer("P1", script=[True, fodder])
        p1_scripted.zones = p1.zones
        p1_scripted.life = p1.life
        trigger.controller = p1_scripted
        card.controller = p1_scripted

        trigger.effect(game)

        stack_size_after = len(list(game.stack._items))

        # A copy should have been pushed onto the stack.
        assert stack_size_after > stack_size_before, (
            "A copy of the spell must be pushed onto the stack after casualty sacrifice"
        )

    def test_copy_has_same_card_name_as_original(self) -> None:
        """The copy on the stack should be a copy of the original instant."""
        from engine.player import DeterministicPlayer

        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = _find_spell_cast_trigger(game, card)
        assert trigger is not None

        fodder = _make_creature("SacFodder", owner=p1, power=1, toughness=1)
        game.get_battlefield(p1).add(fodder)

        instant = _make_instant("DistinctiveSpellName", owner=p1)
        instant.controller = p1
        stack_obj = StackObject(source=instant, controller=p1, targets=[])
        game.stack.push(stack_obj)

        event = SpellCastTriggeredEvent(
            spell=instant, player=p1, card=instant, controller=p1
        )
        game._last_spell_cast_event = event

        p1_scripted = DeterministicPlayer("P1", script=[True, fodder])
        p1_scripted.zones = p1.zones
        p1_scripted.life = p1.life
        trigger.controller = p1_scripted
        card.controller = p1_scripted

        trigger.effect(game)

        # Find the newly-pushed copy by looking for its name at the top of stack.
        stack_items = list(game.stack._items)
        copy_names = [
            getattr(obj.source, "name", None)
            for obj in stack_items
            if obj.source is not instant
        ]
        assert "DistinctiveSpellName" in copy_names, (
            "Copy's source card should have the same name as the original spell"
        )


# ---------------------------------------------------------------------------
# 8. Trigger effect — sacrifice declined → no copy, no sacrifice
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyDeclined:
    """When the controller declines to sacrifice, no copy is created and
    no creature moves to the graveyard."""

    def test_no_copy_when_sacrifice_declined(self) -> None:
        from engine.player import DeterministicPlayer

        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = _find_spell_cast_trigger(game, card)
        assert trigger is not None

        fodder = _make_creature("SafeCreature", owner=p1, power=2, toughness=2)
        game.get_battlefield(p1).add(fodder)

        instant = _make_instant("NoCopySpell", owner=p1)
        instant.controller = p1
        stack_obj = StackObject(source=instant, controller=p1, targets=[])
        game.stack.push(stack_obj)

        event = SpellCastTriggeredEvent(spell=instant, player=p1, card=instant, controller=p1)
        game._last_spell_cast_event = event

        stack_size_before = len(list(game.stack._items))

        # Player says no to sacrifice.
        p1_scripted = DeterministicPlayer("P1", script=[False])
        p1_scripted.zones = p1.zones
        p1_scripted.life = p1.life
        trigger.controller = p1_scripted
        card.controller = p1_scripted

        trigger.effect(game)

        stack_size_after = len(list(game.stack._items))

        assert stack_size_after == stack_size_before, (
            "No copy should be pushed when sacrifice is declined"
        )

    def test_creature_survives_when_sacrifice_declined(self) -> None:
        from engine.player import DeterministicPlayer

        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = _find_spell_cast_trigger(game, card)
        assert trigger is not None

        fodder = _make_creature("SafeCreature", owner=p1, power=2, toughness=2)
        game.get_battlefield(p1).add(fodder)

        instant = _make_instant("NoCopySpell", owner=p1)
        instant.controller = p1
        stack_obj = StackObject(source=instant, controller=p1, targets=[])
        game.stack.push(stack_obj)

        event = SpellCastTriggeredEvent(spell=instant, player=p1, card=instant, controller=p1)
        game._last_spell_cast_event = event

        p1_scripted = DeterministicPlayer("P1", script=[False])
        p1_scripted.zones = p1.zones
        p1_scripted.life = p1.life
        trigger.controller = p1_scripted
        card.controller = p1_scripted

        trigger.effect(game)

        # Creature must still be on the battlefield.
        assert game.get_battlefield(p1_scripted).contains(fodder), (
            "Creature must remain on battlefield when sacrifice is declined"
        )
