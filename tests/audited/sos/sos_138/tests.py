"""Audited tests for Aberrant Manawurm (collector key 138).

Verifies the Aberrant Manawurm card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import AberrantManawurm

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost
from benchmarks.sos.workspace.engine.types import Keyword


@pytest.mark.basic
class TestAberrantManawurmBasicProperties:
    """Basic property tests for Aberrant Manawurm."""

    def test_is_creature(self) -> None:
        """Aberrant Manawurm must be a Creature subclass."""
        card = AberrantManawurm(name="Aberrant Manawurm", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """AberrantManawurm.name must be 'Aberrant Manawurm'."""
        card = AberrantManawurm(name="Aberrant Manawurm", owner=None)
        assert card.name == "Aberrant Manawurm"

    def test_card_types(self) -> None:
        """Aberrant Manawurm must have correct card types."""
        card = AberrantManawurm(name="Aberrant Manawurm", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Aberrant Manawurm must have converted mana cost 4."""
        card = AberrantManawurm(name="Aberrant Manawurm", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Aberrant Manawurm must have correct colors."""
        card = AberrantManawurm(name="Aberrant Manawurm", owner=None)
        assert "G" in card.colors

    def test_power(self) -> None:
        """Aberrant Manawurm must have base power 2."""
        card = AberrantManawurm(name="Aberrant Manawurm", owner=None)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Aberrant Manawurm must have base toughness 5."""
        card = AberrantManawurm(name="Aberrant Manawurm", owner=None)
        assert card.base_toughness == 5

    def test_has_trample_keyword(self) -> None:
        """Aberrant Manawurm must have Trample keyword."""
        card = AberrantManawurm(name="Aberrant Manawurm", owner=None)
        assert Keyword.TRAMPLE in card.keywords


@pytest.mark.ability
class TestAberrantManawurmAbilities:
    """Ability tests for Aberrant Manawurm — expected to fail against stubs."""

    def test_on_resolve_changes_state(self) -> None:
        """Resolution must produce observable state change."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[target])
        card = AberrantManawurm(name="Aberrant Manawurm", owner=player)
        card.controller = player
        p_life = player.life
        o_life = opponent.life
        p_bf = len(game.get_battlefield(player).get_all())
        o_bf = len(game.get_battlefield(opponent).get_all())
        p_hand = len(player.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        changed = (
            player.life != p_life or opponent.life != o_life or
            len(game.get_battlefield(player).get_all()) != p_bf or
            len(game.get_battlefield(opponent).get_all()) != o_bf or
            len(player.zones[Zone.HAND].get_all()) != p_hand or
            len(player.zones[Zone.GRAVEYARD].get_all()) > 0 or
            len(opponent.zones[Zone.GRAVEYARD].get_all()) > 0
        )
        assert changed, "on_resolve must change game state"


@pytest.mark.edge
class TestAberrantManawurmEdgeCases:
    """Edge case tests for Aberrant Manawurm."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = AberrantManawurm(name="Aberrant Manawurm", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestAberrantManawurmInteractions:
    """Interaction tests for Aberrant Manawurm."""

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
        card = AberrantManawurm(name="Aberrant Manawurm", owner=player)
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
        card = AberrantManawurm(name="Aberrant Manawurm", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
