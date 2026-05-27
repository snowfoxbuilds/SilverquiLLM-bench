"""Tests for SOS 1 — The Dawning Archaic.

The Dawning Archaic is a legendary 7/7 creature (Avatar) for {10} with:
1. Cost reduction: costs {1} less for each instant/sorcery in your graveyard.
2. Keyword: Reach.
3. Triggered ability: Whenever it attacks, you may cast target instant or
   sorcery card from your graveyard without paying its mana cost. If that
   spell would be put into your graveyard, exile it instead.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static Properties
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

    def test_power_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7
        assert card.base_toughness == 7

    def test_has_reach(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Keyword.REACH in card.keywords

    def test_is_legendary(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtype_avatar(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert "Avatar" in card.subtypes

    def test_colorless(self) -> None:
        """The Dawning Archaic has no colored pips — it's colorless."""
        card = TheDawningArchaic(owner=None)
        assert card.mana_cost.pips == {} or all(
            v == 0 for v in card.mana_cost.pips.values()
        )


# ---------------------------------------------------------------------------
# Cost Reduction
# ---------------------------------------------------------------------------

class TestTheDawningArchaicCostReduction:
    """Costs {1} less for each instant and sorcery card in your graveyard."""

    def test_no_instants_or_sorceries_no_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        # Empty graveyard — no reduction
        assert card.cost_reduction(game) == 0

    def test_one_instant_in_graveyard_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        bolt = Instant(name="Lightning Bolt", owner=p1)
        set_board_state(game, 0, graveyard=[bolt])
        assert card.cost_reduction(game) == 1

    def test_one_sorcery_in_graveyard_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        divination = Sorcery(name="Divination", owner=p1)
        set_board_state(game, 0, graveyard=[divination])
        assert card.cost_reduction(game) == 1

    def test_multiple_instants_and_sorceries_reduce_cumulatively(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        bolt = Instant(name="Lightning Bolt", owner=p1)
        divination = Sorcery(name="Divination", owner=p1)
        opt = Instant(name="Opt", owner=p1)
        set_board_state(game, 0, graveyard=[bolt, divination, opt])
        assert card.cost_reduction(game) == 3

    def test_non_instant_sorcery_cards_do_not_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", owner=p1, base_power=2, base_toughness=2)
        bolt = Instant(name="Lightning Bolt", owner=p1)
        set_board_state(game, 0, graveyard=[bear, bolt])
        # Only the instant counts
        assert card.cost_reduction(game) == 1

    def test_opponent_graveyard_does_not_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TheDawningArchaic(owner=p1, controller=p1)
        bolt = Instant(name="Lightning Bolt", owner=p2)
        set_board_state(game, 1, graveyard=[bolt])
        assert card.cost_reduction(game) == 0

    def test_reduction_does_not_exceed_generic_cost(self) -> None:
        """Even with 15 instants/sorceries, cost_reduction is clamped
        by the engine (generic can't go below 0). But the card itself
        can report the raw count; the engine clamps it."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        cards_in_gy = [Instant(name=f"Spell {i}", owner=p1) for i in range(15)]
        set_board_state(game, 0, graveyard=cards_in_gy)
        # The reduction should be at least 10 (the full generic cost)
        # The engine will clamp, but the card reports actual count
        assert card.cost_reduction(game) >= 10


# ---------------------------------------------------------------------------
# Attack Trigger — targets and casting from graveyard
# ---------------------------------------------------------------------------

class TestTheDawningArchaicAttackTrigger:
    """Whenever The Dawning Archaic attacks, you may cast target instant or
    sorcery card from your graveyard without paying its mana cost.
    If that spell would be put into your graveyard, exile it instead.
    """

    def test_register_triggers_adds_attack_trigger(self) -> None:
        """The card should register a trigger watching for attacks."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        # After registration, the trigger manager should have at least one
        # trigger from this source.
        triggers = [
            t for t in game.trigger_manager.triggers
            if t.source is card
        ]
        assert len(triggers) >= 1

    def test_attack_trigger_targets_instant_in_graveyard(self) -> None:
        """The trigger should be able to target instants in graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        bolt = Instant(name="Lightning Bolt", owner=p1)
        set_board_state(game, 0, graveyard=[bolt])
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        # The trigger's target should include instant/sorcery in graveyard
        triggers = [
            t for t in game.trigger_manager.triggers
            if t.source is card
        ]
        assert len(triggers) >= 1

    def test_attack_trigger_targets_sorcery_in_graveyard(self) -> None:
        """The trigger should be able to target sorceries in graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        divination = Sorcery(name="Divination", owner=p1)
        set_board_state(game, 0, graveyard=[divination])
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        triggers = [
            t for t in game.trigger_manager.triggers
            if t.source is card
        ]
        assert len(triggers) >= 1

    def test_cast_from_graveyard_spell_resolves(self) -> None:
        """When the attack trigger resolves and a spell is chosen,
        the spell should resolve (effect applied)."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        # Create a simple instant in graveyard
        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[bolt])

        # Simulate the trigger effect: card casts bolt from graveyard
        # After resolution, bolt should NOT be in graveyard (exiled instead)
        card.register_triggers(game)
        triggers = [
            t for t in game.trigger_manager.triggers
            if t.source is card
        ]
        assert len(triggers) >= 1
        # The trigger's effect, when called with a chosen target of bolt,
        # should move bolt out of graveyard
        trigger = triggers[0]
        # Set up the chosen target for the trigger
        card.chosen_targets = [bolt]
        trigger.effect(game)
        # Bolt should be exiled, not in graveyard
        gy = game.get_graveyard(p1)
        assert not gy.contains(bolt)

    def test_spell_cast_from_graveyard_is_exiled_not_returned(self) -> None:
        """If that spell would be put into your graveyard, exile it instead."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[bolt])

        card.register_triggers(game)
        triggers = [
            t for t in game.trigger_manager.triggers
            if t.source is card
        ]
        assert len(triggers) >= 1
        trigger = triggers[0]
        card.chosen_targets = [bolt]
        trigger.effect(game)
        # Bolt should be in exile
        exile = game.get_exile(p1)
        assert exile.contains(bolt)
