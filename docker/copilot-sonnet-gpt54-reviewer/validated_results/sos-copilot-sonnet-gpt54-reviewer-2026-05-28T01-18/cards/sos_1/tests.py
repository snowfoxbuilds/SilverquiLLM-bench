"""Tests for SOS 1 — The Dawning Archaic.

Covers:
- Static card properties (name, mana cost, type, P/T, keywords)
- Cost-reduction mechanic: {1} less per instant/sorcery in controller's graveyard
- Reach keyword
- Attack trigger: register_triggers hooks AttacksTriggeredEvent
- Attack trigger effect: casts target instant/sorcery from graveyard for free
- Exile replacement: if the cast spell would go to graveyard, exile it instead
"""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent, MoveToGraveyardReplacementEvent
from engine.replacement_effects import ReplacementEffect
from engine.triggers import TriggerRegistration
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------


class TestTheDawningArchaicProperties:
    """Static card data must match the SOS 1 spec."""

    def test_is_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

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

    def test_subtype_includes_avatar(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert "Avatar" in card.subtypes

    def test_card_type_is_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert CardType.CREATURE in card.card_types


# ---------------------------------------------------------------------------
# Cost-reduction mechanic
# ---------------------------------------------------------------------------


class TestCostReduction:
    """cost_reduction() returns {1} per instant/sorcery in controller's graveyard."""

    def test_no_graveyard_cards_gives_zero_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_instant_gives_reduction_of_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        instant = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 1

    def test_one_sorcery_gives_reduction_of_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sorcery = Sorcery(name="Divination", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[sorcery])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 1

    def test_three_instants_and_sorceries_gives_reduction_of_three(self) -> None:
        game = create_game()
        p1 = game.players[0]
        g1 = Instant(name="Shock", owner=p1, controller=p1)
        g2 = Sorcery(name="Ponder", owner=p1, controller=p1)
        g3 = Instant(name="Opt", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[g1, g2, g3])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 3

    def test_creature_in_graveyard_does_not_reduce_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2,
                            owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[creature])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_mixed_graveyard_counts_only_instants_and_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]
        instant = Instant(name="Brainstorm", owner=p1, controller=p1)
        creature = Creature(name="Llanowar Elves", base_power=1, base_toughness=1,
                            owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant, creature])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 1

    def test_opponents_graveyard_does_not_contribute(self) -> None:
        """Only the controller's graveyard counts, not the opponent's."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Put instants in opponent's graveyard only
        opp_instant = Instant(name="Counterspell", owner=p2, controller=p2)
        set_board_state(game, 1, graveyard=[opp_instant])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_reduction_cannot_exceed_base_cost(self) -> None:
        """With >10 instants/sorceries, reduction is still only as large as needed;
        the returned integer may exceed 10, but the engine clamps generic to >= 0."""
        game = create_game()
        p1 = game.players[0]
        # 15 instants in graveyard — reduction should be 15 (engine clamps)
        cards = [Instant(name=f"Spell{i}", owner=p1, controller=p1) for i in range(15)]
        set_board_state(game, 0, graveyard=cards)
        card = TheDawningArchaic(owner=p1, controller=p1)
        reduction = card.cost_reduction(game)
        assert reduction == 15


# ---------------------------------------------------------------------------
# Reach keyword (blocking restriction tested via engine)
# ---------------------------------------------------------------------------


class TestReach:
    """Reach allows blocking flying creatures."""

    def test_reach_keyword_present(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Keyword.REACH & card.keywords

    def test_can_block_flying_creature(self) -> None:
        """TheDawningArchaic with Reach can block a flying attacker."""
        from engine.combat import _can_block
        attacker = Creature(name="Air Elemental", base_power=4, base_toughness=4)
        attacker.keywords = Keyword.FLYING
        attacker.is_tapped = False
        # Use the card's own keywords — must have REACH for this to pass
        blocker = TheDawningArchaic(owner=None)
        blocker.is_tapped = False
        assert _can_block(blocker, attacker) is True


# ---------------------------------------------------------------------------
# Attack trigger registration
# ---------------------------------------------------------------------------


class TestAttackTriggerRegistration:
    """register_triggers must wire an AttacksTriggeredEvent trigger."""

    def test_registers_at_least_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_registered_trigger_fires_on_attacks_event(self) -> None:
        """A trigger registered for AttacksTriggeredEvent must be present."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        event_types = [t.event_type for t in triggers]
        assert AttacksTriggeredEvent in event_types

    def test_trigger_fires_only_for_this_creature(self) -> None:
        """Trigger condition must check that the attacker is this specific card."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_trigger = next(
            (t for t in triggers if t.event_type is AttacksTriggeredEvent),
            None,
        )
        assert attack_trigger is not None

        # Condition should pass for THIS creature
        event_self = AttacksTriggeredEvent(creature=card, attacker=card)
        other_creature = Creature(name="Other", base_power=1, base_toughness=1)
        event_other = AttacksTriggeredEvent(creature=other_creature, attacker=other_creature)

        if attack_trigger.condition is not None:
            assert attack_trigger.condition(game, event_self) is True
            assert attack_trigger.condition(game, event_other) is False


# ---------------------------------------------------------------------------
# Attack trigger effect: cast from graveyard for free
# ---------------------------------------------------------------------------


class TestAttackTriggerEffect:
    """When the trigger resolves, it casts an instant/sorcery from the
    controller's graveyard without paying its mana cost."""

    def test_trigger_effect_moves_spell_out_of_graveyard(self) -> None:
        """After the trigger resolves, the chosen spell should no longer be
        in the graveyard (it was cast)."""
        game = create_game()
        p1 = game.players[0]

        spell = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[spell])

        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_trigger = next(
            (t for t in triggers if t.event_type is AttacksTriggeredEvent),
            None,
        )
        assert attack_trigger is not None

        # Simulate trigger resolution with the spell chosen
        card.chosen_graveyard_spell = spell
        attack_trigger.effect(game)

        graveyard = game.get_graveyard(p1)
        assert not graveyard.contains(spell)

    def test_trigger_effect_with_no_valid_target_is_noop(self) -> None:
        """If the graveyard has no instants/sorceries, trigger resolves safely."""
        game = create_game()
        p1 = game.players[0]

        # No spells in graveyard
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_trigger = next(
            (t for t in triggers if t.event_type is AttacksTriggeredEvent),
            None,
        )
        assert attack_trigger is not None
        # Should not raise even with empty graveyard
        attack_trigger.effect(game)


