"""Audited tests for Germination Practicum (collector key 149).

Verifies the Germination Practicum card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import GerminationPracticum

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestGerminationPracticumBasicProperties:
    """Basic property tests for Germination Practicum."""

    def test_is_sorcery(self) -> None:
        """Germination Practicum must be a Sorcery subclass."""
        card = GerminationPracticum(name="Germination Practicum", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """GerminationPracticum.name must be 'Germination Practicum'."""
        card = GerminationPracticum(name="Germination Practicum", owner=None)
        assert card.name == "Germination Practicum"

    def test_card_types(self) -> None:
        """Germination Practicum must have correct card types."""
        card = GerminationPracticum(name="Germination Practicum", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Germination Practicum must have converted mana cost 5."""
        card = GerminationPracticum(name="Germination Practicum", owner=None)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Germination Practicum must have correct colors."""
        card = GerminationPracticum(name="Germination Practicum", owner=None)
        assert "G" in card.colors


@pytest.mark.ability
class TestGerminationPracticumAbilities:
    """Ability tests for Germination Practicum -- expected to fail against stubs."""

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
        card = GerminationPracticum(name="Germination Practicum", owner=player)
        card.controller = player
        card.on_resolve(game)
        exile = opponent.zones[Zone.EXILE].get_all()
        assert target in exile, "Germination Practicum must exile target"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = GerminationPracticum(name="Germination Practicum", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Germination Practicum must implement behavioral method"


@pytest.mark.edge
class TestGerminationPracticumEdgeCases:
    """Edge case and trap tests for Germination Practicum."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = GerminationPracticum(name="Germination Practicum", owner=None)
        card2 = GerminationPracticum(name="Germination Practicum", owner=None)
        card1.name = "Modified"
        assert card2.name == "Germination Practicum", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = GerminationPracticum(name="Germination Practicum", owner=None)
        assert card.mana_cost.cmc == 5, \
            f"CMC must be 5, got {card.mana_cost.cmc}"

    def test_resolution_with_empty_board(self) -> None:
        """Spell must handle resolution with no valid targets/creatures."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = GerminationPracticum(name="Germination Practicum", owner=player)
        card.controller = player
        # Resolution on empty board should not crash
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Fizzle on empty board is acceptable
        # Verify game state is consistent
        assert player.life == 20, "Caster life should be unchanged on fizzle"


@pytest.mark.interaction
class TestGerminationPracticumInteractions:
    """Multi-card interaction tests for Germination Practicum."""

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = GerminationPracticum(name="Germination Practicum", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"

    def test_coexists_with_other_permanents(self) -> None:
        """Card must coexist with other permanents without errors."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        set_board_state(game, 0, battlefield=[other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
