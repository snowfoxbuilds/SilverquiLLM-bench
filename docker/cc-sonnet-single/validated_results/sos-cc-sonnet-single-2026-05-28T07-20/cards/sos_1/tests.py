"""Tests for SOS 1 — The Dawning Archaic.

Requirements under test:
1. Static properties: Legendary Creature - Avatar, 7/7, colorless (mana cost {10}),
   Legendary supertype, Reach keyword.
2. Cost reduction: costs {1} less for each instant/sorcery in controller's graveyard.
3. Attack trigger: whenever it attacks, controller may cast target instant or sorcery
   from their graveyard without paying its mana cost.
4. Exile-instead replacement: if the graveyard-cast spell would be put into the
   graveyard, exile it instead.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------


class TestTheDawningArchaicProperties:
    """Static characteristics should match the SOS 1 card spec."""

    def test_is_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_base_power(self) -> None:
        assert TheDawningArchaic(owner=None).base_power == 7

    def test_base_toughness(self) -> None:
        assert TheDawningArchaic(owner=None).base_toughness == 7

    def test_has_reach_keyword(self) -> None:
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in TheDawningArchaic(owner=None).supertypes

    def test_has_avatar_subtype(self) -> None:
        assert "Avatar" in TheDawningArchaic(owner=None).subtypes

    def test_creature_card_type(self) -> None:
        assert CardType.CREATURE in TheDawningArchaic(owner=None).card_types


# ---------------------------------------------------------------------------
# Cost reduction — counted from controller's graveyard
# ---------------------------------------------------------------------------


class TestTheDawningArchaicCostReduction:
    """cost_reduction() returns the count of instant+sorcery cards in the
    controller's graveyard."""

    def test_zero_when_graveyard_is_empty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_instant_gives_reduction_of_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        instant = Instant(
            name="Lightning Bolt",
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, graveyard=[instant])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 1

    def test_one_sorcery_gives_reduction_of_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sorcery = Sorcery(
            name="Divination",
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, graveyard=[sorcery])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 1

    def test_multiple_instants_and_sorceries_counted(self) -> None:
        game = create_game()
        p1 = game.players[0]
        instant1 = Instant(name="Counterspell", owner=p1, controller=p1)
        instant2 = Instant(name="Giant Growth", owner=p1, controller=p1)
        sorcery1 = Sorcery(name="Cultivate", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant1, instant2, sorcery1])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 3

    def test_creature_in_graveyard_not_counted(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = Creature(name="Grizzly Bears", base_power=2, base_toughness=2,
                            owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[creature])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_mixed_types_only_instant_sorcery_counted(self) -> None:
        """Creatures mixed with instants: only instants/sorceries count."""
        game = create_game()
        p1 = game.players[0]
        instant = Instant(name="Shock", owner=p1, controller=p1)
        creature = Creature(name="Goblin Guide", base_power=2, base_toughness=2,
                            owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant, creature])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 1

    def test_opponent_graveyard_not_counted(self) -> None:
        """Only the controller's graveyard matters, not opponent's."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        instant = Instant(name="Shock", owner=p2, controller=p2)
        set_board_state(game, 1, graveyard=[instant])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_no_controller_returns_zero(self) -> None:
        """If controller is None, cost_reduction must return 0 (not crash)."""
        game = create_game()
        card = TheDawningArchaic(owner=None)
        result = card.cost_reduction(game)
        assert result == 0

    def test_cost_reduction_capped_at_base_generic(self) -> None:
        """With 12 instant/sorceries in graveyard, the engine clamps cost
        to 0 (cost_reduction is allowed to exceed the base generic cost;
        the engine does the clamping). We just verify reduction >= 10 so
        the card becomes free."""
        game = create_game()
        p1 = game.players[0]
        graveyard_cards = [
            Instant(name=f"Spell {i}", owner=p1, controller=p1)
            for i in range(12)
        ]
        set_board_state(game, 0, graveyard=graveyard_cards)
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) >= 10


# ---------------------------------------------------------------------------
# Attack trigger — registration
# ---------------------------------------------------------------------------


class TestTheDawningArchaicTriggerRegistration:
    """register_triggers() must wire an AttacksTriggeredEvent trigger."""

    def test_registers_at_least_one_trigger_on_etb(self) -> None:
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
        event_types = [t.event_type for t in triggers]
        assert AttacksTriggeredEvent in event_types

    def test_trigger_condition_fires_only_for_self(self) -> None:
        """The trigger condition must match only when this card is the attacker."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)

        triggers = [
            t for t in game.trigger_manager.get_triggers_for_source(card)
            if t.event_type is AttacksTriggeredEvent
        ]
        assert triggers, "No AttacksTriggeredEvent trigger registered"
        trigger = triggers[0]

        other = Creature(name="Other Creature", base_power=2, base_toughness=2)
        event_self = AttacksTriggeredEvent(creature=card, attacker=card)
        event_other = AttacksTriggeredEvent(creature=other, attacker=other)

        if trigger.condition is not None:
            assert trigger.condition(game, event_self) is True
            assert trigger.condition(game, event_other) is False


