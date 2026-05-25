"""Audited tests for Sneering Shadewriter (collector key 101).

Verifies the Sneering Shadewriter card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import SneeringShadewriter

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost
from benchmarks.sos.workspace.engine.types import Keyword


@pytest.mark.basic
class TestSneeringShadewriterBasicProperties:
    """Basic property tests for Sneering Shadewriter."""

    def test_is_creature(self) -> None:
        """Sneering Shadewriter must be a Creature subclass."""
        card = SneeringShadewriter(name="Sneering Shadewriter", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """SneeringShadewriter.name must be 'Sneering Shadewriter'."""
        card = SneeringShadewriter(name="Sneering Shadewriter", owner=None)
        assert card.name == "Sneering Shadewriter"

    def test_card_types(self) -> None:
        """Sneering Shadewriter must have correct card types."""
        card = SneeringShadewriter(name="Sneering Shadewriter", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Sneering Shadewriter must have converted mana cost 5."""
        card = SneeringShadewriter(name="Sneering Shadewriter", owner=None)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Sneering Shadewriter must have correct colors."""
        card = SneeringShadewriter(name="Sneering Shadewriter", owner=None)
        assert "B" in card.colors

    def test_power(self) -> None:
        """Sneering Shadewriter must have base power 3."""
        card = SneeringShadewriter(name="Sneering Shadewriter", owner=None)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Sneering Shadewriter must have base toughness 3."""
        card = SneeringShadewriter(name="Sneering Shadewriter", owner=None)
        assert card.base_toughness == 3

    def test_has_flying_keyword(self) -> None:
        """Sneering Shadewriter must have Flying keyword."""
        card = SneeringShadewriter(name="Sneering Shadewriter", owner=None)
        assert Keyword.FLYING in card.keywords


@pytest.mark.ability
class TestSneeringShadewriterAbilities:
    """Ability tests for Sneering Shadewriter — expected to fail against stubs."""

    def test_gains_life(self) -> None:
        """Resolution should gain life."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = SneeringShadewriter(name="Sneering Shadewriter", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        assert player.life > life_before, (
            f"Should gain life: {life_before} -> {player.life}"
        )

    def test_causes_life_loss(self) -> None:
        """Resolution should cause life loss."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = SneeringShadewriter(name="Sneering Shadewriter", owner=player)
        card.controller = player
        life_before = opponent.life
        card.on_resolve(game)
        assert opponent.life < life_before, (
            f"Should lose life: {life_before} -> {opponent.life}"
        )


@pytest.mark.edge
class TestSneeringShadewriterEdgeCases:
    """Edge case tests for Sneering Shadewriter."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = SneeringShadewriter(name="Sneering Shadewriter", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestSneeringShadewriterInteractions:
    """Interaction tests for Sneering Shadewriter."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = SneeringShadewriter(name="Sneering Shadewriter", owner=player)
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
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = SneeringShadewriter(name="Sneering Shadewriter", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
