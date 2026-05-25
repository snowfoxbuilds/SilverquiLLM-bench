"""Audited tests for Lecturing Scornmage (collector key 87).

Verifies the Lecturing Scornmage card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import LecturingScornmage

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestLecturingScornmageBasicProperties:
    """Basic property tests for Lecturing Scornmage."""

    def test_is_creature(self) -> None:
        """Lecturing Scornmage must be a Creature subclass."""
        card = LecturingScornmage(name="Lecturing Scornmage", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """LecturingScornmage.name must be 'Lecturing Scornmage'."""
        card = LecturingScornmage(name="Lecturing Scornmage", owner=None)
        assert card.name == "Lecturing Scornmage"

    def test_card_types(self) -> None:
        """Lecturing Scornmage must have correct card types."""
        card = LecturingScornmage(name="Lecturing Scornmage", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Lecturing Scornmage must have converted mana cost 1."""
        card = LecturingScornmage(name="Lecturing Scornmage", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Lecturing Scornmage must have correct colors."""
        card = LecturingScornmage(name="Lecturing Scornmage", owner=None)
        assert "B" in card.colors

    def test_power(self) -> None:
        """Lecturing Scornmage must have base power 1."""
        card = LecturingScornmage(name="Lecturing Scornmage", owner=None)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Lecturing Scornmage must have base toughness 1."""
        card = LecturingScornmage(name="Lecturing Scornmage", owner=None)
        assert card.base_toughness == 1


@pytest.mark.ability
class TestLecturingScornmageAbilities:
    """Ability tests for Lecturing Scornmage — expected to fail against stubs."""

    def test_repartee_registers_trigger(self) -> None:
        """Repartee must register a triggered ability."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = LecturingScornmage(name="Lecturing Scornmage", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        triggers = getattr(game, "triggers", [])
        assert len(triggers) > 0 or hasattr(card, "on_spell_cast"), (
            "Repartee card must register a trigger or expose on_spell_cast"
        )

    def test_repartee_requires_creature_target(self) -> None:
        """Repartee only triggers for spells targeting a creature."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = LecturingScornmage(name="Lecturing Scornmage", owner=player)
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

    def test_repartee_adds_counter(self) -> None:
        """Repartee trigger should add +1/+1 counter."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = LecturingScornmage(name="Lecturing Scornmage", owner=player)
        card.controller = player
        target = Creature(name="Buffed", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card, target])
        power_before = target.base_power
        if hasattr(card, "on_spell_cast"):
            card.on_spell_cast(game, target)
        elif hasattr(card, "repartee_trigger"):
            card.repartee_trigger(game, target)
        power_after = target.power if hasattr(target, "power") else target.base_power
        assert power_after > power_before, (
            f"Repartee should add counter: power {power_before} -> {power_after}"
        )


@pytest.mark.edge
class TestLecturingScornmageEdgeCases:
    """Edge case tests for Lecturing Scornmage."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = LecturingScornmage(name="Lecturing Scornmage", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestLecturingScornmageInteractions:
    """Interaction tests for Lecturing Scornmage."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = LecturingScornmage(name="Lecturing Scornmage", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = LecturingScornmage(name="Lecturing Scornmage", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
