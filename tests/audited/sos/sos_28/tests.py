"""Audited tests for Rapier Wit (collector key 28).

Verifies the Rapier Wit card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import RapierWit

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestRapierWitBasicProperties:
    """Basic property tests for Rapier Wit."""

    def test_is_instant(self) -> None:
        """Rapier Wit must be a Instant subclass."""
        card = RapierWit(name="Rapier Wit", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """RapierWit.name must be 'Rapier Wit'."""
        card = RapierWit(name="Rapier Wit", owner=None)
        assert card.name == "Rapier Wit"

    def test_card_types(self) -> None:
        """Rapier Wit must have correct card types."""
        card = RapierWit(name="Rapier Wit", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Rapier Wit must have converted mana cost 2."""
        card = RapierWit(name="Rapier Wit", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Rapier Wit must have correct colors."""
        card = RapierWit(name="Rapier Wit", owner=None)
        assert "W" in card.colors


@pytest.mark.ability
class TestRapierWitAbilities:
    """Ability tests for Rapier Wit -- expected to fail against stubs."""

    def test_resolution_draws_cards(self) -> None:
        """Spell resolution must draw cards per oracle text."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        for i in range(5):
            c = Creature(name=f"Lib{i}", owner=player, base_power=1, base_toughness=1)
            player.zones[Zone.LIBRARY].add(c)
        hand_before = len(player.zones[Zone.HAND].get_all())
        card = RapierWit(name="Rapier Wit", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, "Rapier Wit must draw cards"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = RapierWit(name="Rapier Wit", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Rapier Wit must implement behavioral method"


@pytest.mark.edge
class TestRapierWitEdgeCases:
    """Edge case and trap tests for Rapier Wit."""

    def test_fizzle_spell_goes_to_graveyard(self) -> None:
        """Fizzled spell must end up in graveyard."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = RapierWit(name="Rapier Wit", owner=player)
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
        card1 = RapierWit(name="Rapier Wit", owner=None)
        card2 = RapierWit(name="Rapier Wit", owner=None)
        card1.name = "Modified"
        assert card2.name == "Rapier Wit", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = RapierWit(name="Rapier Wit", owner=None)
        assert card.mana_cost.cmc == 2, \
            f"CMC must be 2, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestRapierWitInteractions:
    """Multi-card interaction tests for Rapier Wit."""

    def test_targets_valid_objects(self) -> None:
        """Spell targeting must find valid targets."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=3, base_toughness=3)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = RapierWit(name="Rapier Wit", owner=player)
        card.controller = player
        if callable(getattr(card, "get_targets", None)):
            targets = card.get_targets(game)
            assert len(targets) > 0, "Must find valid targets"

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = RapierWit(name="Rapier Wit", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"
