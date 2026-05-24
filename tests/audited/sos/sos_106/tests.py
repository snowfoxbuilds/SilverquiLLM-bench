"""Audited tests for Ancestral Anger (collector key 106).

Verifies the Ancestral Anger card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import AncestralAnger

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestAncestralAngerBasicProperties:
    """Basic property tests for Ancestral Anger."""

    def test_is_sorcery(self) -> None:
        """Ancestral Anger must be a Sorcery subclass."""
        card = AncestralAnger(name="Ancestral Anger", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """AncestralAnger.name must be 'Ancestral Anger'."""
        card = AncestralAnger(name="Ancestral Anger", owner=None)
        assert card.name == "Ancestral Anger"

    def test_card_types(self) -> None:
        """Ancestral Anger must have correct card types."""
        card = AncestralAnger(name="Ancestral Anger", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Ancestral Anger must have converted mana cost 1."""
        card = AncestralAnger(name="Ancestral Anger", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Ancestral Anger must have correct colors."""
        card = AncestralAnger(name="Ancestral Anger", owner=None)
        assert "R" in card.colors


@pytest.mark.ability
class TestAncestralAngerAbilities:
    """Ability tests for Ancestral Anger — expected to fail against stubs."""

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
        card = AncestralAnger(name="Ancestral Anger", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Should draw: hand {hand_before} -> {hand_after}"
        )

    def test_grants_trample(self) -> None:
        """Resolution should grant trample."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Keyword
        game = create_game()
        player = game.players[0]
        target = Creature(name="KWTarget", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = AncestralAnger(name="Ancestral Anger", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        assert Keyword.TRAMPLE in target.keywords, (
            "Target should have trample after resolution"
        )


@pytest.mark.edge
class TestAncestralAngerEdgeCases:
    """Edge case tests for Ancestral Anger."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = AncestralAnger(name="Ancestral Anger", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestAncestralAngerInteractions:
    """Interaction tests for Ancestral Anger."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = AncestralAnger(name="Ancestral Anger", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = AncestralAnger(name="Ancestral Anger", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
