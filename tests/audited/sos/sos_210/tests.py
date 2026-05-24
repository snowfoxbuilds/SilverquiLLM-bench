"""Audited tests for Practiced Scrollsmith (collector key 210).

Verifies the Practiced Scrollsmith card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import PracticedScrollsmith

from engine.card import Creature
from engine.types import CardType, ManaCost
from engine.types import Keyword


@pytest.mark.basic
class TestPracticedScrollsmithBasicProperties:
    """Basic property tests for Practiced Scrollsmith."""

    def test_is_creature(self) -> None:
        """Practiced Scrollsmith must be a Creature subclass."""
        card = PracticedScrollsmith(name="Practiced Scrollsmith", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """PracticedScrollsmith.name must be 'Practiced Scrollsmith'."""
        card = PracticedScrollsmith(name="Practiced Scrollsmith", owner=None)
        assert card.name == "Practiced Scrollsmith"

    def test_card_types(self) -> None:
        """Practiced Scrollsmith must have correct card types."""
        card = PracticedScrollsmith(name="Practiced Scrollsmith", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Practiced Scrollsmith must have converted mana cost 4."""
        card = PracticedScrollsmith(name="Practiced Scrollsmith", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Practiced Scrollsmith must have correct colors."""
        card = PracticedScrollsmith(name="Practiced Scrollsmith", owner=None)
        assert "R" in card.colors
        assert "W" in card.colors

    def test_power(self) -> None:
        """Practiced Scrollsmith must have base power 3."""
        card = PracticedScrollsmith(name="Practiced Scrollsmith", owner=None)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Practiced Scrollsmith must have base toughness 2."""
        card = PracticedScrollsmith(name="Practiced Scrollsmith", owner=None)
        assert card.base_toughness == 2

    def test_has_first_strike_keyword(self) -> None:
        """Practiced Scrollsmith must have First strike keyword."""
        card = PracticedScrollsmith(name="Practiced Scrollsmith", owner=None)
        assert Keyword.FIRST_STRIKE in card.keywords


@pytest.mark.ability
class TestPracticedScrollsmithAbilities:
    """Ability tests for Practiced Scrollsmith — expected to fail against stubs."""

    def test_exiles_target(self) -> None:
        """Resolution should exile the target."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        target = Creature(name="Exiled", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = PracticedScrollsmith(name="Practiced Scrollsmith", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        exile = player.zones[Zone.EXILE].get_all()
        assert target in exile, "Target should be in exile"


@pytest.mark.edge
class TestPracticedScrollsmithEdgeCases:
    """Edge case tests for Practiced Scrollsmith."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = PracticedScrollsmith(name="Practiced Scrollsmith", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestPracticedScrollsmithInteractions:
    """Interaction tests for Practiced Scrollsmith."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = PracticedScrollsmith(name="Practiced Scrollsmith", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = PracticedScrollsmith(name="Practiced Scrollsmith", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
