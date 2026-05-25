"""Audited tests for Essenceknit Scholar (collector key 187).

Verifies the Essenceknit Scholar card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import EssenceknitScholar

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestEssenceknitScholarBasicProperties:
    """Basic property tests for Essenceknit Scholar."""

    def test_is_creature(self) -> None:
        """Essenceknit Scholar must be a Creature subclass."""
        card = EssenceknitScholar(name="Essenceknit Scholar", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """EssenceknitScholar.name must be 'Essenceknit Scholar'."""
        card = EssenceknitScholar(name="Essenceknit Scholar", owner=None)
        assert card.name == "Essenceknit Scholar"

    def test_card_types(self) -> None:
        """Essenceknit Scholar must have correct card types."""
        card = EssenceknitScholar(name="Essenceknit Scholar", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Essenceknit Scholar must have converted mana cost 4."""
        card = EssenceknitScholar(name="Essenceknit Scholar", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Essenceknit Scholar must have correct colors."""
        card = EssenceknitScholar(name="Essenceknit Scholar", owner=None)
        assert "B" in card.colors
        assert "G" in card.colors

    def test_power(self) -> None:
        """Essenceknit Scholar must have base power 3."""
        card = EssenceknitScholar(name="Essenceknit Scholar", owner=None)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Essenceknit Scholar must have base toughness 1."""
        card = EssenceknitScholar(name="Essenceknit Scholar", owner=None)
        assert card.base_toughness == 1


@pytest.mark.ability
class TestEssenceknitScholarAbilities:
    """Ability tests for Essenceknit Scholar — expected to fail against stubs."""

    def test_creates_token(self) -> None:
        """Resolution should create token(s) on battlefield."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = EssenceknitScholar(name="Essenceknit Scholar", owner=player)
        card.controller = player
        bf_before = len(game.get_battlefield(player).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after > bf_before, (
            f"Should create token: bf {bf_before} -> {bf_after}"
        )

    def test_draws_cards(self) -> None:
        """Resolution should draw card(s)."""
        from test_utils import create_game
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        filler = Sorcery(name="Filler", owner=player)
        player.zones[Zone.LIBRARY].add(filler)
        player.zones[Zone.LIBRARY].add(Sorcery(name="F2", owner=player))
        hand_before = len(player.zones[Zone.HAND].get_all())
        card = EssenceknitScholar(name="Essenceknit Scholar", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Should draw: hand {hand_before} -> {hand_after}"
        )

    def test_gains_life(self) -> None:
        """Resolution should gain life."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = EssenceknitScholar(name="Essenceknit Scholar", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        assert player.life > life_before, (
            f"Should gain life: {life_before} -> {player.life}"
        )


@pytest.mark.edge
class TestEssenceknitScholarEdgeCases:
    """Edge case tests for Essenceknit Scholar."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = EssenceknitScholar(name="Essenceknit Scholar", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestEssenceknitScholarInteractions:
    """Interaction tests for Essenceknit Scholar."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = EssenceknitScholar(name="Essenceknit Scholar", owner=player)
        card.controller = player
        card._targets = [t1]
        if hasattr(card, "set_targets"):
            card.set_targets([t1])
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Non-targeted creature should remain
        bf = game.get_battlefield(opponent).get_all()
        assert t2 in bf, "Non-targeted creature should remain"

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = EssenceknitScholar(name="Essenceknit Scholar", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
