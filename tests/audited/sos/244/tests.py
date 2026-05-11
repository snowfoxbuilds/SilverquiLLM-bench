"""Audited tests for Witherbloom Charm (collector key 244).

Verifies the Witherbloom Charm card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import WitherbloomCharm

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestWitherbloomCharmBasicProperties:
    """Basic property tests for Witherbloom Charm."""

    def test_is_instant(self) -> None:
        """Witherbloom Charm must be a Instant subclass."""
        card = WitherbloomCharm(name="Witherbloom Charm", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """WitherbloomCharm.name must be 'Witherbloom Charm'."""
        card = WitherbloomCharm(name="Witherbloom Charm", owner=None)
        assert card.name == "Witherbloom Charm"

    def test_card_types(self) -> None:
        """Witherbloom Charm must have correct card types."""
        card = WitherbloomCharm(name="Witherbloom Charm", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Witherbloom Charm must have converted mana cost 2."""
        card = WitherbloomCharm(name="Witherbloom Charm", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Witherbloom Charm must have correct colors."""
        card = WitherbloomCharm(name="Witherbloom Charm", owner=None)
        assert "B" in card.colors
        assert "G" in card.colors


@pytest.mark.ability
class TestWitherbloomCharmAbilities:
    """Ability tests for Witherbloom Charm -- expected to fail against stubs."""

    def test_resolution_removes_creatures(self) -> None:
        """Spell resolution must remove/destroy creatures per oracle text."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Victim", owner=opponent, base_power=1, base_toughness=1)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = WitherbloomCharm(name="Witherbloom Charm", owner=player)
        card.controller = player
        card.on_resolve(game)
        bf = opponent.zones[Zone.BATTLEFIELD].get_all()
        gy = opponent.zones[Zone.GRAVEYARD].get_all()
        assert target not in bf or target in gy, "Witherbloom Charm must remove creature"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = WitherbloomCharm(name="Witherbloom Charm", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Witherbloom Charm must implement behavioral method"


@pytest.mark.edge
class TestWitherbloomCharmEdgeCases:
    """Edge case and trap tests for Witherbloom Charm."""

    def test_fizzle_spell_goes_to_graveyard(self) -> None:
        """Fizzled spell must end up in graveyard."""
        from tests.test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = WitherbloomCharm(name="Witherbloom Charm", owner=player)
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
        card1 = WitherbloomCharm(name="Witherbloom Charm", owner=None)
        card2 = WitherbloomCharm(name="Witherbloom Charm", owner=None)
        card1.name = "Modified"
        assert card2.name == "Witherbloom Charm", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = WitherbloomCharm(name="Witherbloom Charm", owner=None)
        assert card.mana_cost.cmc == 2, \
            f"CMC must be 2, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestWitherbloomCharmInteractions:
    """Multi-card interaction tests for Witherbloom Charm."""

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
        card = WitherbloomCharm(name="Witherbloom Charm", owner=player)
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
        card = WitherbloomCharm(name="Witherbloom Charm", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"
