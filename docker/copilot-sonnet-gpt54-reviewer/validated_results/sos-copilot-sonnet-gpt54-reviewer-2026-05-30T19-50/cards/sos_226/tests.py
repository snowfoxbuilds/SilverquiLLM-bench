"""Tests for Silverquill, the Disputant (SOS #226).

Covers:
- Card attributes (4/4, Flying, Vigilance, Legendary, Elder Dragon)
- Casualty trigger fires for instant/sorcery cast by controller
- Casualty with valid creature (power >= 1): creature sacrificed, copy on stack
- Casualty with invalid creature (power 0): not in valid targets list
- Casualty is optional: declining does not copy the spell
- No valid casualty targets: no offer made
- Doesn't apply to non-instant/sorcery spells
- Doesn't apply to opponent's spells
- Copy can have new targets
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant, _get_valid_casualty_creatures
from engine.card import Creature, Instant, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.stack import StackObject, copy_spell
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _put_on_battlefield(game: Any, player_index: int, card: Any) -> None:
    """Put *card* onto the battlefield for *player_index*, registering triggers."""
    player = game.players[player_index]
    card.owner = player
    card.controller = player
    game.get_battlefield(player).add(card)
    if hasattr(card, "register_triggers"):
        card.register_triggers(game)
    if hasattr(card, "register_replacement_effects"):
        card.register_replacement_effects(game)


def _make_instant(name: str = "Test Instant") -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse("{1}{U}"))


def _make_sorcery(name: str = "Test Sorcery") -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse("{1}{R}"))


def _make_creature(name: str = "Test Bear", power: int = 2, toughness: int = 2) -> Creature:
    return Creature(
        name=name,
        base_power=power,
        base_toughness=toughness,
    )


def _fire_spell_cast_event(
    game: Any, player: Any, card: Any, stack_obj: StackObject
) -> None:
    """Fire SpellCastTriggeredEvent to simulate a spell being cast."""
    game.trigger_manager.fire_event(
        game,
        SpellCastTriggeredEvent(spell=stack_obj, player=player, card=card, controller=player),
    )


def _resolve_stack(game: Any) -> None:
    """Resolve all items on the stack."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


def _make_stack_obj(card: Any, player: Any) -> StackObject:
    return StackObject(source=card, controller=player, targets=[])


# ---------------------------------------------------------------------------
# Card attribute tests
# ---------------------------------------------------------------------------

class TestSilverquillAttributes:
    """Static card data must match the sos_226 spec."""

    def test_name(self) -> None:
        card = SilverquillTheDisputant()
        assert card.name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        card = SilverquillTheDisputant()
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_power(self) -> None:
        card = SilverquillTheDisputant()
        assert card.base_power == 4
        assert card.power == 4

    def test_toughness(self) -> None:
        card = SilverquillTheDisputant()
        assert card.base_toughness == 4
        assert card.toughness == 4

    def test_is_creature(self) -> None:
        card = SilverquillTheDisputant()
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_is_legendary(self) -> None:
        card = SilverquillTheDisputant()
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes_elder_dragon(self) -> None:
        card = SilverquillTheDisputant()
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_flying(self) -> None:
        card = SilverquillTheDisputant()
        assert Keyword.FLYING & card.keywords

    def test_vigilance(self) -> None:
        card = SilverquillTheDisputant()
        assert Keyword.VIGILANCE & card.keywords

    def test_rules_text_contains_casualty(self) -> None:
        card = SilverquillTheDisputant()
        assert "casualty" in card.rules_text.lower()


# ---------------------------------------------------------------------------
# _get_valid_casualty_creatures helper
# ---------------------------------------------------------------------------

