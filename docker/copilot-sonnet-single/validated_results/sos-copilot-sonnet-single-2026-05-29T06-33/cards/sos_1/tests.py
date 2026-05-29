"""Tests for SOS 1 — The Dawning Archaic.

Covers:
- Static card properties (name, mana_cost, P/T, type, legendary, subtype)
- Reach keyword
- Cost reduction: {1} less per instant/sorcery in controller's graveyard
- Attack trigger: cast an instant or sorcery from graveyard for free
- Attack trigger replacement: spell exiled instead of going to graveyard
"""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.combat import _can_block
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state, declare_attackers


# ---------------------------------------------------------------------------
# Static property tests
# ---------------------------------------------------------------------------


class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_is_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_power(self) -> None:
        assert TheDawningArchaic(owner=None).base_power == 7

    def test_toughness(self) -> None:
        assert TheDawningArchaic(owner=None).base_toughness == 7

    def test_has_reach_keyword(self) -> None:
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in TheDawningArchaic(owner=None).supertypes

    def test_subtype_is_avatar(self) -> None:
        assert "Avatar" in TheDawningArchaic(owner=None).subtypes

    def test_has_creature_card_type(self) -> None:
        assert CardType.CREATURE in TheDawningArchaic(owner=None).card_types


# ---------------------------------------------------------------------------
# Reach — blocking flying attackers
# ---------------------------------------------------------------------------


class TestTheDawningArchaicReach:
    """REACH allows this creature to block creatures with flying."""

    def test_can_block_flying_attacker(self) -> None:
        archaic = TheDawningArchaic(owner=None)
        archaic.is_tapped = False
        flier = Creature(name="Air Elemental", base_power=4, base_toughness=4)
        flier.keywords = Keyword.FLYING
        flier.is_tapped = False
        assert _can_block(archaic, flier) is True

    def test_ground_creature_without_reach_cannot_block_flier(self) -> None:
        """Sanity check: non-reach creatures cannot block fliers."""
        ground = Creature(name="Forest Bear", base_power=2, base_toughness=2)
        ground.keywords = Keyword(0)
        ground.is_tapped = False
        flier = Creature(name="Air Elemental", base_power=4, base_toughness=4)
        flier.keywords = Keyword.FLYING
        flier.is_tapped = False
        assert _can_block(ground, flier) is False


# ---------------------------------------------------------------------------
# Cost reduction
# ---------------------------------------------------------------------------


class TestTheDawningArchaicCostReduction:
    """Cost reduces by 1 for each instant/sorcery in controller's graveyard."""

    def test_zero_reduction_with_empty_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_reduction_for_one_instant_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant = Instant(name="Lightning Bolt")
        set_board_state(game, 0, graveyard=[instant])
        assert card.cost_reduction(game) == 1

    def test_one_reduction_for_one_sorcery_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        sorcery = Sorcery(name="Divination")
        set_board_state(game, 0, graveyard=[sorcery])
        assert card.cost_reduction(game) == 1

    def test_multiple_instants_and_sorceries_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        spells = [
            Instant(name="Bolt 1"),
            Instant(name="Bolt 2"),
            Sorcery(name="Twirl"),
        ]
        set_board_state(game, 0, graveyard=spells)
        assert card.cost_reduction(game) == 3

    def test_creature_in_graveyard_does_not_reduce_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        creature = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[creature])
        assert card.cost_reduction(game) == 0

    def test_only_controller_graveyard_counts_not_opponent(self) -> None:
        """Opponent's instant/sorceries in graveyard should not reduce cost."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        # Put spells in opponent's graveyard
        opp_spells = [Instant(name="Counterspell"), Sorcery(name="Dark Ritual")]
        set_board_state(game, 1, graveyard=opp_spells)
        # Controller's graveyard is empty
        assert card.cost_reduction(game) == 0

    def test_mixed_graveyard_counts_only_instants_and_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        cards_in_gy = [
            Instant(name="Shock"),
            Creature(name="Soldier", base_power=1, base_toughness=1),
            Sorcery(name="Overrun"),
        ]
        set_board_state(game, 0, graveyard=cards_in_gy)
        assert card.cost_reduction(game) == 2

    def test_ten_spells_reduces_cost_by_ten(self) -> None:
        """Ten instants/sorceries reduces {10} to {0} (clamped by engine)."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        spells = [Instant(name=f"Spell {i}") for i in range(10)]
        set_board_state(game, 0, graveyard=spells)
        assert card.cost_reduction(game) == 10


# ---------------------------------------------------------------------------
# Attack trigger — register_triggers
# ---------------------------------------------------------------------------


