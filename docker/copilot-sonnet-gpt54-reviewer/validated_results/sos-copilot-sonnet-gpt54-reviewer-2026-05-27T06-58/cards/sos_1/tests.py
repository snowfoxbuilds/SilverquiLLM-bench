"""Tests for SOS 1 — The Dawning Archaic.

Covers:
  1. Static card properties (name, mana cost, P/T, keywords, supertypes, subtypes, card type).
  2. Cost reduction: {1} less for each instant and sorcery in controller's graveyard.
  3. Trigger registration: register_triggers wires an AttacksTriggeredEvent trigger.
  4. Trigger fires: the trigger only fires when The Dawning Archaic itself attacks.
  5. Attack trigger resolution: allows casting a target instant or sorcery from the graveyard
     without paying its mana cost.
  6. Replacement effect: if the spell cast from graveyard would go to the graveyard, exile it
     instead.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent, MoveToGraveyardReplacementEvent
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


class TestTheDawningArchaicProperties:
    """Static card data must match the SOS 1 spec."""

    def test_is_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.mana_cost == ManaCost.parse("{10}")

    def test_base_power(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7

    def test_base_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_toughness == 7

    def test_has_reach(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Keyword.REACH in card.keywords

    def test_is_legendary(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_avatar_subtype(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert "Avatar" in card.subtypes

    def test_is_creature_card_type(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert CardType.CREATURE in card.card_types


# ---------------------------------------------------------------------------
# Cost reduction
# ---------------------------------------------------------------------------


class TestTheDawningArchaicCostReduction:
    """cost_reduction(game) counts instants and sorceries in the
    controller's graveyard and returns how much to reduce the cost by."""

    def test_zero_reduction_with_empty_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_instant_in_graveyard_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        instant = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant])

        assert card.cost_reduction(game) == 1

    def test_one_sorcery_in_graveyard_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[sorcery])

        assert card.cost_reduction(game) == 1

    def test_mixed_instants_and_sorceries_count_both(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        instant = Instant(name="Shock", owner=p1, controller=p1)
        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant, sorcery])

        assert card.cost_reduction(game) == 2

    def test_non_instant_sorcery_cards_not_counted(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        creature_in_gy = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                                   base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[creature_in_gy])

        assert card.cost_reduction(game) == 0

    def test_five_instants_reduces_by_five(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        instants = [Instant(name=f"Spell{i}", owner=p1, controller=p1) for i in range(5)]
        set_board_state(game, 0, graveyard=instants)

        assert card.cost_reduction(game) == 5

    def test_ten_instants_reduces_by_ten(self) -> None:
        """At 10 instants/sorceries the cost should be free (reduction == 10 == CMC)."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        instants = [Instant(name=f"Spell{i}", owner=p1, controller=p1) for i in range(10)]
        set_board_state(game, 0, graveyard=instants)

        assert card.cost_reduction(game) == 10

    def test_cost_reduction_uses_controller_graveyard_not_opponent(self) -> None:
        """Instants/sorceries in the opponent's graveyard must NOT count."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TheDawningArchaic(owner=p1, controller=p1)

        opponent_instant = Instant(name="Counterspell", owner=p2, controller=p2)
        set_board_state(game, 1, graveyard=[opponent_instant])

        assert card.cost_reduction(game) == 0


# ---------------------------------------------------------------------------
# Trigger registration
# ---------------------------------------------------------------------------


class TestTheDawningArchaicTriggerRegistration:
    """register_triggers must wire a trigger for AttacksTriggeredEvent."""

    def test_registers_at_least_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())

        assert after > before

    def test_registered_trigger_is_for_attacks_event(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)

        attack_triggers = [
            t for t in triggers if t.event_type is AttacksTriggeredEvent
        ]
        assert len(attack_triggers) >= 1

    def test_registered_trigger_has_correct_source(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)

        assert len(triggers) >= 1
        assert all(t.source is card for t in triggers)

    def test_registered_trigger_has_correct_controller(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)

        attack_triggers = [t for t in triggers if t.event_type is AttacksTriggeredEvent]
        assert len(attack_triggers) >= 1
        assert attack_triggers[0].controller is p1


# ---------------------------------------------------------------------------
# Trigger firing behaviour
# ---------------------------------------------------------------------------


class TestTheDawningArchaicTriggerFiring:
    """The trigger fires when The Dawning Archaic itself attacks, not
    when a different creature attacks."""

    def test_trigger_fires_when_archaic_attacks(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)

        before = len(game.stack)
        event = AttacksTriggeredEvent(creature=card, attacker=card)
        game.trigger_manager.fire_event(game, event)
        after = len(game.stack)

        assert after > before

    def test_trigger_does_not_fire_for_different_attacker(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)

        other_creature = Creature(name="Bear", owner=p1, controller=p1,
                                   base_power=2, base_toughness=2)

        before = len(game.stack)
        event = AttacksTriggeredEvent(creature=other_creature, attacker=other_creature)
        game.trigger_manager.fire_event(game, event)
        after = len(game.stack)

        assert after == before


# ---------------------------------------------------------------------------
# Trigger resolution: cast from graveyard
# ---------------------------------------------------------------------------


