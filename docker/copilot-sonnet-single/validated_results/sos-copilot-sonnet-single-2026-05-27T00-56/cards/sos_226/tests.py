"""Tests for sos_226 — Silverquill, the Disputant.

Card spec:
  Mana cost: {2}{W}{B}
  Type: Legendary Creature — Elder Dragon
  P/T: 4/4
  Keywords: Flying, Vigilance
  Oracle text:
    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1. (As you cast that
    spell, you may sacrifice a creature with power 1 or greater. When you do,
    copy the spell and you may choose new targets for the copy.)

Requirements tested:
  1. Static properties: name, mana cost, P/T, creature type, keywords,
     supertype, subtypes (Elder Dragon).
  2. register_triggers() adds at least one SpellCastTriggeredEvent trigger.
  3. Trigger condition fires for instants/sorceries cast by the controller
     while Silverquill is on the battlefield.
  4. Trigger condition does NOT fire for non-instant/sorcery spells.
  5. Trigger condition does NOT fire for spells cast by an opponent.
  6. Trigger condition does NOT fire when Silverquill is not on the battlefield.
  7. Firing SpellCastTriggeredEvent with a matching spell pushes the trigger
     onto the stack.
  8. Casualty effect: no copy when no eligible creatures (power >= 1) exist.
  9. Casualty effect: no copy when all battlefield creatures have power = 0.
  10. Casualty effect: copy created on the stack when eligible creature is
      sacrificed (player says yes, chooses creature with power >= 1).
  11. Eligible sacrifice creature must have power >= 1 (not power 0).
"""

from __future__ import annotations

from engine.card import Creature, Instant, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.stack import StackObject
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    Supertype,
)
from test_utils import create_game, set_board_state

from cards.sos.sos_226.card_impl import SilverquillTheDisputant


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestSilverquillTheDisputantProperties:
    """Static card data should match the sos_226 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(SilverquillTheDisputant(owner=None), Creature)

    def test_name(self) -> None:
        assert SilverquillTheDisputant(owner=None).name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        assert SilverquillTheDisputant(owner=None).mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_base_power(self) -> None:
        assert SilverquillTheDisputant(owner=None).base_power == 4

    def test_base_toughness(self) -> None:
        assert SilverquillTheDisputant(owner=None).base_toughness == 4

    def test_has_flying(self) -> None:
        kw = SilverquillTheDisputant(owner=None).keywords
        assert Keyword.FLYING in kw

    def test_has_vigilance(self) -> None:
        kw = SilverquillTheDisputant(owner=None).keywords
        assert Keyword.VIGILANCE in kw

    def test_is_legendary(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes_include_elder(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert "Elder" in card.subtypes

    def test_subtypes_include_dragon(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert "Dragon" in card.subtypes


# ---------------------------------------------------------------------------
# Trigger registration — SpellCastTriggeredEvent
# ---------------------------------------------------------------------------

class TestSilverquillTriggerRegistration:
    """register_triggers() must add at least one SpellCastTriggeredEvent trigger."""

    def test_register_triggers_adds_at_least_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_trigger_watches_spell_cast_event(self) -> None:
        """The registered trigger must watch SpellCastTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        event_types = [t.event_type for t in triggers]
        assert any(
            t is SpellCastTriggeredEvent or issubclass(SpellCastTriggeredEvent, t)
            for t in event_types
        )


# ---------------------------------------------------------------------------
# Trigger condition — what spells qualify for casualty
# ---------------------------------------------------------------------------

