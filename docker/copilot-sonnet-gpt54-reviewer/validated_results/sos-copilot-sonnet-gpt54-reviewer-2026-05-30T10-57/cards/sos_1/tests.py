"""Tests for SOS 1 — The Dawning Archaic.

Covers:
- Static card properties: Creature, name, mana cost, P/T, Reach, Legendary.
- Cost-reduction mechanic: 1 less generic mana per instant/sorcery in your graveyard.
- Reach keyword: The Dawning Archaic can block creatures with flying.
- Attack trigger: cast an instant or sorcery from graveyard for free when it attacks.
- Exile replacement: a spell cast via the trigger is exiled on resolution instead
  of going back to the graveyard.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.combat import _can_block
from engine.events import AttacksTriggeredEvent, MoveToGraveyardReplacementEvent
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_instant(name: str = "Test Instant") -> Instant:
    """Create a minimal Instant for graveyard population."""
    return Instant(name=name, mana_cost=ManaCost.parse("{U}"))


def _make_sorcery(name: str = "Test Sorcery") -> Sorcery:
    """Create a minimal Sorcery for graveyard population."""
    return Sorcery(name=name, mana_cost=ManaCost.parse("{R}"))


def _resolve_all_triggers(game) -> None:
    """Pop and resolve all objects currently on the stack (triggers + spells)."""
    from engine.state_based_actions import resolve_state_based_actions
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------

class TestTheDawningArchaicProperties:
    """Static card data must match the SOS 1 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(TheDawningArchaic(owner=None), Creature)

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.mana_cost == ManaCost.parse("{10}")

    def test_power(self) -> None:
        assert TheDawningArchaic(owner=None).base_power == 7

    def test_toughness(self) -> None:
        assert TheDawningArchaic(owner=None).base_toughness == 7

    def test_has_reach_keyword(self) -> None:
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in TheDawningArchaic(owner=None).supertypes

    def test_card_type_is_creature(self) -> None:
        assert CardType.CREATURE in TheDawningArchaic(owner=None).card_types


# ---------------------------------------------------------------------------
# Cost reduction
# ---------------------------------------------------------------------------

class TestTheDawningArchaicCostReduction:
    """cost_reduction() returns 1 per instant/sorcery in the controller's graveyard."""

    def test_zero_reduction_with_empty_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        # Graveyard is empty; no reduction.
        assert archaic.cost_reduction(game) == 0

    def test_one_reduction_per_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[_make_instant()])
        assert archaic.cost_reduction(game) == 1

    def test_one_reduction_per_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[_make_sorcery()])
        assert archaic.cost_reduction(game) == 1

    def test_stacks_across_instants_and_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            graveyard=[_make_instant("Bolt"), _make_sorcery("Loot"), _make_instant("Rune")],
        )
        assert archaic.cost_reduction(game) == 3

    def test_non_instant_sorcery_cards_not_counted(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[bear])
        assert archaic.cost_reduction(game) == 0

    def test_mixed_graveyard_counts_only_instants_and_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        set_board_state(
            game,
            0,
            graveyard=[bear, _make_instant("Shock"), _make_sorcery("Ponder")],
        )
        assert archaic.cost_reduction(game) == 2

    def test_only_controllers_graveyard_counts(self) -> None:
        """Instants in opponent's graveyard do not count toward cost reduction."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        # Put instants in opponent's graveyard, not player 0's.
        set_board_state(game, 1, graveyard=[_make_instant(), _make_instant()])
        assert archaic.cost_reduction(game) == 0


# ---------------------------------------------------------------------------
# Reach — blocking flying attackers
# ---------------------------------------------------------------------------

class TestTheDawningArchaicReach:
    """Reach allows The Dawning Archaic to block creatures with flying."""

    def test_can_block_flying_attacker(self) -> None:
        attacker = Creature(
            name="Flying Beatstick",
            base_power=3,
            base_toughness=3,
            keywords=Keyword.FLYING,
        )
        archaic = TheDawningArchaic(owner=None)
        archaic.is_tapped = False
        # Reach should allow blocking a flying attacker.
        assert _can_block(archaic, attacker) is True

    def test_ground_creature_without_reach_cannot_block_flier(self) -> None:
        """Baseline: ground creature without reach/flying can't block a flier."""
        attacker = Creature(
            name="Flying Beatstick",
            base_power=3,
            base_toughness=3,
            keywords=Keyword.FLYING,
        )
        blocker = Creature(name="Ground Bear", base_power=2, base_toughness=2)
        blocker.keywords = Keyword(0)
        blocker.is_tapped = False
        assert _can_block(blocker, attacker) is False

    def test_tapped_archaic_cannot_block(self) -> None:
        """Even a Reach creature can't block when tapped."""
        attacker = Creature(
            name="Flying Beater",
            base_power=2,
            base_toughness=2,
            keywords=Keyword.FLYING,
        )
        archaic = TheDawningArchaic(owner=None)
        archaic.is_tapped = True
        assert _can_block(archaic, attacker) is False


# ---------------------------------------------------------------------------
# Attack trigger — register_triggers registers for AttacksTriggeredEvent
# ---------------------------------------------------------------------------

