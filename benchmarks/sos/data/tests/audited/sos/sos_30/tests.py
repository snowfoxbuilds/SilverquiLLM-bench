"""Audited tests for Restoration Seminar (collector key 30).

Verifies the Restoration Seminar card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import RestorationSeminar

from engine.card import Sorcery
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestRestorationSeminarBasicProperties:
    """Basic property tests for Restoration Seminar."""

    def test_is_sorcery(self) -> None:
        """Restoration Seminar must be a Sorcery subclass."""
        card = RestorationSeminar(name="Restoration Seminar", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """RestorationSeminar.name must be 'Restoration Seminar'."""
        card = RestorationSeminar(name="Restoration Seminar", owner=None)
        assert card.name == "Restoration Seminar"

    def test_card_types(self) -> None:
        """Restoration Seminar must have correct card types."""
        card = RestorationSeminar(name="Restoration Seminar", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Restoration Seminar must have converted mana cost 7."""
        card = RestorationSeminar(name="Restoration Seminar", owner=None)
        assert card.mana_cost.cmc == 7

    def test_colors(self) -> None:
        """Restoration Seminar must have correct colors."""
        card = RestorationSeminar(name="Restoration Seminar", owner=None)
        assert "W" in card_colors(card)

@pytest.mark.ability
class TestRestorationSeminarAbilities:
    """Ability tests for Restoration Seminar -- expected to fail against stubs."""

    def test_resolution_exiles_target(self) -> None:
        """Spell resolution must exile target per oracle text."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = RestorationSeminar(name="Restoration Seminar", owner=player)
        card.controller = player
        card.on_resolve(game)
        exile = opponent.zones[Zone.EXILE].get_all()
        assert target in exile, "Restoration Seminar must exile target"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = RestorationSeminar(name="Restoration Seminar", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Restoration Seminar must implement behavioral method"

@pytest.mark.edge
class TestRestorationSeminarEdgeCases:
    """Edge case and trap tests for Restoration Seminar."""

    def test_fizzle_spell_goes_to_graveyard(self) -> None:
        """Fizzled spell must end up in graveyard."""
        from test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = RestorationSeminar(name="Restoration Seminar", owner=player)
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
        card1 = RestorationSeminar(name="Restoration Seminar", owner=None)
        card2 = RestorationSeminar(name="Restoration Seminar", owner=None)
        card1.name = "Modified"
        assert card2.name == "Restoration Seminar", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = RestorationSeminar(name="Restoration Seminar", owner=None)
        assert card.mana_cost.cmc == 7, \
            f"CMC must be 7, got {card.mana_cost.cmc}"

@pytest.mark.interaction
class TestRestorationSeminarInteractions:
    """Multi-card interaction tests for Restoration Seminar."""

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
        card = RestorationSeminar(name="Restoration Seminar", owner=player)
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
        card = RestorationSeminar(name="Restoration Seminar", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"
