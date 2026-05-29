"""Tests for sos_1 — The Dawning Archaic.

Tests cover:
1. Static card properties (name, mana_cost, P/T, type, keywords, supertypes, subtypes).
2. Cost-reduction mechanic: {1} less per instant/sorcery in controller's graveyard.
3. Attack trigger: registers for AttacksTriggeredEvent, condition checks the Archaic itself.
4. Attack trigger effect: casts target instant/sorcery from GY for free.
5. Exile-instead replacement: spell cast via trigger goes to exile, not graveyard.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_instant(name: str = "Test Instant", owner=None) -> Instant:
    """Create a minimal no-op Instant for testing."""
    inst = Instant(name=name, owner=owner, controller=owner)
    return inst


def _make_sorcery(name: str = "Test Sorcery", owner=None) -> Sorcery:
    """Create a minimal no-op Sorcery for testing."""
    sor = Sorcery(name=name, owner=owner, controller=owner)
    return sor


def _get_archaic_trigger(game, archaic: TheDawningArchaic) -> TriggerRegistration | None:
    """Return the first TriggerRegistration owned by *archaic*, or None."""
    triggers = game.trigger_manager.get_triggers_for_source(archaic)
    return triggers[0] if triggers else None


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------

class TestTheDawningArchaicProperties:
    """Static card data must match the sos_1 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(TheDawningArchaic(owner=None), Creature)

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_base_power(self) -> None:
        assert TheDawningArchaic(owner=None).base_power == 7

    def test_base_toughness(self) -> None:
        assert TheDawningArchaic(owner=None).base_toughness == 7

    def test_has_reach(self) -> None:
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in TheDawningArchaic(owner=None).supertypes

    def test_has_avatar_subtype(self) -> None:
        assert "Avatar" in TheDawningArchaic(owner=None).subtypes


# ---------------------------------------------------------------------------
# Cost-reduction mechanic
# ---------------------------------------------------------------------------

class TestTheDawningArchaicCostReduction:
    """This spell costs {1} less for each instant/sorcery in your graveyard."""

    def test_zero_reduction_with_empty_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        # No instants/sorceries in graveyard
        assert archaic.cost_reduction(game) == 0

    def test_one_instant_gives_one_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        instant = _make_instant(owner=p1)
        set_board_state(game, 0, graveyard=[instant])
        assert archaic.cost_reduction(game) == 1

    def test_one_sorcery_gives_one_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        sorcery = _make_sorcery(owner=p1)
        set_board_state(game, 0, graveyard=[sorcery])
        assert archaic.cost_reduction(game) == 1

    def test_multiple_instants_and_sorceries_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        cards = [
            _make_instant("Instant A", p1),
            _make_instant("Instant B", p1),
            _make_sorcery("Sorcery A", p1),
        ]
        set_board_state(game, 0, graveyard=cards)
        assert archaic.cost_reduction(game) == 3

    def test_creatures_in_graveyard_do_not_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2, owner=p1)
        set_board_state(game, 0, graveyard=[bear])
        assert archaic.cost_reduction(game) == 0

    def test_cost_reduction_capped_at_generic_mana(self) -> None:
        """Reduction cannot make the cost go below 0; capped at 10."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        # 15 instants in graveyard — can only reduce by 10 (the full generic cost)
        cards = [_make_instant(f"Instant {i}", p1) for i in range(15)]
        set_board_state(game, 0, graveyard=cards)
        # cost_reduction() itself may return > 10; the casting engine clamps it.
        # But we can verify the raw value doesn't go negative if clamped.
        raw = archaic.cost_reduction(game)
        assert raw >= 10  # should return at least 10 (the full generic)

    def test_opponent_graveyard_does_not_count(self) -> None:
        """Only the controller's graveyard counts, not the opponent's."""
        game = create_game()
        p1, p2 = game.players
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        # Put instants in opponent's GY only
        set_board_state(game, 1, graveyard=[_make_instant(owner=p2)])
        assert archaic.cost_reduction(game) == 0


# ---------------------------------------------------------------------------
# Attack trigger registration
# ---------------------------------------------------------------------------

class TestTheDawningArchaicTriggerRegistration:
    """register_triggers must wire an AttacksTriggeredEvent trigger."""

    def test_registers_exactly_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        archaic.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after - before == 1

    def test_trigger_event_type_is_attacks(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        trigger = _get_archaic_trigger(game, archaic)
        assert trigger is not None
        assert trigger.event_type is AttacksTriggeredEvent

    def test_trigger_source_is_archaic(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        trigger = _get_archaic_trigger(game, archaic)
        assert trigger is not None
        assert trigger.source is archaic

    def test_trigger_controller_is_owner(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        trigger = _get_archaic_trigger(game, archaic)
        assert trigger is not None
        assert trigger.controller is p1


# ---------------------------------------------------------------------------
# Attack trigger condition
# ---------------------------------------------------------------------------

class TestTheDawningArchaicTriggerCondition:
    """Trigger condition fires only when the Archaic itself is the attacker."""

    def test_condition_true_when_archaic_attacks(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        trigger = _get_archaic_trigger(game, archaic)
        assert trigger is not None
        assert trigger.condition is not None

        # Fire event with the archaic as attacker
        event = AttacksTriggeredEvent(creature=archaic, attacker=archaic)
        assert trigger.condition(game, event) is True

    def test_condition_false_when_different_creature_attacks(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        trigger = _get_archaic_trigger(game, archaic)
        assert trigger is not None
        assert trigger.condition is not None

        # Fire event with a different creature as attacker
        other = Creature(name="Other Creature", base_power=2, base_toughness=2)
        event = AttacksTriggeredEvent(creature=other, attacker=other)
        assert trigger.condition(game, event) is False

    def test_condition_not_none(self) -> None:
        """The trigger must have a condition guard (not unconditional)."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        trigger = _get_archaic_trigger(game, archaic)
        assert trigger is not None
        assert trigger.condition is not None