class TestTheDawningArchaicTriggerResolution:
    """When the attack trigger resolves, the controller may cast a target
    instant or sorcery from their graveyard without paying its mana cost."""

    def test_trigger_effect_callable_exists_after_registration(self) -> None:
        """Sanity check: after register_triggers, there is at least one
        trigger with a non-None effect callable."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert any(t.effect is not None for t in triggers)

    def test_resolving_trigger_moves_chosen_instant_from_graveyard(self) -> None:
        """When the attack trigger resolves and an instant is chosen,
        that instant leaves the graveyard (it is cast)."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        instant = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant])

        card.register_triggers(game)

        # Grab the attack trigger
        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_trigger = next(
            (t for t in triggers if t.event_type is AttacksTriggeredEvent), None
        )
        assert attack_trigger is not None

        # Simulate the trigger resolving by calling the effect directly.
        # The implementation needs to know what to cast, so we set chosen_targets
        # or the implementation reads the game state.  We inject the chosen spell
        # via DeterministicPlayer script.
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(instant)

        attack_trigger.effect(game)

        # After resolution the spell should no longer be in the graveyard
        graveyard = game.get_graveyard(p1).get_all()
        assert instant not in graveyard

    def test_resolving_trigger_moves_chosen_sorcery_from_graveyard(self) -> None:
        """When the attack trigger resolves and a sorcery is chosen,
        that sorcery leaves the graveyard (it is cast)."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        sorcery = Sorcery(name="Mind Rot", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[sorcery])

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_trigger = next(
            (t for t in triggers if t.event_type is AttacksTriggeredEvent), None
        )
        assert attack_trigger is not None

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(sorcery)

        attack_trigger.effect(game)

        graveyard = game.get_graveyard(p1).get_all()
        assert sorcery not in graveyard

    def test_trigger_noop_when_graveyard_has_no_instants_or_sorceries(self) -> None:
        """If there are no valid targets (no instants/sorceries in graveyard),
        the trigger effect resolves without error."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        # Put only a creature in the graveyard
        creature_gy = Creature(name="Dead Bear", owner=p1, controller=p1,
                                base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[creature_gy])

        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_trigger = next(
            (t for t in triggers if t.event_type is AttacksTriggeredEvent), None
        )
        assert attack_trigger is not None

        # Should not raise even with no valid targets
        attack_trigger.effect(game)


# ---------------------------------------------------------------------------
# Replacement effect: exile instead of graveyard
# ---------------------------------------------------------------------------


class TestTheDawningArchaicExileReplacement:
    """If the spell cast from the graveyard via the attack trigger would
    be put into the graveyard, exile it instead."""

    def test_registers_or_applies_exile_replacement_on_trigger_resolution(self) -> None:
        """After the trigger resolves and a spell is cast, a replacement effect
        or equivalent mechanism must be active to redirect the cast spell to
        exile instead of the graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        instant = Instant(name="Opt", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant])

        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_trigger = next(
            (t for t in triggers if t.event_type is AttacksTriggeredEvent), None
        )
        assert attack_trigger is not None

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(instant)

        before_replacements = len(game.replacement_manager._effects)
        attack_trigger.effect(game)

        # Either a replacement effect was registered, OR the spell ended up
        # in exile rather than the graveyard after resolution.
        graveyard_after = game.get_graveyard(p1).get_all()
        exile_after = game.get_exile(p1).get_all()
        replacements_after = len(game.replacement_manager._effects)

        # The spell was cast from the graveyard — it should NOT be back in gy,
        # and either be in exile or a replacement effect covers it.
        # We accept either observable outcome: spell in exile, or a
        # MoveToGraveyardReplacementEvent replacement was registered.
        spell_in_exile = instant in exile_after
        new_replacement_added = replacements_after > before_replacements

        assert spell_in_exile or new_replacement_added, (
            "Expected the cast spell to be in exile OR a replacement effect to "
            "have been registered redirecting it from graveyard to exile."
        )

    def test_spell_cast_from_graveyard_ends_in_exile_not_graveyard(self) -> None:
        """An instant resolved after being cast via the trigger must end up
        in exile (not the graveyard) after it resolves."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        # A simple instant with no effect (on_resolve is a no-op)
        instant = Instant(name="Opt", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant])

        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_trigger = next(
            (t for t in triggers if t.event_type is AttacksTriggeredEvent), None
        )
        assert attack_trigger is not None

        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(instant)

        attack_trigger.effect(game)

        # Resolve the cast spell from the stack (if it was put there)
        while not game.stack.is_empty():
            from engine.state_based_actions import resolve_state_based_actions
            obj = game.stack.pop()
            obj.on_resolve(game)
            resolve_state_based_actions(game)

        # The spell should now be in exile, not in the graveyard
        graveyard = game.get_graveyard(p1).get_all()
        exile = game.get_exile(p1).get_all()

        assert instant not in graveyard, (
            "Spell cast from graveyard via Dawning Archaic trigger should be "
            "exiled, not put back in the graveyard."
        )
        assert instant in exile, (
            "Spell cast from graveyard via Dawning Archaic trigger should be "
            "in exile after resolution."
        )
