"""Audited tests for Thornfist Striker (collector key 164).

Verifies the Thornfist Striker card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import ThornfistStriker

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost
from benchmarks.sos.workspace.engine.types import Keyword


@pytest.mark.basic
class TestThornfistStrikerBasicProperties:
    """Basic property tests for Thornfist Striker."""

    def test_is_creature(self) -> None:
        """Thornfist Striker must be a Creature subclass."""
        card = ThornfistStriker(name="Thornfist Striker", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """ThornfistStriker.name must be 'Thornfist Striker'."""
        card = ThornfistStriker(name="Thornfist Striker", owner=None)
        assert card.name == "Thornfist Striker"

    def test_card_types(self) -> None:
        """Thornfist Striker must have correct card types."""
        card = ThornfistStriker(name="Thornfist Striker", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Thornfist Striker must have converted mana cost 3."""
        card = ThornfistStriker(name="Thornfist Striker", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Thornfist Striker must have correct colors."""
        card = ThornfistStriker(name="Thornfist Striker", owner=None)
        assert "G" in card.colors

    def test_power(self) -> None:
        """Thornfist Striker must have base power 3."""
        card = ThornfistStriker(name="Thornfist Striker", owner=None)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Thornfist Striker must have base toughness 3."""
        card = ThornfistStriker(name="Thornfist Striker", owner=None)
        assert card.base_toughness == 3

    def test_has_ward_keyword(self) -> None:
        """Thornfist Striker must have Ward keyword."""
        card = ThornfistStriker(name="Thornfist Striker", owner=None)
        assert Keyword.WARD in card.keywords


@pytest.mark.ability
class TestThornfistStrikerAbilities:
    """Ability tests for Thornfist Striker — expected to fail against stubs."""

    def test_pump_effect(self) -> None:
        """Resolution should grant +1/+0."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="PumpTarget", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[target])
        card = ThornfistStriker(name="Thornfist Striker", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        actual_power = target.power if hasattr(target, "power") else target.base_power
        assert actual_power == 2, (
            f"Should pump to 2 power, got {actual_power}"
        )

    def test_gains_life(self) -> None:
        """Resolution should gain life."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = ThornfistStriker(name="Thornfist Striker", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        assert player.life > life_before, (
            f"Should gain life: {life_before} -> {player.life}"
        )


@pytest.mark.edge
class TestThornfistStrikerEdgeCases:
    """Edge case tests for Thornfist Striker."""

    def test_targets_only_own_permanents(self) -> None:
        """Should only target permanents you control."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        own = Creature(name="Own", owner=player, base_power=2, base_toughness=2)
        enemy = Creature(name="Enemy", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[own])
        set_board_state(game, 1, battlefield=[enemy])
        card = ThornfistStriker(name="Thornfist Striker", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        if len(targets) > 0:
            assert own in targets, "Own creature should be valid"
            assert enemy not in targets, "Opponent creature should be invalid"


@pytest.mark.interaction
class TestThornfistStrikerInteractions:
    """Interaction tests for Thornfist Striker."""

    def test_get_targets_finds_own_creatures(self) -> None:
        """get_targets should return valid own creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        creature = Creature(name="Mine", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[creature])
        card = ThornfistStriker(name="Thornfist Striker", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find own creature as target"

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = ThornfistStriker(name="Thornfist Striker", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
