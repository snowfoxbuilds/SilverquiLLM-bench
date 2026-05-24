"""Audited tests for Orysa, Tide Choreographer (collector key 62).

Verifies the Orysa, Tide Choreographer card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import OrysaTideChoreographer

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestOrysaTideChoreographerBasicProperties:
    """Basic property tests for Orysa, Tide Choreographer."""

    def test_is_creature(self) -> None:
        """Orysa, Tide Choreographer must be a Creature subclass."""
        card = OrysaTideChoreographer(name="Orysa, Tide Choreographer", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """OrysaTideChoreographer.name must be 'Orysa, Tide Choreographer'."""
        card = OrysaTideChoreographer(name="Orysa, Tide Choreographer", owner=None)
        assert card.name == "Orysa, Tide Choreographer"

    def test_card_types(self) -> None:
        """Orysa, Tide Choreographer must have correct card types."""
        card = OrysaTideChoreographer(name="Orysa, Tide Choreographer", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Orysa, Tide Choreographer must have converted mana cost 5."""
        card = OrysaTideChoreographer(name="Orysa, Tide Choreographer", owner=None)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Orysa, Tide Choreographer must have correct colors."""
        card = OrysaTideChoreographer(name="Orysa, Tide Choreographer", owner=None)
        assert "U" in card.colors

    def test_power(self) -> None:
        """Orysa, Tide Choreographer must have base power 2."""
        card = OrysaTideChoreographer(name="Orysa, Tide Choreographer", owner=None)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Orysa, Tide Choreographer must have base toughness 2."""
        card = OrysaTideChoreographer(name="Orysa, Tide Choreographer", owner=None)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestOrysaTideChoreographerAbilities:
    """Ability tests for Orysa, Tide Choreographer — expected to fail against stubs."""

    def test_draws_cards(self) -> None:
        """Resolution should draw card(s)."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.card import Sorcery
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        filler = Sorcery(name="Filler", owner=player)
        player.zones[Zone.LIBRARY].add(filler)
        player.zones[Zone.LIBRARY].add(Sorcery(name="F2", owner=player))
        hand_before = len(player.zones[Zone.HAND].get_all())
        card = OrysaTideChoreographer(name="Orysa, Tide Choreographer", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Should draw: hand {hand_before} -> {hand_after}"
        )

    def test_cost_reduction_applies(self) -> None:
        """cost_reduction should return > 0 when condition met."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = OrysaTideChoreographer(name="Orysa, Tide Choreographer", owner=player)
        card.controller = player
        target = Creature(name="Cond", owner=player, base_power=2, base_toughness=2)
        target.tapped = True
        set_board_state(game, 0, battlefield=[target])
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        reduction = card.cost_reduction(game)
        assert reduction > 0, f"Cost reduction should apply, got {reduction}"


@pytest.mark.edge
class TestOrysaTideChoreographerEdgeCases:
    """Edge case tests for Orysa, Tide Choreographer."""

    def test_no_reduction_when_condition_unmet(self) -> None:
        """No cost reduction when condition is not met."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = OrysaTideChoreographer(name="Orysa, Tide Choreographer", owner=player)
        card.controller = player
        target = Creature(name="Untapped", owner=player, base_power=2, base_toughness=2)
        target.tapped = False
        set_board_state(game, 0, battlefield=[target])
        card._targets = [target]
        reduction = card.cost_reduction(game)
        assert reduction == 0, f"No reduction when unmet, got {reduction}"


@pytest.mark.interaction
class TestOrysaTideChoreographerInteractions:
    """Interaction tests for Orysa, Tide Choreographer."""

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
        card = OrysaTideChoreographer(name="Orysa, Tide Choreographer", owner=player)
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
        card = OrysaTideChoreographer(name="Orysa, Tide Choreographer", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