class TestTheDawningArchaicAttackTrigger:
    """Whenever The Dawning Archaic attacks, the trigger registers correctly."""

    def test_register_triggers_does_not_raise(self) -> None:
        """register_triggers must not raise on a freshly created game."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)  # Should not raise

    def test_attack_trigger_is_registered(self) -> None:
        """After register_triggers, at least one trigger exists for source."""
        from engine.events import AttacksTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(archaic)
        assert len(triggers) >= 1

    def test_attack_trigger_fires_on_attacks_event(self) -> None:
        """Firing AttacksTriggeredEvent for this creature pushes onto the stack."""
        from engine.events import AttacksTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        assert game.stack.is_empty()
        event = AttacksTriggeredEvent(creature=archaic, attacker=archaic)
        game.trigger_manager.fire_event(game, event)
        # The trigger should have put something on the stack
        assert not game.stack.is_empty()

    def test_attack_trigger_does_not_fire_for_other_creature(self) -> None:
        """The trigger should only fire for The Dawning Archaic attacking."""
        from engine.events import AttacksTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        assert game.stack.is_empty()
        other = Creature(name="Bear", base_power=2, base_toughness=2)
        event = AttacksTriggeredEvent(creature=other, attacker=other)
        game.trigger_manager.fire_event(game, event)
        # The trigger should NOT fire for a different attacker
        assert game.stack.is_empty()


# ---------------------------------------------------------------------------
# Attack trigger resolution — cast from graveyard for free
# ---------------------------------------------------------------------------


class TestTheDawningArchaicTriggerResolution:
    """Trigger resolves: cast instant/sorcery from graveyard without paying cost."""

    def test_trigger_resolves_noop_with_empty_graveyard(self) -> None:
        """With no instant/sorcery in graveyard, trigger resolution is a no-op."""
        from engine.events import AttacksTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)

        event = AttacksTriggeredEvent(creature=archaic, attacker=archaic)
        game.trigger_manager.fire_event(game, event)

        # Pop and resolve the trigger — should not raise
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

    def test_trigger_can_cast_instant_from_graveyard(self) -> None:
        """Trigger resolution casts an instant from graveyard at zero cost."""
        from engine.events import AttacksTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)

        # Put an instant in the graveyard
        bolt = Instant(name="Lightning Bolt")
        bolt.owner = p1
        bolt.controller = p1
        p1.zones[Zone.GRAVEYARD].add(bolt)

        gy_before = len(p1.zones[Zone.GRAVEYARD].get_all())
        assert gy_before == 1

        event = AttacksTriggeredEvent(creature=archaic, attacker=archaic)
        game.trigger_manager.fire_event(game, event)
        trigger_obj = game.stack.pop()
        # Script the player to choose the bolt
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(bolt)
        trigger_obj.on_resolve(game)

        # The bolt is no longer in the graveyard after being cast
        gy_after_cards = p1.zones[Zone.GRAVEYARD].get_all()
        assert bolt not in gy_after_cards

    def test_trigger_can_cast_sorcery_from_graveyard(self) -> None:
        """Trigger resolution can also cast a sorcery from graveyard for free."""
        from engine.events import AttacksTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)

        sorcery = Sorcery(name="Ancestral Recall")
        sorcery.owner = p1
        sorcery.controller = p1
        p1.zones[Zone.GRAVEYARD].add(sorcery)

        event = AttacksTriggeredEvent(creature=archaic, attacker=archaic)
        game.trigger_manager.fire_event(game, event)
        trigger_obj = game.stack.pop()
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(sorcery)
        trigger_obj.on_resolve(game)

        # The sorcery should leave the graveyard
        gy_cards = p1.zones[Zone.GRAVEYARD].get_all()
        assert sorcery not in gy_cards

    def test_spell_cast_via_trigger_exiled_instead_of_graveyard(self) -> None:
        """If spell cast via trigger would go to graveyard, exile it instead."""
        from engine.events import AttacksTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)

        bolt = Instant(name="Lightning Bolt")
        bolt.owner = p1
        bolt.controller = p1
        p1.zones[Zone.GRAVEYARD].add(bolt)

        event = AttacksTriggeredEvent(creature=archaic, attacker=archaic)
        game.trigger_manager.fire_event(game, event)
        trigger_obj = game.stack.pop()
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(bolt)
        trigger_obj.on_resolve(game)

        # After resolution: spell should be exiled, NOT in graveyard
        exile_cards = p1.zones[Zone.EXILE].get_all()
        gy_cards = p1.zones[Zone.GRAVEYARD].get_all()
        assert bolt not in gy_cards
        # The bolt ends up exiled (not in graveyard)
        assert bolt in exile_cards

    def test_trigger_no_op_with_only_creatures_in_graveyard(self) -> None:
        """Trigger is a no-op when only creatures are in graveyard."""
        from engine.events import AttacksTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)

        creature = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        creature.owner = p1
        creature.controller = p1
        p1.zones[Zone.GRAVEYARD].add(creature)

        event = AttacksTriggeredEvent(creature=archaic, attacker=archaic)
        game.trigger_manager.fire_event(game, event)
        trigger_obj = game.stack.pop()
        # No valid target, trigger resolves as no-op
        trigger_obj.on_resolve(game)

        # Creature remains in graveyard untouched
        gy_cards = p1.zones[Zone.GRAVEYARD].get_all()
        assert creature in gy_cards
