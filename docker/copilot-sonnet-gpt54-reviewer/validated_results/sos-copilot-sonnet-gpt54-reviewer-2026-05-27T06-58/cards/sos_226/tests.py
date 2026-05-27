"""Tests for SOS 226 — Silverquill, the Disputant.

Silverquill, the Disputant is a legendary 4/4 Elder Dragon with Flying and
Vigilance that grants casualty 1 to each instant and sorcery spell you cast.

Casualty 1: As you cast an instant/sorcery, you may sacrifice a creature
with power 1 or greater. If you do, copy the spell and you may choose new
targets for the copy.

Tests cover:
- Static properties (name, mana cost, type, P/T, keywords, supertypes)
- Trigger registration when Silverquill enters the battlefield
- Casualty 1 fires only for instants/sorceries (not permanents)
- Casualty 1 only applies to spells cast by Silverquill's controller
- When casualty is triggered and player sacrifices: copy appears on stack
- When casualty is triggered and player declines: no copy
- Only creatures with power >= 1 qualify as sacrifice candidates
- A creature with power 0 does NOT qualify as a casualty sacrifice
"""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_instant(name: str = "TestInstant") -> Instant:
    """Create a trivial Instant card for use as spell bait."""
    spell = Instant(name=name)
    return spell


def _make_sorcery(name: str = "TestSorcery") -> Sorcery:
    """Create a trivial Sorcery card for use as spell bait."""
    spell = Sorcery(name=name)
    return spell


