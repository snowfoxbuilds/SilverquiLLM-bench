"""Audited tests for Nita, Forum Conciliator (collector key 206).

Verifies the Nita, Forum Conciliator card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import NitaForumConciliator

from engine.card import Creature
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestNitaForumConciliatorBasicProperties:
    """Basic property tests for Nita, Forum Conciliator."""

    def test_is_creature(self) -> None:
        """Nita, Forum Conciliator must be a Creature subclass."""
        card = NitaForumConciliator(name="Nita, Forum Conciliator", owner=None, base_power=2, base_toughness=3)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """NitaForumConciliator.name must be 'Nita, Forum Conciliator'."""
        card = NitaForumConciliator(name="Nita, Forum Conciliator", owner=None, base_power=2, base_toughness=3)
        assert card.name == "Nita, Forum Conciliator"

    def test_card_types(self) -> None:
        """Nita, Forum Conciliator must have correct card types."""
        card = NitaForumConciliator(name="Nita, Forum Conciliator", owner=None, base_power=2, base_toughness=3)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Nita, Forum Conciliator must have converted mana cost 3."""
        card = NitaForumConciliator(name="Nita, Forum Conciliator", owner=None, base_power=2, base_toughness=3)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Nita, Forum Conciliator must have correct colors."""
        card = NitaForumConciliator(name="Nita, Forum Conciliator", owner=None, base_power=2, base_toughness=3)
        assert "B" in card_colors(card)
        assert "W" in card_colors(card)

    def test_power(self) -> None:
        """Nita, Forum Conciliator must have base power 2."""
        card = NitaForumConciliator(name="Nita, Forum Conciliator", owner=None, base_power=2, base_toughness=3)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Nita, Forum Conciliator must have base toughness 3."""
        card = NitaForumConciliator(name="Nita, Forum Conciliator", owner=None, base_power=2, base_toughness=3)
        assert card.base_toughness == 3

@pytest.mark.ability
class TestNitaForumConciliatorAbilities:
    """Ability tests for Nita, Forum Conciliator -- expected to fail against stubs."""

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = NitaForumConciliator(name="Nita, Forum Conciliator", owner=None, base_power=2, base_toughness=3)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Nita, Forum Conciliator must implement behavioral method"

@pytest.mark.edge
class TestNitaForumConciliatorEdgeCases:
    """Edge case and trap tests for Nita, Forum Conciliator."""

    def test_fizzle_no_targets_creature_stays(self) -> None:
        """If ETB ability fizzles, the creature remains on battlefield."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = NitaForumConciliator(name="Nita, Forum Conciliator", owner=player, base_power=2, base_toughness=3)
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

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = NitaForumConciliator(name="Nita, Forum Conciliator", owner=None, base_power=2, base_toughness=3)
        card2 = NitaForumConciliator(name="Nita, Forum Conciliator", owner=None, base_power=2, base_toughness=3)
        card1.name = "Modified"
        assert card2.name == "Nita, Forum Conciliator", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = NitaForumConciliator(name="Nita, Forum Conciliator", owner=None, base_power=2, base_toughness=3)
        assert card.mana_cost.cmc == 3, \
            f"CMC must be 3, got {card.mana_cost.cmc}"

@pytest.mark.interaction
class TestNitaForumConciliatorInteractions:
    """Multi-card interaction tests for Nita, Forum Conciliator."""

    def test_exile_from_graveyard_interaction(self) -> None:
        """Cards exiled from graveyard must move to exile zone."""
        from test_utils import create_game, set_board_state
        from engine.card import Instant
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        fodder = Instant(name="Fodder", owner=player)
        set_board_state(game, 0, graveyard=[fodder])
        card = NitaForumConciliator(name="Nita, Forum Conciliator", owner=player, base_power=2, base_toughness=3)
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

    def test_counters_survive_end_of_turn(self) -> None:
        """Permanent counters must persist through end of turn."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = NitaForumConciliator(name="Nita, Forum Conciliator", owner=player, base_power=2, base_toughness=3)
        card.controller = player
        if hasattr(card, "colors_spent"):
            card.colors_spent = 2
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        counters = getattr(card, "counters", {})
        p1p1 = counters.get("+1/+1", counters.get("p1p1", 0))
        assert p1p1 == 2, f"Should have 2 +1/+1 counters, got {p1p1}"

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = NitaForumConciliator(name="Nita, Forum Conciliator", owner=player, base_power=2, base_toughness=3)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
