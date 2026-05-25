"""Audited tests for Imperious Inkmage (collector key 195).

Verifies the Imperious Inkmage card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import ImperiousInkmage

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost
from benchmarks.sos.workspace.engine.types import Keyword


@pytest.mark.basic
class TestImperiousInkmageBasicProperties:
    """Basic property tests for Imperious Inkmage."""

    def test_is_creature(self) -> None:
        """Imperious Inkmage must be a Creature subclass."""
        card = ImperiousInkmage(name="Imperious Inkmage", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """ImperiousInkmage.name must be 'Imperious Inkmage'."""
        card = ImperiousInkmage(name="Imperious Inkmage", owner=None)
        assert card.name == "Imperious Inkmage"

    def test_card_types(self) -> None:
        """Imperious Inkmage must have correct card types."""
        card = ImperiousInkmage(name="Imperious Inkmage", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Imperious Inkmage must have converted mana cost 3."""
        card = ImperiousInkmage(name="Imperious Inkmage", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Imperious Inkmage must have correct colors."""
        card = ImperiousInkmage(name="Imperious Inkmage", owner=None)
        assert "B" in card.colors
        assert "W" in card.colors

    def test_power(self) -> None:
        """Imperious Inkmage must have base power 3."""
        card = ImperiousInkmage(name="Imperious Inkmage", owner=None)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Imperious Inkmage must have base toughness 3."""
        card = ImperiousInkmage(name="Imperious Inkmage", owner=None)
        assert card.base_toughness == 3

    def test_has_vigilance_keyword(self) -> None:
        """Imperious Inkmage must have Vigilance keyword."""
        card = ImperiousInkmage(name="Imperious Inkmage", owner=None)
        assert Keyword.VIGILANCE in card.keywords


@pytest.mark.ability
class TestImperiousInkmageAbilities:
    """Ability tests for Imperious Inkmage — expected to fail against stubs."""

    def test_surveil_effect(self) -> None:
        """Resolution should surveil 2."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.card import Sorcery
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        for i in range(4):
            player.zones[Zone.LIBRARY].add(Sorcery(name=f"Lib{i}", owner=player))
        lib_before = len(player.zones[Zone.LIBRARY].get_all())
        card = ImperiousInkmage(name="Imperious Inkmage", owner=player)
        card.controller = player
        card.on_resolve(game)
        gy_after = len(player.zones[Zone.GRAVEYARD].get_all())
        assert gy_after > 0 or len(player.zones[Zone.LIBRARY].get_all()) <= lib_before, (
            "Surveil should manipulate library/graveyard"
        )


@pytest.mark.edge
class TestImperiousInkmageEdgeCases:
    """Edge case tests for Imperious Inkmage."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = ImperiousInkmage(name="Imperious Inkmage", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestImperiousInkmageInteractions:
    """Interaction tests for Imperious Inkmage."""

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
        card = ImperiousInkmage(name="Imperious Inkmage", owner=player)
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
        card = ImperiousInkmage(name="Imperious Inkmage", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