class TestSilverquillTriggerCondition:
    """The trigger condition: instant/sorcery by controller while on battlefield."""

    def _get_spell_cast_trigger(self, game, card):
        """Return the SpellCastTriggeredEvent trigger registered by card."""
        triggers = game.trigger_manager.get_triggers_for_source(card)
        for t in triggers:
            if t.event_type is SpellCastTriggeredEvent or (
                isinstance(t.event_type, type) and issubclass(SpellCastTriggeredEvent, t.event_type)
            ):
                return t
        return None

    def test_condition_true_for_instant_by_controller_on_battlefield(self) -> None:
        """Trigger condition returns True for an instant cast by the controller
        when Silverquill is on the battlefield."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        # Put Silverquill on the battlefield so the on-battlefield check passes.
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        trigger = self._get_spell_cast_trigger(game, card)
        assert trigger is not None

        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=instant, player=p1, controller=p1)
        if trigger.condition is not None:
            assert trigger.condition(game, event) is True

    def test_condition_true_for_sorcery_by_controller_on_battlefield(self) -> None:
        """Trigger condition returns True for a sorcery cast by the controller."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        trigger = self._get_spell_cast_trigger(game, card)
        assert trigger is not None

        sorcery = Sorcery(name="Test Sorcery", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=sorcery, player=p1, controller=p1)
        if trigger.condition is not None:
            assert trigger.condition(game, event) is True

    def test_condition_false_for_creature_spell_by_controller(self) -> None:
        """Trigger condition returns False for a creature spell — not instant/sorcery."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        trigger = self._get_spell_cast_trigger(game, card)
        assert trigger is not None

        creature_spell = Creature(name="Test Creature", owner=p1, controller=p1,
                                  base_power=2, base_toughness=2)
        event = SpellCastTriggeredEvent(spell=creature_spell, player=p1, controller=p1)
        if trigger.condition is not None:
            assert trigger.condition(game, event) is False

    def test_condition_false_for_instant_by_opponent(self) -> None:
        """Trigger condition returns False when the spell is cast by an opponent,
        not the controller of Silverquill."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        trigger = self._get_spell_cast_trigger(game, card)
        assert trigger is not None

        instant = Instant(name="Opponent Instant", owner=p2, controller=p2)
        event = SpellCastTriggeredEvent(spell=instant, player=p2, controller=p2)
        if trigger.condition is not None:
            assert trigger.condition(game, event) is False

    def test_condition_false_when_silverquill_not_on_battlefield(self) -> None:
        """Trigger condition returns False when Silverquill is not on the battlefield
        (e.g., has left play since registering)."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        # Register triggers WITHOUT putting Silverquill on battlefield first.
        # (Simulates the card registering when entering battlefield but being
        # removed before the event fires — condition should guard this.)
        card.register_triggers(game)
        trigger = self._get_spell_cast_trigger(game, card)
        assert trigger is not None

        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=instant, player=p1, controller=p1)
        if trigger.condition is not None:
            assert trigger.condition(game, event) is False


# ---------------------------------------------------------------------------
# Trigger firing — stack interaction
# ---------------------------------------------------------------------------

class TestSilverquillTriggerFiring:
    """fire_event with matching spell pushes trigger onto stack; non-matching does not."""

    def test_trigger_fires_on_instant_cast_event(self) -> None:
        """Firing SpellCastTriggeredEvent with an instant cast by controller
        causes Silverquill's trigger to appear on the stack."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=instant, player=p1, controller=p1)
        stack_before = len(game.stack)
        game.trigger_manager.fire_event(game, event)
        assert len(game.stack) > stack_before

    def test_trigger_fires_on_sorcery_cast_event(self) -> None:
        """Firing SpellCastTriggeredEvent with a sorcery cast by controller
        causes Silverquill's trigger to appear on the stack."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        sorcery = Sorcery(name="Test Sorcery", owner=p1, controller=p1)
        event = SpellCastTriggeredEvent(spell=sorcery, player=p1, controller=p1)
        stack_before = len(game.stack)
        game.trigger_manager.fire_event(game, event)
        assert len(game.stack) > stack_before

    def test_trigger_does_not_fire_on_creature_cast_event(self) -> None:
        """Firing SpellCastTriggeredEvent with a creature spell does NOT push
        Silverquill's casualty trigger onto the stack."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        creature_spell = Creature(name="Test Bear", owner=p1, controller=p1,
                                  base_power=2, base_toughness=2)
        event = SpellCastTriggeredEvent(spell=creature_spell, player=p1, controller=p1)
        stack_before = len(game.stack)
        game.trigger_manager.fire_event(game, event)
        assert len(game.stack) == stack_before

    def test_trigger_does_not_fire_for_opponent_instant(self) -> None:
        """Opponent casting an instant should NOT push Silverquill's trigger."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        instant = Instant(name="Opponent Bolt", owner=p2, controller=p2)
        event = SpellCastTriggeredEvent(spell=instant, player=p2, controller=p2)
        stack_before = len(game.stack)
        game.trigger_manager.fire_event(game, event)
        assert len(game.stack) == stack_before


# ---------------------------------------------------------------------------
# Casualty 1 effect — no copy when no eligible creatures
# ---------------------------------------------------------------------------

class TestSilverquillCasualtyEffectNoEligibleCreatures:
    """Casualty 1 effect must not create a copy when no eligible creatures exist."""

    def _get_casualty_effect(self, game, card):
        """Return the effect function of the SpellCastTriggeredEvent trigger."""
        triggers = game.trigger_manager.get_triggers_for_source(card)
        for t in triggers:
            if t.event_type is SpellCastTriggeredEvent or (
                isinstance(t.event_type, type) and issubclass(SpellCastTriggeredEvent, t.event_type)
            ):
                return t.effect
        return None

    def test_effect_noop_with_empty_battlefield(self) -> None:
        """Casualty trigger effect must not raise and must not add a copy to the
        stack when the controller has no creatures to sacrifice."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        # Silverquill alone on battlefield — cannot sacrifice itself for casualty.
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        # Simulate the original spell being on the stack.
        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        original_so = StackObject(source=instant, controller=p1)
        game.stack.push(original_so)

        # Fire event so condition captures the spell.
        event = SpellCastTriggeredEvent(spell=instant, player=p1, controller=p1)
        game.trigger_manager.fire_event(game, event)

        # Pop trigger off stack, run effect.
        trigger_so = game.stack.pop()  # trigger StackObject on top
        stack_size_before_effect = len(game.stack)
        # Effect must not raise.
        trigger_so.on_resolve(game)
        # No extra copy pushed — original spell is still there and nothing added.
        assert len(game.stack) <= stack_size_before_effect

    def test_effect_noop_with_creature_power_zero(self) -> None:
        """A creature with power 0 is not a legal casualty sacrifice target.
        The effect must not create a copy."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        zero_power = Creature(name="Zero Bear", owner=p1, controller=p1,
                              base_power=0, base_toughness=2)
        set_board_state(game, 0, battlefield=[card, zero_power])
        card.register_triggers(game)

        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        original_so = StackObject(source=instant, controller=p1)
        game.stack.push(original_so)

        event = SpellCastTriggeredEvent(spell=instant, player=p1, controller=p1)
        game.trigger_manager.fire_event(game, event)

        trigger_so = game.stack.pop()
        stack_size_before_effect = len(game.stack)
        trigger_so.on_resolve(game)
        # No copy pushed because no valid casualty creature (all have power 0).
        assert len(game.stack) <= stack_size_before_effect


# ---------------------------------------------------------------------------
# Casualty 1 effect — copy created when eligible creature sacrificed
# ---------------------------------------------------------------------------

class TestSilverquillCasualtyEffectWithEligibleCreature:
    """Casualty 1 creates a copy on the stack when player pays by sacrificing
    a creature with power >= 1."""

    def test_copy_added_to_stack_when_casualty_paid(self) -> None:
        """When the controller has a creature with power >= 1 and chooses to
        pay the casualty cost (scripted), the original spell is copied and
        the copy is pushed onto the stack."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        sacrifice_target = Creature(
            name="Casualty Fodder",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        set_board_state(game, 0, battlefield=[card, sacrifice_target])
        card.register_triggers(game)

        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        original_so = StackObject(source=instant, controller=p1)
        game.stack.push(original_so)

        event = SpellCastTriggeredEvent(spell=instant, player=p1, controller=p1)
        game.trigger_manager.fire_event(game, event)

        trigger_so = game.stack.pop()

        # Script the player: yes, sacrifice; choose sacrifice_target.
        p1._script.append(True)           # yes, pay casualty
        p1._script.append(sacrifice_target)  # choose this creature to sacrifice

        stack_size_before_effect = len(game.stack)
        trigger_so.on_resolve(game)
        # A copy of the spell should have been pushed to the stack.
        assert len(game.stack) > stack_size_before_effect

    def test_sacrificed_creature_moves_to_graveyard_when_casualty_paid(self) -> None:
        """When casualty 1 is paid, the sacrificed creature must leave the
        battlefield (move to graveyard)."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        sacrifice_target = Creature(
            name="Casualty Fodder",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card, sacrifice_target])
        card.register_triggers(game)

        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        original_so = StackObject(source=instant, controller=p1)
        game.stack.push(original_so)

        event = SpellCastTriggeredEvent(spell=instant, player=p1, controller=p1)
        game.trigger_manager.fire_event(game, event)

        trigger_so = game.stack.pop()

        p1._script.append(True)           # yes, pay casualty
        p1._script.append(sacrifice_target)  # choose this creature

        trigger_so.on_resolve(game)

        # Sacrifice target must not remain on the battlefield.
        bf = game.get_battlefield(p1)
        assert not bf.contains(sacrifice_target)

    def test_no_copy_when_player_declines_casualty(self) -> None:
        """Casualty is optional. When the player says 'no', no copy is created
        and no creature is sacrificed."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        sacrifice_target = Creature(
            name="Saved Creature",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card, sacrifice_target])
        card.register_triggers(game)

        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        original_so = StackObject(source=instant, controller=p1)
        game.stack.push(original_so)

        event = SpellCastTriggeredEvent(spell=instant, player=p1, controller=p1)
        game.trigger_manager.fire_event(game, event)

        trigger_so = game.stack.pop()

        p1._script.append(False)  # no, decline casualty

        stack_size_before = len(game.stack)
        trigger_so.on_resolve(game)

        # No copy pushed.
        assert len(game.stack) == stack_size_before
        # Creature stays on battlefield.
        bf = game.get_battlefield(p1)
        assert bf.contains(sacrifice_target)


