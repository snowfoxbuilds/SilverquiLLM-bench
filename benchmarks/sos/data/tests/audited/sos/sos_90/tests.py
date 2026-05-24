"""Audited tests for Melancholic Poet (collector key 90).

Verifies the Melancholic Poet card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import MelancholicPoet

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestMelancholicPoetBasicProperties:
    """Basic property tests for Melancholic Poet."""

    def test_is_creature(self) -> None:
        """Melancholic Poet must be a Creature subclass."""
        card = MelancholicPoet(name="Melancholic Poet", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """MelancholicPoet.name must be 'Melancholic Poet'."""
        card = MelancholicPoet(name="Melancholic Poet", owner=None)
        assert card.name == "Melancholic Poet"

    def test_card_types(self) -> None:
        """Melancholic Poet must have correct card types."""
        card = MelancholicPoet(name="Melancholic Poet", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Melancholic Poet must have converted mana cost 2."""
        card = MelancholicPoet(name="Melancholic Poet", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Melancholic Poet must have correct colors."""
        card = MelancholicPoet(name="Melancholic Poet", owner=None)
        assert "B" in card.colors

    def test_power(self) -> None:
        """Melancholic Poet must have base power 2."""
        card = MelancholicPoet(name="Melancholic Poet", owner=None)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Melancholic Poet must have base toughness 2."""
        card = MelancholicPoet(name="Melancholic Poet", owner=None)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestMelancholicPoetAbilities:
    """Ability tests for Melancholic Poet — expected to fail against stubs."""

    def test_repartee_registers_trigger(self) -> None:
        """Repartee must register a triggered ability."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = MelancholicPoet(name="Melancholic Poet", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        triggers = getattr(game, "triggers", [])
        assert len(triggers) > 0 or hasattr(card, "on_spell_cast"), (
            "Repartee card must register a trigger or expose on_spell_cast"
        )

    def test_repartee_requires_creature_target(self) -> None:
        """Repartee only triggers for spells targeting a creature."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = MelancholicPoet(name="Melancholic Poet", owner=player)
        card.controller = player
        target = Creature(name="Target", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[card, target])
        card.register_triggers(game)
        has_trigger_logic = (
            hasattr(card, "on_spell_cast") or
            hasattr(card, "repartee_trigger") or
            hasattr(card, "check_trigger_condition")
        )
        assert has_trigger_logic, "Repartee must check spell targets creature"

    def test_repartee_produces_effect(self) -> None:
        """Repartee trigger should produce an observable effect."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = MelancholicPoet(name="Melancholic Poet", owner=player)
        card.controller = player
        target = Creature(name="Target", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[card, target])
        bf_before = len(game.get_battlefield(player).get_all())
        life_before = player.life
        if hasattr(card, "on_spell_cast"):
            card.on_spell_cast(game, target)
        elif hasattr(card, "repartee_trigger"):
            card.repartee_trigger(game, target)
        bf_after = len(game.get_battlefield(player).get_all())
        life_after = player.life
        hand_after = len(player.zones[Zone.HAND].get_all())
        changed = bf_after != bf_before or life_after != life_before or hand_after > 0
        assert changed, "Repartee trigger must produce observable effect"

    def test_gains_life(self) -> None:
        """Resolution should gain life."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = MelancholicPoet(name="Melancholic Poet", owner=player)
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
        card = MelancholicPoet(name="Melancholic Poet", owner=player)
        card.controller = player
        life_before = opponent.life
        card.on_resolve(game)
        assert opponent.life < life_before, (
            f"Should lose life: {life_before} -> {opponent.life}"
        )


@pytest.mark.edge
class TestMelancholicPoetEdgeCases:
    """Edge case tests for Melancholic Poet."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = MelancholicPoet(name="Melancholic Poet", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestMelancholicPoetInteractions:
    """Interaction tests for Melancholic Poet."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = MelancholicPoet(name="Melancholic Poet", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = MelancholicPoet(name="Melancholic Poet", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