class TestTheDawningArchaicAttackTriggerRegistration:
    """register_triggers() must register a trigger for AttacksTriggeredEvent."""

    def test_register_triggers_adds_attack_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        initial_count = len(game.trigger_manager._triggers)
        archaic.register_triggers(game)
        # At least one new trigger should have been registered.
        assert len(game.trigger_manager._triggers) > initial_count

    def test_registered_trigger_watches_attacks_event(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        # At least one trigger must be for the AttacksTriggeredEvent type.
        attack_triggers = [
            t for t in game.trigger_manager._triggers
            if issubclass(t.event_type, AttacksTriggeredEvent)
        ]
        assert len(attack_triggers) >= 1

    def test_trigger_fires_only_for_archaic_attacking(self) -> None:
        """The condition must match only when the archaic itself attacks."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)

        other_creature = Creature(name="Other Attacker", base_power=2, base_toughness=2)
        # Firing the event with a different creature should not place anything on the stack.
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=other_creature, attacker=other_creature),
        )
        assert game.stack.is_empty()

    def test_trigger_fires_when_archaic_attacks(self) -> None:
        """Firing AttacksTriggeredEvent with archaic as the attacker pushes a trigger."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )
        # The trigger should have been pushed onto the stack.
        assert not game.stack.is_empty()

    def test_attack_trigger_condition_excludes_other_creatures(self) -> None:
        """The condition explicitly rejects events from other creatures."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        attack_triggers = [
            t for t in game.trigger_manager._triggers
            if issubclass(t.event_type, AttacksTriggeredEvent)
        ]
        trigger = attack_triggers[0]
        assert trigger.condition is not None
        other = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1)
        event_other = AttacksTriggeredEvent(creature=other, attacker=other)
        assert trigger.condition(game, event_other) is False


# ---------------------------------------------------------------------------
# Attack trigger — effect: cast instant/sorcery from graveyard for free
# ---------------------------------------------------------------------------

class TestTheDawningArchaicAttackTriggerEffect:
    """When the trigger resolves with a chosen spell, it is cast for free."""

    def test_instant_removed_from_graveyard_when_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        instant = _make_instant("Shock")
        set_board_state(game, 0, graveyard=[instant])
        archaic.register_triggers(game)

        # Script: choose the instant when the trigger asks what to cast.
        p1._script.appendleft(instant)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )
        _resolve_all_triggers(game)

        # The instant should no longer be in the graveyard.
        graveyard = game.get_graveyard(p1)
        assert not graveyard.contains(instant)

    def test_sorcery_removed_from_graveyard_when_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        sorcery = _make_sorcery("Ponder")
        set_board_state(game, 0, graveyard=[sorcery])
        archaic.register_triggers(game)

        p1._script.appendleft(sorcery)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )
        _resolve_all_triggers(game)

        graveyard = game.get_graveyard(p1)
        assert not graveyard.contains(sorcery)

    def test_spell_cast_for_free_no_mana_required(self) -> None:
        """Casting via the trigger requires no mana from the player's pool."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        # Expensive instant — player has no mana to pay normally.
        expensive = Instant(name="Expensive Instant", mana_cost=ManaCost.parse("{7}"))
        set_board_state(game, 0, graveyard=[expensive])
        archaic.register_triggers(game)

        # Player has no mana — the free-cast should still succeed.
        p1._script.appendleft(expensive)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )
        _resolve_all_triggers(game)

        # Spell is no longer in graveyard (it was cast and resolved).
        graveyard = game.get_graveyard(p1)
        assert not graveyard.contains(expensive)


# ---------------------------------------------------------------------------
# Exile replacement — spell cast via trigger goes to exile, not graveyard
# ---------------------------------------------------------------------------

class TestTheDawningArchaicExileReplacement:
    """A spell cast via the attack trigger must be exiled after resolution, not graveyarded."""

    def test_instant_cast_via_trigger_ends_in_exile(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        instant = _make_instant("Lightning Bolt")
        set_board_state(game, 0, graveyard=[instant])
        archaic.register_triggers(game)

        p1._script.appendleft(instant)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )
        _resolve_all_triggers(game)

        exile = game.get_exile(p1)
        graveyard = game.get_graveyard(p1)
        assert exile.contains(instant), "Spell cast via trigger should be exiled"
        assert not graveyard.contains(instant), "Spell must not return to graveyard"

    def test_sorcery_cast_via_trigger_ends_in_exile(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        sorcery = _make_sorcery("Divination")
        set_board_state(game, 0, graveyard=[sorcery])
        archaic.register_triggers(game)

        p1._script.appendleft(sorcery)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )
        _resolve_all_triggers(game)

        exile = game.get_exile(p1)
        graveyard = game.get_graveyard(p1)
        assert exile.contains(sorcery), "Sorcery cast via trigger should be exiled"
        assert not graveyard.contains(sorcery), "Sorcery must not return to graveyard"

    def test_exile_replacement_does_not_affect_unrelated_spells(self) -> None:
        """A spell NOT cast via the trigger still goes to the graveyard normally."""
        from engine.casting import cast_spell as _engine_cast_spell
        from engine.types import Phase

        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)

        # Cast a separate instant from hand the normal way.
        normal_instant = _make_instant("Normal Instant")
        set_board_state(game, 0, hand=[normal_instant], mana={ManaType.BLUE: 1})
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        _engine_cast_spell(game, p1, normal_instant)
        _resolve_all_triggers(game)

        graveyard = game.get_graveyard(p1)
        exile = game.get_exile(p1)
        assert graveyard.contains(normal_instant), "Normal instant should go to graveyard"
        assert not exile.contains(normal_instant), "Normal instant must not be exiled"
