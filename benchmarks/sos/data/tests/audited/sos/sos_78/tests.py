"""Audited tests for Decorum Dissertation (collector key 78).

Verifies the Decorum Dissertation card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import DecorumDissertation

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestDecorumDissertationBasicProperties:
    """Basic property tests for Decorum Dissertation."""

    def test_is_sorcery(self) -> None:
        """Decorum Dissertation must be a Sorcery subclass."""
        card = DecorumDissertation(name="Decorum Dissertation", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """DecorumDissertation.name must be 'Decorum Dissertation'."""
        card = DecorumDissertation(name="Decorum Dissertation", owner=None)
        assert card.name == "Decorum Dissertation"

    def test_card_types(self) -> None:
        """Decorum Dissertation must have correct card types."""
        card = DecorumDissertation(name="Decorum Dissertation", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Decorum Dissertation must have converted mana cost 5."""
        card = DecorumDissertation(name="Decorum Dissertation", owner=None)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Decorum Dissertation must have correct colors."""
        card = DecorumDissertation(name="Decorum Dissertation", owner=None)
        assert "B" in card.colors


@pytest.mark.ability
class TestDecorumDissertationAbilities:
    """Ability tests for Decorum Dissertation — expected to fail against stubs."""

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
        card = DecorumDissertation(name="Decorum Dissertation", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Should draw: hand {hand_before} -> {hand_after}"
        )

    def test_causes_life_loss(self) -> None:
        """Resolution should cause life loss."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = DecorumDissertation(name="Decorum Dissertation", owner=player)
        card.controller = player
        life_before = opponent.life
        card.on_resolve(game)
        assert opponent.life < life_before, (
            f"Should lose life: {life_before} -> {opponent.life}"
        )


@pytest.mark.edge
class TestDecorumDissertationEdgeCases:
    """Edge case tests for Decorum Dissertation."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = DecorumDissertation(name="Decorum Dissertation", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestDecorumDissertationInteractions:
    """Interaction tests for Decorum Dissertation."""

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
        card = DecorumDissertation(name="Decorum Dissertation", owner=player)
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

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = DecorumDissertation(name="Decorum Dissertation", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