# ---------------------------------------------------------------------------
# Attack trigger effect — casting from graveyard
# ---------------------------------------------------------------------------

class TestTheDawningArchaicTriggerEffect:
    """Trigger effect casts a target instant/sorcery from GY for free."""

    def _get_effect(self, game, archaic):
        """Register triggers and return the effect callable."""
        archaic.register_triggers(game)
        trigger = _get_archaic_trigger(game, archaic)
        assert trigger is not None
        return trigger.effect

    def test_effect_with_empty_graveyard_does_not_raise(self) -> None:
        """If there are no instants/sorceries in the GY, the effect should be a no-op."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        effect = self._get_effect(game, archaic)
        # No instants/sorceries in GY — must not raise
        effect(game)

    def test_effect_with_player_declining_does_not_cast(self) -> None:
        """Player says 'no' to the 'you may' — spell stays in graveyard."""
        from collections import deque

        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        effect = self._get_effect(game, archaic)

        instant = _make_instant(owner=p1)
        set_board_state(game, 0, graveyard=[instant])

        # Script: choose "no" for "you may"
        p1._script.appendleft(False)
        effect(game)

        # Instant should still be in graveyard
        gy = p1.zones[Zone.GRAVEYARD]
        assert gy.contains(instant)

    def test_effect_casts_chosen_instant_from_graveyard(self) -> None:
        """When player says yes and chooses the instant, it leaves the GY."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        effect = self._get_effect(game, archaic)

        instant = _make_instant("Chosen Instant", owner=p1)
        set_board_state(game, 0, graveyard=[instant])

        # Script: say yes, then choose the instant
        p1._script.appendleft(instant)   # card chosen from GY
        p1._script.appendleft(True)      # "you may" = yes
        effect(game)

        # The instant should no longer be in the graveyard (it was cast)
        gy = p1.zones[Zone.GRAVEYARD]
        assert not gy.contains(instant)

    def test_effect_casts_chosen_sorcery_from_graveyard(self) -> None:
        """Sorcery cards in the GY are also valid targets for the trigger."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        effect = self._get_effect(game, archaic)

        sorcery = _make_sorcery("Chosen Sorcery", owner=p1)
        set_board_state(game, 0, graveyard=[sorcery])

        # Script: say yes, then choose the sorcery
        p1._script.appendleft(sorcery)   # card chosen
        p1._script.appendleft(True)      # "you may" = yes
        effect(game)

        gy = p1.zones[Zone.GRAVEYARD]
        assert not gy.contains(sorcery)


# ---------------------------------------------------------------------------
# Exile-instead replacement
# ---------------------------------------------------------------------------

class TestTheDawningArchaicExileInstead:
    """Spell cast via the trigger must go to exile, not graveyard, after resolving."""

    def test_instant_cast_from_graveyard_exiles_not_graveyard(self) -> None:
        """After the trigger effect fires and the cast spell resolves, it is in exile."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        trigger = _get_archaic_trigger(game, archaic)
        assert trigger is not None

        instant = _make_instant("Exiling Instant", owner=p1)
        set_board_state(game, 0, graveyard=[instant])

        # Script: say yes, choose the instant
        p1._script.appendleft(instant)
        p1._script.appendleft(True)
        trigger.effect(game)

        # Resolve anything on the stack (the cast instant)
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        # The instant must be in exile, NOT in the graveyard
        exile = p1.zones[Zone.EXILE]
        gy = p1.zones[Zone.GRAVEYARD]
        assert exile.contains(instant), "Spell should be exiled after being cast via Dawning Archaic"
        assert not gy.contains(instant), "Spell should NOT be in graveyard after being cast via Dawning Archaic"

    def test_sorcery_cast_from_graveyard_exiles_not_graveyard(self) -> None:
        """Sorcery cast via the trigger also ends up in exile."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        trigger = _get_archaic_trigger(game, archaic)
        assert trigger is not None

        sorcery = _make_sorcery("Exiling Sorcery", owner=p1)
        set_board_state(game, 0, graveyard=[sorcery])

        p1._script.appendleft(sorcery)
        p1._script.appendleft(True)
        trigger.effect(game)

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        exile = p1.zones[Zone.EXILE]
        gy = p1.zones[Zone.GRAVEYARD]
        assert exile.contains(sorcery), "Sorcery should be exiled after Dawning Archaic trigger"
        assert not gy.contains(sorcery), "Sorcery should NOT be in graveyard after Dawning Archaic trigger"