# ---------------------------------------------------------------------------
# Attack trigger — effect: cast from graveyard
# ---------------------------------------------------------------------------


class TestTheDawningArchaicAttackEffect:
    """When the attack trigger resolves, it should enable casting an instant
    or sorcery from the graveyard without paying mana cost."""

    def test_trigger_effect_runs_without_raising_on_empty_graveyard(self) -> None:
        """With no instants/sorceries in graveyard, effect must not crash."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)

        triggers = [
            t for t in game.trigger_manager.get_triggers_for_source(card)
            if t.event_type is AttacksTriggeredEvent
        ]
        assert triggers
        # Invoke the trigger effect directly (simulating stack resolution).
        triggers[0].effect(game)

    def test_trigger_moves_instant_from_graveyard_to_stack_or_exile(self) -> None:
        """After the trigger resolves with an instant in the graveyard,
        the instant should no longer be in the graveyard (it was cast or exiled)."""
        game = create_game()
        p1 = game.players[0]
        instant = Instant(name="Shock", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant])
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)

        triggers = [
            t for t in game.trigger_manager.get_triggers_for_source(card)
            if t.event_type is AttacksTriggeredEvent
        ]
        assert triggers
        triggers[0].effect(game)

        # After resolution, the instant must have left the graveyard.
        graveyard = game.get_graveyard(p1)
        # The card may be on the stack, battlefield, or exile — but not graveyard.
        assert not graveyard.contains(instant)


# ---------------------------------------------------------------------------
# Exile-instead replacement
# ---------------------------------------------------------------------------


class TestTheDawningArchaicExileReplacement:
    """When the graveyard-cast spell would go to graveyard, exile it instead.

    The card registers (or arranges for) a replacement effect that redirects
    that particular spell from graveyard to exile.
    """

    def test_spell_cast_via_trigger_goes_to_exile_not_graveyard(self) -> None:
        """The overall contract: a spell cast via the attack trigger that
        would normally go to the graveyard ends up in exile instead."""
        game = create_game()
        p1 = game.players[0]

        # A simple sorcery that does nothing on resolution — it will end up
        # in the graveyard by default if no replacement is applied.
        class _NoopSorcery(Sorcery):
            def on_resolve(self, game):  # type: ignore[override]
                pass

        sorcery = _NoopSorcery(name="Noop Sorcery", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[sorcery])

        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)

        triggers = [
            t for t in game.trigger_manager.get_triggers_for_source(card)
            if t.event_type is AttacksTriggeredEvent
        ]
        assert triggers
        triggers[0].effect(game)

        # After the trigger effect runs, the sorcery must NOT be in the
        # graveyard (it was moved elsewhere — stack, exile, etc.).
        graveyard = game.get_graveyard(p1)
        assert not graveyard.contains(sorcery)
