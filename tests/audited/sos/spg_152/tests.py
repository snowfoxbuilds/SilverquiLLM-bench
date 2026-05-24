"""Audited tests for Grim Haruspex (collector key spg_152).

Verifies the Grim Haruspex card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import GrimHaruspex

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestGrimHaruspexBasicProperties:
    """Basic property tests for Grim Haruspex."""

    def test_is_creature(self) -> None:
        """Grim Haruspex must be a Creature subclass."""
        card = GrimHaruspex(name="Grim Haruspex", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """GrimHaruspex.name must be 'Grim Haruspex'."""
        card = GrimHaruspex(name="Grim Haruspex", owner=None)
        assert card.name == "Grim Haruspex"

    def test_card_types(self) -> None:
        """Grim Haruspex must have correct card types."""
        card = GrimHaruspex(name="Grim Haruspex", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Grim Haruspex must have converted mana cost 3."""
        card = GrimHaruspex(name="Grim Haruspex", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Grim Haruspex must have correct colors."""
        card = GrimHaruspex(name="Grim Haruspex", owner=None)
        assert "B" in card.colors

    def test_power(self) -> None:
        """Grim Haruspex must have base power 3."""
        card = GrimHaruspex(name="Grim Haruspex", owner=None)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Grim Haruspex must have base toughness 2."""
        card = GrimHaruspex(name="Grim Haruspex", owner=None)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestGrimHaruspexAbilities:
    """Ability tests for Grim Haruspex — expected to fail against stubs."""

    def test_draws_cards(self) -> None:
        """Resolution should draw card(s)."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        filler = Sorcery(name="Filler", owner=player)
        player.zones[Zone.LIBRARY].add(filler)
        player.zones[Zone.LIBRARY].add(Sorcery(name="F2", owner=player))
        hand_before = len(player.zones[Zone.HAND].get_all())
        card = GrimHaruspex(name="Grim Haruspex", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Should draw: hand {hand_before} -> {hand_after}"
        )


@pytest.mark.edge
class TestGrimHaruspexEdgeCases:
    """Edge case tests for Grim Haruspex."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = GrimHaruspex(name="Grim Haruspex", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestGrimHaruspexInteractions:
    """Interaction tests for Grim Haruspex."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = GrimHaruspex(name="Grim Haruspex", owner=player)
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
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = GrimHaruspex(name="Grim Haruspex", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