class TestGetValidCasualtyCreatures:

    def test_returns_creatures_with_power_ge_1(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = _make_creature("Bear", power=2)
        set_board_state(game, 0, battlefield=[bear])
        result = _get_valid_casualty_creatures(game, p1, min_power=1)
        assert bear in result

    def test_excludes_power_0_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        zero = _make_creature("Mite", power=0)
        set_board_state(game, 0, battlefield=[zero])
        result = _get_valid_casualty_creatures(game, p1, min_power=1)
        assert zero not in result

    def test_empty_when_no_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        result = _get_valid_casualty_creatures(game, p1, min_power=1)
        assert result == []

    def test_includes_exactly_power_1(self) -> None:
        game = create_game()
        p1 = game.players[0]
        one = _make_creature("One", power=1)
        set_board_state(game, 0, battlefield=[one])
        result = _get_valid_casualty_creatures(game, p1, min_power=1)
        assert one in result


# ---------------------------------------------------------------------------
# Casualty trigger: fires for instant/sorcery by controller
# ---------------------------------------------------------------------------

class TestCasualtyTriggerFires:

    def test_trigger_fires_for_instant_by_controller(self) -> None:
        """Casting an instant by controller should trigger casualty."""
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        _put_on_battlefield(game, 0, silverquill)

        instant = _make_instant()
        instant.owner = p1
        instant.controller = p1
        so = _make_stack_obj(instant, p1)
        game.stack.push(so)

        bear = _make_creature()
        set_board_state(game, 0, battlefield=[silverquill, bear])

        # Script: use casualty=True, choose bear, no new targets
        p1._script.extend([True, bear, False])

        stack_before = len(game.stack._items)
        _fire_spell_cast_event(game, p1, instant, so)

        # Resolve the trigger StackObject
        if len(game.stack._items) > stack_before:
            trigger_obj = game.stack.pop()
            trigger_obj.on_resolve(game)

        # Spell + copy should be on stack; bear sacrificed
        assert so in game.stack._items  # original still present
        graveyard = game.get_graveyard(p1)
        gy_objects = graveyard.get_all()
        assert bear in gy_objects

    def test_trigger_fires_for_sorcery_by_controller(self) -> None:
        """Casting a sorcery by controller should trigger casualty."""
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        _put_on_battlefield(game, 0, silverquill)

        sorcery = _make_sorcery()
        sorcery.owner = p1
        sorcery.controller = p1
        so = _make_stack_obj(sorcery, p1)
        game.stack.push(so)

        bear = _make_creature()
        set_board_state(game, 0, battlefield=[silverquill, bear])

        p1._script.extend([True, bear, False])

        _fire_spell_cast_event(game, p1, sorcery, so)
        if not game.stack.is_empty():
            top = game.stack.peek()
            if top is not so:
                top_obj = game.stack.pop()
                top_obj.on_resolve(game)

        assert game.get_graveyard(p1).contains(bear)

    def test_trigger_does_not_fire_for_opponent_instant(self) -> None:
        """Casualty should not apply to spells cast by the opponent."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        _put_on_battlefield(game, 0, silverquill)

        instant = _make_instant()
        instant.owner = p2
        instant.controller = p2
        so = _make_stack_obj(instant, p2)
        game.stack.push(so)

        stack_count_before = len(game.stack._items)
        # Fire event for p2 (opponent) — no trigger should fire
        _fire_spell_cast_event(game, p2, instant, so)

        # Stack should be the same size (no trigger pushed on top)
        assert len(game.stack._items) == stack_count_before

    def test_trigger_does_not_fire_for_creature_spell(self) -> None:
        """Casualty does not apply to non-instant/sorcery spells."""
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        _put_on_battlefield(game, 0, silverquill)

        # Creature spell on the stack
        creature_spell = _make_creature("Creature Spell", power=3)
        creature_spell.owner = p1
        creature_spell.controller = p1
        so = _make_stack_obj(creature_spell, p1)
        game.stack.push(so)

        stack_count_before = len(game.stack._items)
        _fire_spell_cast_event(game, p1, creature_spell, so)

        assert len(game.stack._items) == stack_count_before


# ---------------------------------------------------------------------------
# Casualty mechanic: sacrifice and copy
# ---------------------------------------------------------------------------

class TestCasualtyMechanic:

    def test_sacrifice_valid_creature_and_copy_on_stack(self) -> None:
        """When casualty is used, creature is sacrificed and copy is on stack."""
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        bear = _make_creature("Bear", power=2)
        set_board_state(game, 0, battlefield=[silverquill, bear])
        silverquill.register_triggers(game)  # Re-register after set_board_state

        instant = _make_instant()
        instant.owner = p1
        instant.controller = p1
        so = _make_stack_obj(instant, p1)
        game.stack.push(so)

        # Script: yes to casualty, choose bear, no to new targets
        p1._script.extend([True, bear, False])

        _fire_spell_cast_event(game, p1, instant, so)
        # Resolve the trigger
        _resolve_stack_top(game)

        # Bear should be in graveyard
        assert game.get_graveyard(p1).contains(bear)
        # Bear should not be on battlefield
        assert not game.get_battlefield(p1).contains(bear)
        # Original spell should still be on stack
        assert so in game.stack._items
        # A copy should also be on stack (stack has >= 2 items: original + copy)
        assert len(game.stack._items) >= 2

    def test_casualty_declined_no_sacrifice_no_copy(self) -> None:
        """Declining casualty means no sacrifice and no copy."""
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        bear = _make_creature("Bear", power=2)
        set_board_state(game, 0, battlefield=[silverquill, bear])
        silverquill.register_triggers(game)

        instant = _make_instant()
        instant.owner = p1
        instant.controller = p1
        so = _make_stack_obj(instant, p1)
        game.stack.push(so)

        # Script: no to casualty
        p1._script.append(False)

        _fire_spell_cast_event(game, p1, instant, so)
        _resolve_stack_top(game)

        # Bear should still be on battlefield
        assert game.get_battlefield(p1).contains(bear)
        # Only original spell on stack (no copy)
        assert len(game.stack._items) == 1
        assert so in game.stack._items

    def test_power_0_creature_not_valid_for_casualty(self) -> None:
        """A creature with power 0 is not in the valid casualty targets list."""
        game = create_game()
        p1 = game.players[0]
        zero_power = _make_creature("Mite", power=0)
        set_board_state(game, 0, battlefield=[zero_power])

        result = _get_valid_casualty_creatures(game, p1, min_power=1)
        assert zero_power not in result
        assert len(result) == 0

    def test_no_valid_creatures_skips_casualty_offer(self) -> None:
        """When no valid sacrifice targets exist, no offer is made."""
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        # Only Silverquill on battlefield — if controller could sacrifice it but
        # let's put nothing else there. Actually Silverquill has power 4 but
        # the controller would have to sacrifice it. For this test, use an
        # empty battlefield (besides Silverquill which just needs no valid ones).
        zero = _make_creature("Mite", power=0)
        set_board_state(game, 0, battlefield=[silverquill, zero])
        silverquill.register_triggers(game)

        instant = _make_instant()
        instant.owner = p1
        instant.controller = p1
        so = _make_stack_obj(instant, p1)
        game.stack.push(so)

        # No scripted choices needed — effect should return early
        stack_before = len(game.stack._items)
        _fire_spell_cast_event(game, p1, instant, so)
        _resolve_stack_top(game)

        # No copy pushed
        assert len(game.stack._items) == stack_before

    def test_copy_has_same_card_type(self) -> None:
        """The copy on the stack has the same card type as the original."""
        game = create_game()
        p1 = game.players[0]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        bear = _make_creature("Bear", power=2)
        set_board_state(game, 0, battlefield=[silverquill, bear])
        silverquill.register_triggers(game)

        instant = _make_instant("Lightning Bolt")
        instant.owner = p1
        instant.controller = p1
        so = _make_stack_obj(instant, p1)
        game.stack.push(so)

        p1._script.extend([True, bear, False])
        _fire_spell_cast_event(game, p1, instant, so)
        _resolve_stack_top(game)

        # Find the copy (should be on top, original below)
        items = game.stack._items
        assert len(items) >= 2
        copy_obj = items[-1]  # top of stack
        copy_card = copy_obj.source
        assert CardType.INSTANT in getattr(copy_card, "card_types", set())

    def test_casualty_with_new_targets(self) -> None:
        """When controller chooses new targets, copy gets new targets."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        bear = _make_creature("Bear", power=2)
        set_board_state(game, 0, battlefield=[silverquill, bear])
        silverquill.register_triggers(game)

        instant = _make_instant()
        instant.owner = p1
        instant.controller = p1
        so = StackObject(source=instant, controller=p1, targets=[p2])
        game.stack.push(so)

        # Script: yes casualty, choose bear, yes new targets, choose p1
        p1._script.extend([True, bear, True, p1])
        _fire_spell_cast_event(game, p1, instant, so)
        _resolve_stack_top(game)

        assert game.get_graveyard(p1).contains(bear)
        items = game.stack._items
        assert len(items) >= 2
        # Copy should be on stack
        copy_obj = items[-1]
        assert copy_obj is not so


# ---------------------------------------------------------------------------
# Engine integration: casting.py fires SpellCastTriggeredEvent
# ---------------------------------------------------------------------------

class TestEngineCastingIntegration:
    """Verify that cast_spell in casting.py fires SpellCastTriggeredEvent."""

    def test_cast_spell_fires_spell_cast_event(self) -> None:
        """cast_spell should fire SpellCastTriggeredEvent after pushing to stack."""
        from engine.casting import cast_spell as engine_cast_spell

        game = create_game()
        p1 = game.players[0]

        events_received: list[SpellCastTriggeredEvent] = []

        # Register a listener that captures the event
        from engine.triggers import TriggerRegistration
        dummy_source = object()

        def _cond(g: Any, event: Any) -> bool:
            events_received.append(event)
            return False  # don't actually push a trigger

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_cond,
                effect=lambda g: None,
                source=dummy_source,
                controller=p1,
            )
        )

        instant = _make_instant()
        set_board_state(
            game, 0,
            hand=[instant],
            mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1},
        )
        from engine.types import Phase
        game.phase = Phase.PRECOMBAT_MAIN
        game.active_player_index = 0

        engine_cast_spell(game, p1, instant)

        assert len(events_received) >= 1
        assert any(isinstance(e, SpellCastTriggeredEvent) for e in events_received)


# ---------------------------------------------------------------------------
# Local helper
# ---------------------------------------------------------------------------

def _resolve_stack_top(game: Any) -> None:
    """Resolve only the top item of the stack, if any (non-original items)."""
    if game.stack.is_empty():
        return
    top = game.stack._items[-1]
    # Only pop trigger objects (not the original spell StackObject).
    # In test context, top after fire_event is the trigger.
    obj = game.stack.pop()
    obj.on_resolve(game)
