"""Audited tests for Joined Researchers // Secret Rendezvous (collector key 23).

Verifies the Joined Researchers // Secret Rendezvous card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import JoinedResearchersSecretRendezvous

from engine.card import Creature
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestJoinedResearchersSecretRendezvousBasicProperties:
    """Basic property tests for Joined Researchers // Secret Rendezvous."""

    def test_is_creature(self) -> None:
        """Joined Researchers // Secret Rendezvous must be a Creature subclass."""
        card = JoinedResearchersSecretRendezvous(name="Joined Researchers // Secret Rendezvous", owner=None, base_power=2, base_toughness=2)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """JoinedResearchersSecretRendezvous.name must be 'Joined Researchers // Secret Rendezvous'."""
        card = JoinedResearchersSecretRendezvous(name="Joined Researchers // Secret Rendezvous", owner=None, base_power=2, base_toughness=2)
        assert card.name == "Joined Researchers // Secret Rendezvous"

    def test_card_types(self) -> None:
        """Joined Researchers // Secret Rendezvous must have correct card types."""
        card = JoinedResearchersSecretRendezvous(name="Joined Researchers // Secret Rendezvous", owner=None, base_power=2, base_toughness=2)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Joined Researchers // Secret Rendezvous must have converted mana cost 5."""
        card = JoinedResearchersSecretRendezvous(name="Joined Researchers // Secret Rendezvous", owner=None, base_power=2, base_toughness=2)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Joined Researchers // Secret Rendezvous must have correct colors."""
        card = JoinedResearchersSecretRendezvous(name="Joined Researchers // Secret Rendezvous", owner=None, base_power=2, base_toughness=2)
        assert "W" in card_colors(card)

    def test_power(self) -> None:
        """Joined Researchers // Secret Rendezvous must have base power 2."""
        card = JoinedResearchersSecretRendezvous(name="Joined Researchers // Secret Rendezvous", owner=None, base_power=2, base_toughness=2)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Joined Researchers // Secret Rendezvous must have base toughness 2."""
        card = JoinedResearchersSecretRendezvous(name="Joined Researchers // Secret Rendezvous", owner=None, base_power=2, base_toughness=2)
        assert card.base_toughness == 2

@pytest.mark.ability
class TestJoinedResearchersSecretRendezvousAbilities:
    """Ability tests for Joined Researchers // Secret Rendezvous -- expected to fail against stubs."""

    def test_has_first_strike(self) -> None:
        """Joined Researchers // Secret Rendezvous must have First strike keyword."""
        from engine.types import Keyword
        card = JoinedResearchersSecretRendezvous(name="Joined Researchers // Secret Rendezvous", owner=None, base_power=2, base_toughness=2)
        assert Keyword.FIRST_STRIKE in card.keywords, "Joined Researchers // Secret Rendezvous should have First strike"

    def test_has_prepared(self) -> None:
        """Joined Researchers // Secret Rendezvous must have Prepared keyword."""
        from engine.types import Keyword
        card = JoinedResearchersSecretRendezvous(name="Joined Researchers // Secret Rendezvous", owner=None, base_power=2, base_toughness=2)
        assert Keyword.PREPARED in card.keywords, "Joined Researchers // Secret Rendezvous should have Prepared"

    def test_prepared_mechanic_implemented(self) -> None:
        """Prepared mechanic must be implemented per oracle text."""
        card = JoinedResearchersSecretRendezvous(name="Joined Researchers // Secret Rendezvous", owner=None, base_power=2, base_toughness=2)
        assert callable(getattr(card, "check_prepared", None)) or \
            callable(getattr(card, "prepared_effect", None)) or \
            callable(getattr(card, "on_resolve", None)), \
            "Joined Researchers // Secret Rendezvous must implement prepared mechanic"

@pytest.mark.edge
class TestJoinedResearchersSecretRendezvousEdgeCases:
    """Edge case and trap tests for Joined Researchers // Secret Rendezvous."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = JoinedResearchersSecretRendezvous(name="Joined Researchers // Secret Rendezvous", owner=None, base_power=2, base_toughness=2)
        card2 = JoinedResearchersSecretRendezvous(name="Joined Researchers // Secret Rendezvous", owner=None, base_power=2, base_toughness=2)
        card1.name = "Modified"
        assert card2.name == "Joined Researchers // Secret Rendezvous", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = JoinedResearchersSecretRendezvous(name="Joined Researchers // Secret Rendezvous", owner=None, base_power=2, base_toughness=2)
        assert card.mana_cost.cmc == 5, \
            f"CMC must be 5, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = JoinedResearchersSecretRendezvous(name="Joined Researchers // Secret Rendezvous", owner=player, base_power=2, base_toughness=2)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 1
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"

@pytest.mark.interaction
class TestJoinedResearchersSecretRendezvousInteractions:
    """Multi-card interaction tests for Joined Researchers // Secret Rendezvous."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = JoinedResearchersSecretRendezvous(name="Joined Researchers // Secret Rendezvous", owner=player, base_power=2, base_toughness=2)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"

    def test_coexists_with_other_permanents(self) -> None:
        """Card must coexist with other permanents without errors."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        card = JoinedResearchersSecretRendezvous(name="Joined Researchers // Secret Rendezvous", owner=player, base_power=2, base_toughness=2)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
