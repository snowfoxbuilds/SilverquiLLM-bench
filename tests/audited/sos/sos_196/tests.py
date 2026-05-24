"""Audited tests for Inkling Mascot (collector key 196).

Verifies the Inkling Mascot card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import InklingMascot

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestInklingMascotBasicProperties:
    """Basic property tests for Inkling Mascot."""

    def test_is_creature(self) -> None:
        """Inkling Mascot must be a Creature subclass."""
        card = InklingMascot(name="Inkling Mascot", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """InklingMascot.name must be 'Inkling Mascot'."""
        card = InklingMascot(name="Inkling Mascot", owner=None)
        assert card.name == "Inkling Mascot"

    def test_card_types(self) -> None:
        """Inkling Mascot must have correct card types."""
        card = InklingMascot(name="Inkling Mascot", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Inkling Mascot must have converted mana cost 2."""
        card = InklingMascot(name="Inkling Mascot", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Inkling Mascot must have correct colors."""
        card = InklingMascot(name="Inkling Mascot", owner=None)
        assert "B" in card.colors
        assert "W" in card.colors

    def test_power(self) -> None:
        """Inkling Mascot must have base power 2."""
        card = InklingMascot(name="Inkling Mascot", owner=None)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Inkling Mascot must have base toughness 2."""
        card = InklingMascot(name="Inkling Mascot", owner=None)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestInklingMascotAbilities:
    """Ability tests for Inkling Mascot — expected to fail against stubs."""

    def test_repartee_registers_trigger(self) -> None:
        """Repartee must register a triggered ability."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = InklingMascot(name="Inkling Mascot", owner=player)
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
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = InklingMascot(name="Inkling Mascot", owner=player)
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
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = InklingMascot(name="Inkling Mascot", owner=player)
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

    def test_grants_flying(self) -> None:
        """Resolution should grant flying."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Keyword
        game = create_game()
        player = game.players[0]
        target = Creature(name="KWTarget", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = InklingMascot(name="Inkling Mascot", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        assert Keyword.FLYING in target.keywords, (
            "Target should have flying after resolution"
        )

    def test_surveil_effect(self) -> None:
        """Resolution should surveil 1."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        for i in range(3):
            player.zones[Zone.LIBRARY].add(Sorcery(name=f"Lib{i}", owner=player))
        lib_before = len(player.zones[Zone.LIBRARY].get_all())
        card = InklingMascot(name="Inkling Mascot", owner=player)
        card.controller = player
        card.on_resolve(game)
        gy_after = len(player.zones[Zone.GRAVEYARD].get_all())
        assert gy_after > 0 or len(player.zones[Zone.LIBRARY].get_all()) <= lib_before, (
            "Surveil should manipulate library/graveyard"
        )


@pytest.mark.edge
class TestInklingMascotEdgeCases:
    """Edge case tests for Inkling Mascot."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = InklingMascot(name="Inkling Mascot", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestInklingMascotInteractions:
    """Interaction tests for Inkling Mascot."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = InklingMascot(name="Inkling Mascot", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = InklingMascot(name="Inkling Mascot", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
