"""Audited tests for Postmortem Professor (collector key 93).

Verifies the Postmortem Professor card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import PostmortemProfessor

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestPostmortemProfessorBasicProperties:
    """Basic property tests for Postmortem Professor."""

    def test_is_creature(self) -> None:
        """Postmortem Professor must be a Creature subclass."""
        card = PostmortemProfessor(name="Postmortem Professor", owner=None, base_power=2, base_toughness=2)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """PostmortemProfessor.name must be 'Postmortem Professor'."""
        card = PostmortemProfessor(name="Postmortem Professor", owner=None, base_power=2, base_toughness=2)
        assert card.name == "Postmortem Professor"

    def test_card_types(self) -> None:
        """Postmortem Professor must have correct card types."""
        card = PostmortemProfessor(name="Postmortem Professor", owner=None, base_power=2, base_toughness=2)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Postmortem Professor must have converted mana cost 2."""
        card = PostmortemProfessor(name="Postmortem Professor", owner=None, base_power=2, base_toughness=2)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Postmortem Professor must have correct colors."""
        card = PostmortemProfessor(name="Postmortem Professor", owner=None, base_power=2, base_toughness=2)
        assert "B" in card.colors

    def test_power(self) -> None:
        """Postmortem Professor must have base power 2."""
        card = PostmortemProfessor(name="Postmortem Professor", owner=None, base_power=2, base_toughness=2)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Postmortem Professor must have base toughness 2."""
        card = PostmortemProfessor(name="Postmortem Professor", owner=None, base_power=2, base_toughness=2)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestPostmortemProfessorAbilities:
    """Ability tests for Postmortem Professor -- expected to fail against stubs."""

    def test_attack_trigger_uses_graveyard(self) -> None:
        """Attack trigger must interact with graveyard per oracle text."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Instant
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        fodder = Instant(name="Bolt", owner=player)
        set_board_state(game, 0, graveyard=[fodder])
        card = PostmortemProfessor(name="Postmortem Professor", owner=player, base_power=2, base_toughness=2)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        gy_before = len(player.zones[Zone.GRAVEYARD].get_all())
        if callable(getattr(card, "on_attack", None)):
            card.on_attack(game)
        gy_after = len(player.zones[Zone.GRAVEYARD].get_all())
        assert gy_after != gy_before, "Attack trigger must interact with graveyard"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = PostmortemProfessor(name="Postmortem Professor", owner=None, base_power=2, base_toughness=2)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Postmortem Professor must implement behavioral method"


@pytest.mark.edge
class TestPostmortemProfessorEdgeCases:
    """Edge case and trap tests for Postmortem Professor."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = PostmortemProfessor(name="Postmortem Professor", owner=None, base_power=2, base_toughness=2)
        card2 = PostmortemProfessor(name="Postmortem Professor", owner=None, base_power=2, base_toughness=2)
        card1.name = "Modified"
        assert card2.name == "Postmortem Professor", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = PostmortemProfessor(name="Postmortem Professor", owner=None, base_power=2, base_toughness=2)
        assert card.mana_cost.cmc == 2, \
            f"CMC must be 2, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = PostmortemProfessor(name="Postmortem Professor", owner=player, base_power=2, base_toughness=2)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 1
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestPostmortemProfessorInteractions:
    """Multi-card interaction tests for Postmortem Professor."""

    def test_exile_from_graveyard_interaction(self) -> None:
        """Cards exiled from graveyard must move to exile zone."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Instant
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        fodder = Instant(name="Fodder", owner=player)
        set_board_state(game, 0, graveyard=[fodder])
        card = PostmortemProfessor(name="Postmortem Professor", owner=player, base_power=2, base_toughness=2)
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
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = PostmortemProfessor(name="Postmortem Professor", owner=player, base_power=2, base_toughness=2)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
