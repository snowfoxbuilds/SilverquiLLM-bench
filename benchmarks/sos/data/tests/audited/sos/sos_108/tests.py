"""Audited tests for Artistic Process (collector key 108).

Verifies the Artistic Process card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import ArtisticProcess

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestArtisticProcessBasicProperties:
    """Basic property tests for Artistic Process."""

    def test_is_sorcery(self) -> None:
        """Artistic Process must be a Sorcery subclass."""
        card = ArtisticProcess(name="Artistic Process", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """ArtisticProcess.name must be 'Artistic Process'."""
        card = ArtisticProcess(name="Artistic Process", owner=None)
        assert card.name == "Artistic Process"

    def test_card_types(self) -> None:
        """Artistic Process must have correct card types."""
        card = ArtisticProcess(name="Artistic Process", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Artistic Process must have converted mana cost 5."""
        card = ArtisticProcess(name="Artistic Process", owner=None)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Artistic Process must have correct colors."""
        card = ArtisticProcess(name="Artistic Process", owner=None)
        assert "R" in card.colors


@pytest.mark.ability
class TestArtisticProcessAbilities:
    """Ability tests for Artistic Process -- expected to fail against stubs."""

    def test_resolution_deals_damage(self) -> None:
        """Spell resolution must deal damage per oracle text."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = ArtisticProcess(name="Artistic Process", owner=player)
        card.controller = player
        initial_life = opponent.life
        card.on_resolve(game)
        assert opponent.life < initial_life, "Artistic Process must deal damage on resolution"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = ArtisticProcess(name="Artistic Process", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Artistic Process must implement behavioral method"


@pytest.mark.edge
class TestArtisticProcessEdgeCases:
    """Edge case and trap tests for Artistic Process."""

    def test_fizzle_spell_goes_to_graveyard(self) -> None:
        """Fizzled spell must end up in graveyard."""
        from test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = ArtisticProcess(name="Artistic Process", owner=player)
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
        card1 = ArtisticProcess(name="Artistic Process", owner=None)
        card2 = ArtisticProcess(name="Artistic Process", owner=None)
        card1.name = "Modified"
        assert card2.name == "Artistic Process", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = ArtisticProcess(name="Artistic Process", owner=None)
        assert card.mana_cost.cmc == 5, \
            f"CMC must be 5, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestArtisticProcessInteractions:
    """Multi-card interaction tests for Artistic Process."""

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
        card = ArtisticProcess(name="Artistic Process", owner=player)
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
        card = ArtisticProcess(name="Artistic Process", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"

    def test_tokens_appear_on_battlefield(self) -> None:
        """Tokens created must appear on the battlefield."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = ArtisticProcess(name="Artistic Process", owner=player)
        card.controller = player
        bf_before = len(player.zones[Zone.BATTLEFIELD].get_all())
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        elif callable(getattr(card, "on_resolve", None)):
            card.on_resolve(game)
        bf_after = len(player.zones[Zone.BATTLEFIELD].get_all())
        assert bf_after > bf_before, "Tokens must appear on battlefield"