# ---------------------------------------------------------------------------
# Casualty 1 — copy target mechanics ("you may choose new targets for the copy")
# ---------------------------------------------------------------------------

class TestSilverquillCopyNewTargets:
    """The copy created by casualty 1 must allow the player to choose new targets.

    Oracle text: 'copy the spell and you may choose new targets for the copy'

    Requirements:
      - The copy StackObject is a distinct object from the original.
      - The copy's target list is independent of the original's.
      - When the player declines to choose new targets the copy retains the
        original spell's targets.
      - When the player supplies new targets the copy uses those new targets
        (not the original spell's targets).
    """

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _setup_trigger(self, game, p1, card, instant, targets=None):
        """Push instant onto the stack, fire the SpellCastTriggeredEvent, and
        return the trigger StackObject that lands on top of the stack.

        ``targets`` is the target list for the original spell StackObject.
        """
        from engine.stack import StackObject
        original_so = StackObject(
            source=instant,
            controller=p1,
            targets=list(targets) if targets else [],
        )
        game.stack.push(original_so)

        event = SpellCastTriggeredEvent(spell=instant, player=p1, controller=p1)
        game.trigger_manager.fire_event(game, event)

        # The trigger goes on top; pop it so we can inspect the stack below.
        trigger_so = game.stack.pop()
        return trigger_so, original_so

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_copy_source_is_distinct_card_object_from_original_spell(self) -> None:
        """The source of the copy StackObject must be a different Python object
        from the original spell — i.e., it is a true independent copy, not an
        alias to the same card instance."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        sac_target = Creature(
            name="Fodder", owner=p1, controller=p1, base_power=1, base_toughness=1
        )
        set_board_state(game, 0, battlefield=[card, sac_target])
        card.register_triggers(game)

        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        trigger_so, _original_so = self._setup_trigger(game, p1, card, instant)

        p1._script.append(True)         # yes, pay casualty
        p1._script.append(sac_target)   # sacrifice this creature

        stack_size_before = len(game.stack)
        trigger_so.on_resolve(game)

        assert len(game.stack) > stack_size_before, "a copy must be pushed onto the stack"
        copy_so = game.stack.peek()
        assert copy_so.source is not instant, (
            "copy source must be a distinct card object, not the same as the original spell"
        )

    def test_copy_targets_list_is_independent_of_original_targets_list(self) -> None:
        """The copy StackObject's targets list must be a separate list from the
        original spell StackObject's targets list. Mutating one must not affect
        the other."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        sac_target = Creature(
            name="Fodder", owner=p1, controller=p1, base_power=1, base_toughness=1
        )
        sentinel = Creature(
            name="Sentinel", owner=p2, controller=p2, base_power=2, base_toughness=2
        )
        set_board_state(game, 0, battlefield=[card, sac_target])
        card.register_triggers(game)

        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        trigger_so, original_so = self._setup_trigger(
            game, p1, card, instant, targets=[sentinel]
        )

        p1._script.append(True)
        p1._script.append(sac_target)

        trigger_so.on_resolve(game)

        copy_so = game.stack.peek()
        assert copy_so is not None, "copy must be on the stack"

        # Appending to the copy's target list must not change the original's.
        original_len = len(original_so.targets)
        copy_so.targets.append(object())
        assert len(original_so.targets) == original_len, (
            "copy's target list must be independent — mutating it must not change the original"
        )

    def test_copy_retains_original_targets_when_player_declines_new_targets(self) -> None:
        """When the original spell had targets and the player declines to choose
        new targets for the copy, the copy StackObject must carry the same
        target(s) as the original spell.

        Oracle: 'you may choose new targets for the copy' — declining the
        option must still leave the copy pointing at the same targets.
        """
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        sac_target = Creature(
            name="Fodder", owner=p1, controller=p1, base_power=1, base_toughness=1
        )
        spell_target = Creature(
            name="SpellTarget", owner=p2, controller=p2, base_power=2, base_toughness=2
        )
        set_board_state(game, 0, battlefield=[card, sac_target])
        card.register_triggers(game)

        instant = Instant(name="Targeted Instant", owner=p1, controller=p1)
        trigger_so, _original_so = self._setup_trigger(
            game, p1, card, instant, targets=[spell_target]
        )

        # Script: pay casualty; decline to choose new targets.
        p1._script.append(True)         # yes, pay casualty
        p1._script.append(sac_target)   # sacrifice this creature
        p1._script.append(False)        # no, keep original targets

        trigger_so.on_resolve(game)

        copy_so = game.stack.peek()
        assert copy_so is not None, "copy must be on the stack"
        assert spell_target in copy_so.targets, (
            "when the player declines new targets the copy must retain the original spell's targets"
        )

    def test_copy_uses_new_targets_when_player_provides_them(self) -> None:
        """When the player provides new targets for the copy, the copy
        StackObject must carry those new targets instead of the original spell's
        targets.

        Oracle: 'you may choose new targets for the copy'
        """
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        sac_target = Creature(
            name="Fodder", owner=p1, controller=p1, base_power=1, base_toughness=1
        )
        original_target = Creature(
            name="OriginalTarget", owner=p2, controller=p2, base_power=2, base_toughness=2
        )
        new_target = Creature(
            name="NewTarget", owner=p2, controller=p2, base_power=3, base_toughness=3
        )
        set_board_state(game, 0, battlefield=[card, sac_target])
        card.register_triggers(game)

        instant = Instant(name="Targeted Instant", owner=p1, controller=p1)
        trigger_so, _original_so = self._setup_trigger(
            game, p1, card, instant, targets=[original_target]
        )

        # Script: pay casualty; opt into new targets; provide new_target.
        p1._script.append(True)           # yes, pay casualty
        p1._script.append(sac_target)     # sacrifice this creature
        p1._script.append(True)           # yes, choose new targets
        p1._script.append(new_target)     # the new target

        trigger_so.on_resolve(game)

        copy_so = game.stack.peek()
        assert copy_so is not None, "copy must be on the stack"
        assert new_target in copy_so.targets, (
            "copy must use the player-chosen new target"
        )
        assert original_target not in copy_so.targets, (
            "copy must NOT carry the original spell's target when new targets were chosen"
        )
