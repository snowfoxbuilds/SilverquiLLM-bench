"""Tests for SOS 1 — The Dawning Archaic.

TDD red-phase tests covering all requirements from the card spec:
  - Static properties (name, mana cost, P/T, keywords, types, supertypes)
  - Cost reduction: {1} less for each instant and sorcery in your graveyard
  - Attack trigger: may cast target instant or sorcery from graveyard free
  - Exile replacement: if the cast spell would go to graveyard, exile instead
"""

from __future__ import annotations

import pytest
from typing import Any

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_instant(name: str = "Lightning Bolt", mana_cost: str = "{R}",
                  owner: Any = None) -> Instant:
    """Create a simple instant card for test setup."""
    return Instant(name=name, mana_cost=ManaCost.parse(mana_cost), owner=owner)


def _make_sorcery(name: str = "Divination", mana_cost: str = "{2}{U}",
                  owner: Any = None) -> Sorcery:
    """Create a simple sorcery card for test setup."""
    return Sorcery(name=name, mana_cost=ManaCost.parse(mana_cost), owner=owner)


def _setup_battlefield_with_archaic(game, player_index=0):
    """Place a TheDawningArchaic on the battlefield for the given player."""
    p = game.players[player_index]
    archaic = TheDawningArchaic(owner=p, controller=p)
    archaic.summoning_sick = False
    set_board_state(game, player_index, battlefield=[archaic])
    archaic.register_triggers(game)
    return archaic


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_is_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.mana_cost == ManaCost.parse("{10}")

    def test_mana_cost_is_generic_10(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.mana_cost.generic == 10
        assert card.mana_cost.pips == {}

    def test_power(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7

    def test_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_toughness == 7

    def test_has_reach(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Keyword.REACH in card.keywords

    def test_is_legendary(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_creature_type(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_subtype_avatar(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert "Avatar" in card.subtypes


# ---------------------------------------------------------------------------
# Cost reduction
# ---------------------------------------------------------------------------


class TestTheDawningArchaicCostReduction:
    """This spell costs {1} less for each instant and sorcery in your graveyard."""

    def test_no_instants_or_sorceries_no_reduction(self) -> None:
        """With an empty graveyard, cost_reduction should return 0."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_instant_in_graveyard_reduces_by_one(self) -> None:
        """One instant in graveyard means cost is reduced by 1."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        bolt = _make_instant("Lightning Bolt", "{R}", owner=p1)
        set_board_state(game, 0, graveyard=[bolt])
        assert card.cost_reduction(game) == 1

    def test_one_sorcery_in_graveyard_reduces_by_one(self) -> None:
        """One sorcery in graveyard means cost is reduced by 1."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        div = _make_sorcery("Divination", "{2}{U}", owner=p1)
        set_board_state(game, 0, graveyard=[div])
        assert card.cost_reduction(game) == 1

    def test_multiple_instants_and_sorceries_reduces_by_count(self) -> None:
        """Three instant/sorcery cards in graveyard means reduction of 3."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        bolt = _make_instant("Lightning Bolt", "{R}", owner=p1)
        shock = _make_instant("Shock", "{R}", owner=p1)
        div = _make_sorcery("Divination", "{2}{U}", owner=p1)
        set_board_state(game, 0, graveyard=[bolt, shock, div])
        assert card.cost_reduction(game) == 3

    def test_creature_in_graveyard_does_not_count(self) -> None:
        """Non-instant/non-sorcery cards should not contribute to reduction."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2,
                        owner=p1)
        set_board_state(game, 0, graveyard=[bear])
        assert card.cost_reduction(game) == 0

    def test_mixed_graveyard_counts_only_instants_and_sorceries(self) -> None:
        """Only instants and sorceries count, not creatures or other types."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        bolt = _make_instant("Lightning Bolt", "{R}", owner=p1)
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2,
                        owner=p1)
        div = _make_sorcery("Divination", "{2}{U}", owner=p1)
        set_board_state(game, 0, graveyard=[bolt, bear, div])
        assert card.cost_reduction(game) == 2

    def test_opponent_graveyard_does_not_count(self) -> None:
        """Only YOUR graveyard matters, not opponent's."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TheDawningArchaic(owner=p1, controller=p1)
        bolt = _make_instant("Lightning Bolt", "{R}", owner=p2)
        set_board_state(game, 1, graveyard=[bolt])
        assert card.cost_reduction(game) == 0

    def test_cost_reduction_cannot_exceed_generic_cost(self) -> None:
        """Even with 10+ instants/sorceries, generic cannot go below 0.

        The engine's get_cost_reduction() clamps at generic cost (10),
        but cost_reduction() itself should return the raw count.
        """
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        # Put 12 instants in graveyard
        gy = [_make_instant(f"Spell {i}", "{R}", owner=p1) for i in range(12)]
        set_board_state(game, 0, graveyard=gy)
        # The raw cost_reduction should return the count (12)
        # The engine clamping happens in get_cost_reduction, not here
        assert card.cost_reduction(game) >= 10


# ---------------------------------------------------------------------------
# Attack trigger — basic registration
# ---------------------------------------------------------------------------


class TestTheDawningArchaicAttackTrigger:
    """Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost."""

    def test_registers_attack_trigger(self) -> None:
        """register_triggers should register a trigger for AttacksTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(archaic)
        assert len(triggers) >= 1
        attack_triggers = [
            t for t in triggers if t.event_type is AttacksTriggeredEvent
        ]
        assert len(attack_triggers) >= 1

    def test_trigger_condition_only_fires_for_self(self) -> None:
        """The trigger should only fire when The Dawning Archaic itself attacks,
        not when some other creature attacks."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(archaic)
        attack_trigger = [
            t for t in triggers if t.event_type is AttacksTriggeredEvent
        ][0]

        # Should match when the archaic attacks
        self_event = AttacksTriggeredEvent(creature=archaic, attacker=archaic)
        assert attack_trigger.condition(game, self_event) is True

        # Should NOT match when another creature attacks
        other = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1)
        other_event = AttacksTriggeredEvent(creature=other, attacker=other)
        assert attack_trigger.condition(game, other_event) is False

    def test_attack_trigger_targets_instant_in_graveyard(self) -> None:
        """The trigger should be able to target an instant card in the
        controller's graveyard and cast it without paying its mana cost."""
        game = create_game()
        p1 = game.players[0]
        archaic = _setup_battlefield_with_archaic(game, 0)
        bolt = _make_instant("Lightning Bolt", "{R}", owner=p1)
        set_board_state(game, 0, graveyard=[bolt])

        # Fire the attack trigger
        triggers = game.trigger_manager.get_triggers_for_source(archaic)
        attack_trigger = [
            t for t in triggers if t.event_type is AttacksTriggeredEvent
        ][0]

        # Script the player's choices: choose yes and the target
        from engine.player import DeterministicPlayer
        player = game.players[0]
        if isinstance(player, DeterministicPlayer):
            # Script: choose the bolt (target), choose yes to cast
            player._script.appendleft(True)
            player._script.appendleft(bolt)

        # Execute the trigger's effect
        attack_trigger.effect(game)

        # The bolt should have been cast from graveyard (either resolved
        # to graveyard/exile or still on stack). It should NOT still be
        # in the graveyard (it was cast).
        gy = game.get_graveyard(p1).get_all()
        bolt_in_gy = any(c is bolt for c in gy)
        # Either the bolt was moved to exile (replacement effect) or
        # it was cast and is on the stack or resolved
        exile = game.get_exile(p1).get_all()
        bolt_in_exile = any(c is bolt for c in exile)
        bolt_on_stack = any(
            getattr(obj, 'source', None) is bolt
            for obj in game.stack._objects
        ) if hasattr(game.stack, '_objects') else False
        # The bolt should have been removed from graveyard (cast successfully)
        assert not bolt_in_gy or bolt_in_exile or bolt_on_stack, \
            "Lightning Bolt should have been cast from graveyard"

    def test_attack_trigger_targets_sorcery_in_graveyard(self) -> None:
        """The trigger should work with sorcery cards in the graveyard too."""
        game = create_game()
        p1 = game.players[0]
        archaic = _setup_battlefield_with_archaic(game, 0)
        div = _make_sorcery("Divination", "{2}{U}", owner=p1)
        set_board_state(game, 0, graveyard=[div])

        triggers = game.trigger_manager.get_triggers_for_source(archaic)
        attack_trigger = [
            t for t in triggers if t.event_type is AttacksTriggeredEvent
        ][0]

        from engine.player import DeterministicPlayer
        player = game.players[0]
        if isinstance(player, DeterministicPlayer):
            player._script.appendleft(True)
            player._script.appendleft(div)

        attack_trigger.effect(game)

        gy = game.get_graveyard(p1).get_all()
        div_in_gy = any(c is div for c in gy)
        exile = game.get_exile(p1).get_all()
        div_in_exile = any(c is div for c in exile)
        # The sorcery should have been cast from graveyard
        assert not div_in_gy or div_in_exile, \
            "Divination should have been cast from graveyard"


# ---------------------------------------------------------------------------
# Exile replacement effect
# ---------------------------------------------------------------------------


class TestTheDawningArchaicExileReplacement:
    """If that spell would be put into your graveyard, exile it instead."""

    def test_cast_instant_from_graveyard_goes_to_exile(self) -> None:
        """An instant cast via the attack trigger should be exiled rather
        than returned to the graveyard upon resolution."""
        game = create_game()
        p1 = game.players[0]
        archaic = _setup_battlefield_with_archaic(game, 0)
        bolt = _make_instant("Lightning Bolt", "{R}", owner=p1)
        set_board_state(game, 0, graveyard=[bolt])

        triggers = game.trigger_manager.get_triggers_for_source(archaic)
        attack_trigger = [
            t for t in triggers if t.event_type is AttacksTriggeredEvent
        ][0]

        from engine.player import DeterministicPlayer
        player = game.players[0]
        if isinstance(player, DeterministicPlayer):
            player._script.appendleft(True)
            player._script.appendleft(bolt)

        attack_trigger.effect(game)

        # Resolve any items on the stack
        from engine.casting import resolve_top
        while not game.stack.is_empty():
            resolve_top(game)

        # The bolt should be in exile, NOT in the graveyard
        gy = game.get_graveyard(p1).get_all()
        exile = game.get_exile(p1).get_all()

        bolt_in_gy = any(c is bolt for c in gy)
        bolt_in_exile = any(c is bolt for c in exile)

        assert bolt_in_exile, "Lightning Bolt should be in exile after resolution"
        assert not bolt_in_gy, "Lightning Bolt should NOT be in graveyard after resolution"

    def test_cast_sorcery_from_graveyard_goes_to_exile(self) -> None:
        """A sorcery cast via the attack trigger should be exiled rather
        than returned to the graveyard upon resolution."""
        game = create_game()
        p1 = game.players[0]
        archaic = _setup_battlefield_with_archaic(game, 0)
        div = _make_sorcery("Divination", "{2}{U}", owner=p1)
        set_board_state(game, 0, graveyard=[div])

        triggers = game.trigger_manager.get_triggers_for_source(archaic)
        attack_trigger = [
            t for t in triggers if t.event_type is AttacksTriggeredEvent
        ][0]

        from engine.player import DeterministicPlayer
        player = game.players[0]
        if isinstance(player, DeterministicPlayer):
            player._script.appendleft(True)
            player._script.appendleft(div)

        attack_trigger.effect(game)

        from engine.casting import resolve_top
        while not game.stack.is_empty():
            resolve_top(game)

        gy = game.get_graveyard(p1).get_all()
        exile = game.get_exile(p1).get_all()

        div_in_gy = any(c is div for c in gy)
        div_in_exile = any(c is div for c in exile)

        assert div_in_exile, "Divination should be in exile after resolution"
        assert not div_in_gy, "Divination should NOT be in graveyard after resolution"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestTheDawningArchaicEdgeCases:
    """Edge cases for The Dawning Archaic."""

    def test_empty_graveyard_trigger_does_not_error(self) -> None:
        """If there are no instants or sorceries in the graveyard when the
        trigger fires, the effect should handle it gracefully (no crash)."""
        game = create_game()
        p1 = game.players[0]
        archaic = _setup_battlefield_with_archaic(game, 0)

        triggers = game.trigger_manager.get_triggers_for_source(archaic)
        attack_trigger = [
            t for t in triggers if t.event_type is AttacksTriggeredEvent
        ][0]

        # No graveyard cards — the effect should not raise
        attack_trigger.effect(game)

    def test_creature_in_graveyard_is_not_valid_target(self) -> None:
        """The attack trigger should only target instant or sorcery cards,
        not creatures or other card types."""
        game = create_game()
        p1 = game.players[0]
        archaic = _setup_battlefield_with_archaic(game, 0)
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1)
        set_board_state(game, 0, graveyard=[bear])

        triggers = game.trigger_manager.get_triggers_for_source(archaic)
        attack_trigger = [
            t for t in triggers if t.event_type is AttacksTriggeredEvent
        ][0]

        # The bear should not be a valid target. The effect should either
        # skip (no valid target) or the filter should reject it.
        # We script the player to pick the bear to see if it's rejected.
        from engine.player import DeterministicPlayer
        player = game.players[0]
        if isinstance(player, DeterministicPlayer):
            player._script.appendleft(bear)

        # Execute the trigger effect — should not cast the bear
        attack_trigger.effect(game)

        # The bear should remain in the graveyard
        gy = game.get_graveyard(p1).get_all()
        assert any(c is bear for c in gy), \
            "Creature card should remain in graveyard — not a valid target"

    def test_you_may_choose_not_to_cast(self) -> None:
        """'You may cast' is optional — the player can decline."""
        game = create_game()
        p1 = game.players[0]
        archaic = _setup_battlefield_with_archaic(game, 0)
        bolt = _make_instant("Lightning Bolt", "{R}", owner=p1)
        set_board_state(game, 0, graveyard=[bolt])

        triggers = game.trigger_manager.get_triggers_for_source(archaic)
        attack_trigger = [
            t for t in triggers if t.event_type is AttacksTriggeredEvent
        ][0]

        from engine.player import DeterministicPlayer
        player = game.players[0]
        if isinstance(player, DeterministicPlayer):
            # Script: decline to cast
            player._script.appendleft(False)
            player._script.appendleft(bolt)

        attack_trigger.effect(game)

        # The bolt should remain in the graveyard since we declined
        gy = game.get_graveyard(p1).get_all()
        assert any(c is bolt for c in gy), \
            "Lightning Bolt should remain in graveyard when player declines"

    def test_cast_without_paying_mana_cost(self) -> None:
        """The spell should be cast without paying its mana cost — the player
        should NOT need mana in their pool."""
        game = create_game()
        p1 = game.players[0]
        archaic = _setup_battlefield_with_archaic(game, 0)
        # An expensive instant that the player cannot afford normally
        expensive = _make_instant("Expensive Spell", "{5}{U}{U}", owner=p1)
        set_board_state(game, 0, graveyard=[expensive])
        # Explicitly empty the mana pool
        p1.mana_pool.empty()

        triggers = game.trigger_manager.get_triggers_for_source(archaic)
        attack_trigger = [
            t for t in triggers if t.event_type is AttacksTriggeredEvent
        ][0]

        from engine.player import DeterministicPlayer
        player = game.players[0]
        if isinstance(player, DeterministicPlayer):
            player._script.appendleft(True)
            player._script.appendleft(expensive)

        # Should not raise despite no mana
        attack_trigger.effect(game)

        # The expensive spell should have been cast (removed from graveyard)
        gy = game.get_graveyard(p1).get_all()
        assert not any(c is expensive for c in gy), \
            "Expensive spell should have been cast from graveyard without paying mana"
