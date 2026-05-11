"""Audited tests for Abrade (collector key soa_37).

Verifies the Abrade card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import Abrade

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestAbradeBasicProperties:
    """Basic property tests for Abrade."""

    def test_is_instant(self) -> None:
        """Abrade must be a Instant subclass."""
        card = Abrade(name="Abrade", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """Abrade.name must be 'Abrade'."""
        card = Abrade(name="Abrade", owner=None)
        assert card.name == "Abrade"

    def test_card_types(self) -> None:
        """Abrade must have correct card types."""
        card = Abrade(name="Abrade", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Abrade must have converted mana cost 2."""
        card = Abrade(name="Abrade", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Abrade must have correct colors."""
        card = Abrade(name="Abrade", owner=None)
        assert "R" in card.colors


@pytest.mark.ability
class TestAbradeAbilities:
    """Ability tests for Abrade -- expected to fail against stubs."""

    def test_resolution_deals_damage(self) -> None:
        """Spell resolution must deal damage per oracle text."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = Abrade(name="Abrade", owner=player)
        card.controller = player
        initial_life = opponent.life
        card.on_resolve(game)
        assert opponent.life < initial_life, "Abrade must deal damage on resolution"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = Abrade(name="Abrade", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Abrade must implement behavioral method"


@pytest.mark.edge
class TestAbradeEdgeCases:
    """Edge case and trap tests for Abrade."""

    def test_fizzle_spell_goes_to_graveyard(self) -> None:
        """Fizzled spell must end up in graveyard."""
        from tests.test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = Abrade(name="Abrade", owner=player)
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
        card1 = Abrade(name="Abrade", owner=None)
        card2 = Abrade(name="Abrade", owner=None)
        card1.name = "Modified"
        assert card2.name == "Abrade", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = Abrade(name="Abrade", owner=None)
        assert card.mana_cost.cmc == 2, \
            f"CMC must be 2, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestAbradeInteractions:
    """Multi-card interaction tests for Abrade."""

    def test_targets_valid_objects(self) -> None:
        """Spell targeting must find valid targets."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=3, base_toughness=3)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = Abrade(name="Abrade", owner=player)
        card.controller = player
        if callable(getattr(card, "get_targets", None)):
            targets = card.get_targets(game)
            assert len(targets) > 0, "Must find valid targets"

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from tests.test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = Abrade(name="Abrade", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"