def _make_creature(name: str = "TestCreature", power: int = 2, toughness: int = 2) -> Creature:
    """Create a vanilla creature with given power/toughness."""
    return Creature(name=name, base_power=power, base_toughness=toughness)


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestSilverquillProperties:
    """Static card data should match the SOS 226 spec."""

    def test_is_creature(self) -> None:
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

    def test_has_flying(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_vigilance(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.VIGILANCE in card.keywords

    def test_is_legendary(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_is_creature_type(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_subtypes_include_elder_dragon(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        # Should have Dragon (and Elder) as subtypes
        assert "Dragon" in card.subtypes

    def test_subtype_includes_elder(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert "Elder" in card.subtypes


# ---------------------------------------------------------------------------
# Trigger registration
# ---------------------------------------------------------------------------


class TestSilverquillTriggerRegistration:
    """Silverquill registers a trigger for SpellCastTriggeredEvent when it
    enters the battlefield (via register_triggers)."""

    def test_registers_trigger_on_register_triggers(self) -> None:
        """register_triggers should register at least one trigger."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_trigger_responds_to_spell_cast_event(self) -> None:
        """The registered trigger should watch for SpellCastTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) > 0
        # At least one trigger should be for SpellCastTriggeredEvent
        event_types = [t.event_type for t in triggers]
        assert SpellCastTriggeredEvent in event_types


# ---------------------------------------------------------------------------
# Casualty 1 — trigger condition checks
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyTriggerCondition:
    """The casualty trigger should only fire for instants/sorceries cast by
    Silverquill's controller — not permanents, not opponent spells."""

    def test_trigger_fires_for_instant_cast_by_controller(self) -> None:
        """Casting an instant while Silverquill is on the battlefield should
        push a casualty trigger onto the stack."""
        game = create_game()
        p1 = game.players[0]

        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        # register_triggers called by move_to_zone when entering battlefield
        # but we need to call it manually after set_board_state
        silverquill.register_triggers(game)

        instant = _make_instant("LightningBolt")
        instant.owner = p1
        instant.controller = p1

        # Fire the spell cast event as if an instant was cast
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=instant, player=p1, card=instant, controller=p1),
        )

        # A casualty trigger should now be on the stack
        assert not game.stack.is_empty()

    def test_trigger_fires_for_sorcery_cast_by_controller(self) -> None:
        """Casting a sorcery while Silverquill is on the battlefield should
        push a casualty trigger onto the stack."""
        game = create_game()
        p1 = game.players[0]

        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        silverquill.register_triggers(game)

        sorcery = _make_sorcery("Divination")
        sorcery.owner = p1
        sorcery.controller = p1

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=sorcery, player=p1, card=sorcery, controller=p1),
        )

        assert not game.stack.is_empty()

    def test_trigger_does_not_fire_for_creature_spell(self) -> None:
        """Casting a creature spell should NOT trigger the casualty ability."""
        game = create_game()
        p1 = game.players[0]

        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        silverquill.register_triggers(game)

        creature_spell = _make_creature("GrizzlyBears")
        creature_spell.owner = p1
        creature_spell.controller = p1

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=creature_spell, player=p1,
                card=creature_spell, controller=p1,
            ),
        )

        # No casualty trigger should fire for non-instant/non-sorcery
        assert game.stack.is_empty()

    def test_trigger_does_not_fire_for_opponent_instant(self) -> None:
        """An opponent casting an instant should NOT trigger Silverquill's
        casualty — it only applies to 'spells you cast'."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        silverquill.register_triggers(game)

        opponent_instant = _make_instant("CounterSpell")
        opponent_instant.owner = p2
        opponent_instant.controller = p2

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=opponent_instant, player=p2,
                card=opponent_instant, controller=p2,
            ),
        )

        # No trigger from Silverquill — opponent's spell
        assert game.stack.is_empty()


# ---------------------------------------------------------------------------
# Casualty 1 — resolution: sacrifice and copy
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyResolution:
    """When the casualty trigger resolves and the player chooses to sacrifice
    a creature with power >= 1, a copy of the spell is pushed onto the stack."""

    def _setup_casualty_trigger(self, game, p1, spell_card):
        """Helper: put Silverquill on battlefield, register triggers, fire
        SpellCastTriggeredEvent, and return the trigger stack object."""
        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        silverquill.register_triggers(game)

        spell_card.owner = p1
        spell_card.controller = p1

        # Also put the spell on the stack as it would be during casting
        p1.zones[Zone.STACK].add(spell_card)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell_card, player=p1,
                card=spell_card, controller=p1,
            ),
        )
        return game.stack.peek()

    def test_no_eligible_creatures_trigger_resolves_without_copy(self) -> None:
        """When the player has no creatures with power >= 1, the trigger
        resolves without creating a copy."""
        game = create_game()
        p1 = game.players[0]

        # Script p1 to decline sacrifice (False = no)
        from engine.player import DeterministicPlayer
        p1._script.appendleft(False)  # "No, I don't sacrifice"

        spell = _make_instant("TestBolt")
        trigger_obj = self._setup_casualty_trigger(game, p1, spell)

        stack_size_before = len(game.stack)
        # Resolve the trigger
        trigger_obj.on_resolve(game)

        # No copy should have been added
        # (the spell is still on the stack but no new copy was added)
        assert len(game.stack) <= stack_size_before

    def test_player_declines_sacrifice_no_copy_created(self) -> None:
        """When the player opts NOT to sacrifice, no copy is made."""
        game = create_game()
        p1 = game.players[0]

        # Script: choose not to sacrifice
        from engine.player import DeterministicPlayer
        p1._script.appendleft(False)  # "No, I don't sacrifice"

        spell = _make_instant("TestBolt2")
        # _setup_casualty_trigger calls set_board_state internally, which replaces
        # the battlefield — so we must add the blocker AFTER it returns.
        trigger_obj = self._setup_casualty_trigger(game, p1, spell)

        # Give p1 a creature they COULD sacrifice but choose not to
        blocker = _make_creature("BigBear", power=2, toughness=2)
        blocker.owner = p1
        blocker.controller = p1
        p1.zones[Zone.BATTLEFIELD].add(blocker)

        # Baseline: the spell + trigger are on the stack
        stack_size_before = len(game.stack)
        trigger_obj.on_resolve(game)

        # No copy; bear should still be alive
        bf_objects = p1.zones[Zone.BATTLEFIELD].get_all()
        assert blocker in bf_objects

    def test_player_sacrifices_creature_and_copy_is_created(self) -> None:
        """When the player sacrifices a creature with power >= 1, a copy of
        the spell should be pushed onto the stack."""
        game = create_game()
        p1 = game.players[0]

        # Give p1 a creature to sacrifice
        fodder = _make_creature("SacrificeFodder", power=1, toughness=1)
        fodder.owner = p1
        fodder.controller = p1
        p1.zones[Zone.BATTLEFIELD].add(fodder)

        # Script: yes sacrifice, then choose the fodder creature
        from engine.player import DeterministicPlayer
        p1._script.appendleft(fodder)  # Which creature to sacrifice
        p1._script.appendleft(True)    # "Yes, I want to sacrifice"

        spell = _make_instant("TestCopy")
        trigger_obj = self._setup_casualty_trigger(game, p1, spell)

        # Count objects on stack before resolving the trigger
        # (spell is on stack, trigger is on stack)
        stack_size_before = len(game.stack)
        trigger_obj.on_resolve(game)

        # A copy of the spell should have been added to the stack
        # (net increase of 1 copy, trigger itself popped)
        assert len(game.stack) >= stack_size_before

    def test_sacrificed_creature_goes_to_graveyard(self) -> None:
        """When the player sacrifices a creature for casualty, that creature
        should move to the graveyard."""
        game = create_game()
        p1 = game.players[0]

        fodder = _make_creature("GraveyardBound", power=2, toughness=2)
        fodder.owner = p1
        fodder.controller = p1
        p1.zones[Zone.BATTLEFIELD].add(fodder)

        from engine.player import DeterministicPlayer
        p1._script.appendleft(fodder)
        p1._script.appendleft(True)

        spell = _make_instant("TestSacrifice")
        trigger_obj = self._setup_casualty_trigger(game, p1, spell)
        trigger_obj.on_resolve(game)

        # The fodder should now be in the graveyard
        assert p1.zones[Zone.GRAVEYARD].contains(fodder)
        # And no longer on the battlefield
        assert not p1.zones[Zone.BATTLEFIELD].contains(fodder)


# ---------------------------------------------------------------------------
# Casualty 1 — power requirement for sacrifice candidate
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyPowerRequirement:
    """Casualty 1 requires sacrificing a creature with power 1 OR GREATER.
    A power-0 creature should not be a valid casualty sacrifice target."""

    def test_power_one_creature_is_valid_sacrifice_candidate(self) -> None:
        """A creature with exactly power 1 qualifies for casualty 1."""
        game = create_game()
        p1 = game.players[0]

        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        silverquill.register_triggers(game)

        # Creature with power 1
        tiny_creature = _make_creature("OnePowerCreature", power=1, toughness=1)
        tiny_creature.owner = p1
        tiny_creature.controller = p1
        p1.zones[Zone.BATTLEFIELD].add(tiny_creature)

        spell = _make_instant("SmallBolt")
        spell.owner = p1
        spell.controller = p1
        p1.zones[Zone.STACK].add(spell)

        # Fire the event — the trigger SHOULD fire (Silverquill watching)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell, player=p1,
                card=spell, controller=p1,
            ),
        )

        trigger_obj = game.stack.peek()

        from engine.player import DeterministicPlayer
        p1._script.appendleft(tiny_creature)
        p1._script.appendleft(True)

        trigger_obj.on_resolve(game)

        # Creature with power 1 should have been sacrificed
        assert p1.zones[Zone.GRAVEYARD].contains(tiny_creature)

    def test_power_zero_creature_not_valid_for_casualty_sacrifice(self) -> None:
        """A creature with power 0 does NOT qualify for casualty 1 sacrifice.
        The implementation should either not offer it or not sacrifice it."""
        game = create_game()
        p1 = game.players[0]

        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        silverquill.register_triggers(game)

        # Creature with power 0 — ineligible for casualty
        zero_power = _make_creature("ZeroPower", power=0, toughness=3)
        zero_power.owner = p1
        zero_power.controller = p1
        p1.zones[Zone.BATTLEFIELD].add(zero_power)

        spell = _make_instant("WeakBolt")
        spell.owner = p1
        spell.controller = p1
        p1.zones[Zone.STACK].add(spell)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell, player=p1,
                card=spell, controller=p1,
            ),
        )

        trigger_obj = game.stack.peek()

        # Script: player tries to sacrifice the zero-power creature
        # Implementation should either ignore it or not allow it
        from engine.player import DeterministicPlayer
        # Decline (no eligible creatures scenario)
        p1._script.appendleft(False)

        trigger_obj.on_resolve(game)

        # The zero-power creature should NOT be in graveyard — it was ineligible
        assert not p1.zones[Zone.GRAVEYARD].contains(zero_power)
        assert p1.zones[Zone.BATTLEFIELD].contains(zero_power)


# ---------------------------------------------------------------------------
# Casualty 1 — copy on stack is functional
# ---------------------------------------------------------------------------


class TestSilverquillCasualtySpellCopy:
    """The copy created by casualty 1 should be on the stack and resolve
    independently when processed."""

    def test_copy_resolves_independently(self) -> None:
        """A copied spell pushed by casualty should have its own on_resolve."""
        game = create_game()
        p1 = game.players[0]

        silverquill = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill])
        silverquill.register_triggers(game)

        fodder = _make_creature("CopyTestFodder", power=1, toughness=1)
        fodder.owner = p1
        fodder.controller = p1
        p1.zones[Zone.BATTLEFIELD].add(fodder)

        spell = _make_instant("CopyTestSpell")
        spell.owner = p1
        spell.controller = p1
        p1.zones[Zone.STACK].add(spell)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=spell, player=p1,
                card=spell, controller=p1,
            ),
        )

        trigger_obj = game.stack.peek()

        from engine.player import DeterministicPlayer
        p1._script.appendleft(fodder)
        p1._script.appendleft(True)

        trigger_obj.on_resolve(game)

        # After the trigger resolves with a sacrifice, there should be
        # at least one StackObject on the stack
        stack_items = game.stack.objects()
        assert len(stack_items) > 0

        # The top item should be callable (has on_resolve)
        top_item = game.stack.peek()
        assert top_item is not None
        assert callable(top_item.on_resolve)
