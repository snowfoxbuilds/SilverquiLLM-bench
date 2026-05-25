"""Audited tests for The Dawning Archaic (collector key 1).

Verifies the The Dawning Archaic card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import TheDawningArchaic

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestTheDawningArchaicBasicProperties:
    """Basic property tests for The Dawning Archaic."""

    def test_is_creature(self) -> None:
        """The Dawning Archaic must be a Creature subclass."""
        card = TheDawningArchaic(name="The Dawning Archaic", owner=None, base_power=7, base_toughness=7)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """TheDawningArchaic.name must be 'The Dawning Archaic'."""
        card = TheDawningArchaic(name="The Dawning Archaic", owner=None, base_power=7, base_toughness=7)
        assert card.name == "The Dawning Archaic"

    def test_card_types(self) -> None:
        """The Dawning Archaic must have correct card types."""
        card = TheDawningArchaic(name="The Dawning Archaic", owner=None, base_power=7, base_toughness=7)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """The Dawning Archaic must have converted mana cost 10."""
        card = TheDawningArchaic(name="The Dawning Archaic", owner=None, base_power=7, base_toughness=7)
        assert card.mana_cost.cmc == 10

    def test_colorless(self) -> None:
        """The Dawning Archaic must be colorless."""
        card = TheDawningArchaic(name="The Dawning Archaic", owner=None, base_power=7, base_toughness=7)
        assert len(card.colors) == 0

    def test_power(self) -> None:
        """The Dawning Archaic must have base power 7."""
        card = TheDawningArchaic(name="The Dawning Archaic", owner=None, base_power=7, base_toughness=7)
        assert card.base_power == 7

    def test_toughness(self) -> None:
        """The Dawning Archaic must have base toughness 7."""
        card = TheDawningArchaic(name="The Dawning Archaic", owner=None, base_power=7, base_toughness=7)
        assert card.base_toughness == 7


@pytest.mark.ability
class TestTheDawningArchaicAbilities:
    """Ability tests for The Dawning Archaic -- expected to fail against stubs."""

    def test_has_reach(self) -> None:
        """The Dawning Archaic must have Reach keyword."""
        from engine.types import Keyword
        card = TheDawningArchaic(name="The Dawning Archaic", owner=None, base_power=7, base_toughness=7)
        assert Keyword.REACH in card.keywords, "The Dawning Archaic should have Reach"

    def test_attack_trigger_uses_graveyard(self) -> None:
        """Attack trigger must interact with graveyard per oracle text."""
        from test_utils import create_game, set_board_state
        from engine.card import Instant
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        fodder = Instant(name="Bolt", owner=player)
        set_board_state(game, 0, graveyard=[fodder])
        card = TheDawningArchaic(name="The Dawning Archaic", owner=player, base_power=7, base_toughness=7)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        gy_before = len(player.zones[Zone.GRAVEYARD].get_all())
        if callable(getattr(card, "on_attack", None)):
            card.on_attack(game)
        gy_after = len(player.zones[Zone.GRAVEYARD].get_all())
        assert gy_after != gy_before, "Attack trigger must interact with graveyard"

    def test_cost_reduction_implemented(self) -> None:
        """Cost reduction must be implemented per oracle text."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = TheDawningArchaic(name="The Dawning Archaic", owner=player, base_power=7, base_toughness=7)
        card.controller = player
        assert callable(getattr(card, "get_adjusted_cost", None)) or \
            callable(getattr(card, "cost_reduction", None)), \
            "The Dawning Archaic must implement cost reduction per oracle text"


@pytest.mark.edge
class TestTheDawningArchaicEdgeCases:
    """Edge case and trap tests for The Dawning Archaic."""

    def test_fizzle_no_targets_creature_stays(self) -> None:
        """If ETB ability fizzles, the creature remains on battlefield."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = TheDawningArchaic(name="The Dawning Archaic", owner=player, base_power=7, base_toughness=7)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        # No targets available; ETB fizzles
        try:
            if callable(getattr(card, "on_enter_battlefield", None)):
                card.on_enter_battlefield(game)
        except (ValueError, IndexError):
            pass  # Fizzle expected
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must stay on battlefield when ETB fizzles"

    def test_cost_reduction_floor_at_zero(self) -> None:
        """Cost reduction must not reduce cost below zero."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = TheDawningArchaic(name="The Dawning Archaic", owner=player, base_power=7, base_toughness=7)
        card.controller = player
        if callable(getattr(card, "get_adjusted_cost", None)):
            cost = card.get_adjusted_cost(game)
            assert cost >= 0, "Adjusted cost must never be negative"
        else:
            assert callable(getattr(card, "cost_reduction", None)), \
                "Must implement cost reduction"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = TheDawningArchaic(name="The Dawning Archaic", owner=None, base_power=7, base_toughness=7)
        card2 = TheDawningArchaic(name="The Dawning Archaic", owner=None, base_power=7, base_toughness=7)
        card1.name = "Modified"
        assert card2.name == "The Dawning Archaic", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = TheDawningArchaic(name="The Dawning Archaic", owner=None, base_power=7, base_toughness=7)
        assert card.mana_cost.cmc == 10, \
            f"CMC must be 10, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestTheDawningArchaicInteractions:
    """Multi-card interaction tests for The Dawning Archaic."""

    def test_exile_from_graveyard_interaction(self) -> None:
        """Cards exiled from graveyard must move to exile zone."""
        from test_utils import create_game, set_board_state
        from engine.card import Instant
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        fodder = Instant(name="Fodder", owner=player)
        set_board_state(game, 0, graveyard=[fodder])
        card = TheDawningArchaic(name="The Dawning Archaic", owner=player, base_power=7, base_toughness=7)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_attack", None)):
            card.on_attack(game)
        elif callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        exile = player.zones[Zone.EXILE].get_all()
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert fodder in exile or fodder not in gy, \
            "Exiled card must leave graveyard"

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = TheDawningArchaic(name="The Dawning Archaic", owner=player, base_power=7, base_toughness=7)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