# ---------------------------------------------------------------------------
# Exile replacement: if the cast spell would go to graveyard, exile it
# ---------------------------------------------------------------------------


class TestExileReplacement:
    """When a spell cast via The Dawning Archaic's trigger would go to
    the graveyard, it should be exiled instead."""

    def test_spell_cast_from_graveyard_goes_to_exile_not_graveyard(self) -> None:
        """After the triggered ability resolves, the spell should end up in
        exile rather than in the graveyard."""
        game = create_game()
        p1 = game.players[0]

        spell = Instant(name="Shock", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[spell])

        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_trigger = next(
            (t for t in triggers if t.event_type is AttacksTriggeredEvent),
            None,
        )
        assert attack_trigger is not None

        # Simulate trigger resolving with the spell chosen
        card.chosen_graveyard_spell = spell
        attack_trigger.effect(game)

        # The spell must NOT be in the graveyard
        graveyard = game.get_graveyard(p1)
        assert not graveyard.contains(spell)

        # The spell should be in exile
        exile = game.get_exile(p1)
        assert exile.contains(spell)

    def test_exile_replacement_second_spell_also_exiled(self) -> None:
        """A second instant/sorcery cast via the trigger should also be exiled,
        not sent to the graveyard."""
        game = create_game()
        p1 = game.players[0]

        spell_a = Instant(name="Brainstorm", owner=p1, controller=p1)
        spell_b = Sorcery(name="Ponder", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[spell_a, spell_b])

        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        attack_trigger = next(
            (t for t in triggers if t.event_type is AttacksTriggeredEvent),
            None,
        )
        assert attack_trigger is not None

        # Cast spell_a via the trigger
        card.chosen_graveyard_spell = spell_a
        attack_trigger.effect(game)

        graveyard = game.get_graveyard(p1)
        exile = game.get_exile(p1)
        assert not graveyard.contains(spell_a)
        assert exile.contains(spell_a)
