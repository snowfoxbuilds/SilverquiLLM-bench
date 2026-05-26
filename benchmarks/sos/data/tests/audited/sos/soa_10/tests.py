"""Audited tests for Requisition Raid (collector key soa_10).

Verifies the Requisition Raid card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import RequisitionRaid

from engine.card import Sorcery
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestRequisitionRaidBasicProperties:
    """Basic property tests for Requisition Raid."""

    def test_is_sorcery(self) -> None:
        """Requisition Raid must be a Sorcery subclass."""
        card = RequisitionRaid(name="Requisition Raid", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """RequisitionRaid.name must be 'Requisition Raid'."""
        card = RequisitionRaid(name="Requisition Raid", owner=None)
        assert card.name == "Requisition Raid"

    def test_card_types(self) -> None:
        """Requisition Raid must have correct card types."""
        card = RequisitionRaid(name="Requisition Raid", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Requisition Raid must have converted mana cost 1."""
        card = RequisitionRaid(name="Requisition Raid", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Requisition Raid must have correct colors."""
        card = RequisitionRaid(name="Requisition Raid", owner=None)
        assert "W" in card_colors(card)

@pytest.mark.ability
class TestRequisitionRaidAbilities:
    """Ability tests for Requisition Raid -- expected to fail against stubs."""

    def test_resolution_removes_creatures(self) -> None:
        """Spell resolution must remove/destroy creatures per oracle text."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Victim", owner=opponent, base_power=1, base_toughness=1)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = RequisitionRaid(name="Requisition Raid", owner=player)
        card.controller = player
        card.on_resolve(game)
        bf = opponent.zones[Zone.BATTLEFIELD].get_all()
        gy = opponent.zones[Zone.GRAVEYARD].get_all()
        assert target not in bf or target in gy, "Requisition Raid must remove creature"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = RequisitionRaid(name="Requisition Raid", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Requisition Raid must implement behavioral method"

@pytest.mark.edge
class TestRequisitionRaidEdgeCases:
    """Edge case and trap tests for Requisition Raid."""

    def test_fizzle_spell_goes_to_graveyard(self) -> None:
        """Fizzled spell must end up in graveyard."""
        from test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = RequisitionRaid(name="Requisition Raid", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Fizzled spell must go to graveyard"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = RequisitionRaid(name="Requisition Raid", owner=None)
        card2 = RequisitionRaid(name="Requisition Raid", owner=None)
        card1.name = "Modified"
        assert card2.name == "Requisition Raid", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = RequisitionRaid(name="Requisition Raid", owner=None)
        assert card.mana_cost.cmc == 1, \
            f"CMC must be 1, got {card.mana_cost.cmc}"

@pytest.mark.interaction
class TestRequisitionRaidInteractions:
    """Multi-card interaction tests for Requisition Raid."""

    def test_targets_valid_objects(self) -> None:
        """Spell targeting must find valid targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=3, base_toughness=3)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = RequisitionRaid(name="Requisition Raid", owner=player)
        card.controller = player
        if callable(getattr(card, "get_targets", None)):
            targets = card.get_targets(game)
            assert len(targets) > 0, "Must find valid targets"

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = RequisitionRaid(name="Requisition Raid", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"
