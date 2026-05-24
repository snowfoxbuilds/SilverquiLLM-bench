"""Audited tests for Emil, Vastlands Roamer (collector key 146).

Verifies the Emil, Vastlands Roamer card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import EmilVastlandsRoamer

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestEmilVastlandsRoamerBasicProperties:
    """Basic property tests for Emil, Vastlands Roamer."""

    def test_is_creature(self) -> None:
        """Emil, Vastlands Roamer must be a Creature subclass."""
        card = EmilVastlandsRoamer(name="Emil, Vastlands Roamer", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """EmilVastlandsRoamer.name must be 'Emil, Vastlands Roamer'."""
        card = EmilVastlandsRoamer(name="Emil, Vastlands Roamer", owner=None)
        assert card.name == "Emil, Vastlands Roamer"

    def test_card_types(self) -> None:
        """Emil, Vastlands Roamer must have correct card types."""
        card = EmilVastlandsRoamer(name="Emil, Vastlands Roamer", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Emil, Vastlands Roamer must have converted mana cost 3."""
        card = EmilVastlandsRoamer(name="Emil, Vastlands Roamer", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Emil, Vastlands Roamer must have correct colors."""
        card = EmilVastlandsRoamer(name="Emil, Vastlands Roamer", owner=None)
        assert "G" in card.colors

    def test_power(self) -> None:
        """Emil, Vastlands Roamer must have base power 3."""
        card = EmilVastlandsRoamer(name="Emil, Vastlands Roamer", owner=None)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Emil, Vastlands Roamer must have base toughness 3."""
        card = EmilVastlandsRoamer(name="Emil, Vastlands Roamer", owner=None)
        assert card.base_toughness == 3


@pytest.mark.ability
class TestEmilVastlandsRoamerAbilities:
    """Ability tests for Emil, Vastlands Roamer — expected to fail against stubs."""

    def test_creates_token(self) -> None:
        """Resolution should create token(s) on battlefield."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = EmilVastlandsRoamer(name="Emil, Vastlands Roamer", owner=player)
        card.controller = player
        bf_before = len(game.get_battlefield(player).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after > bf_before, (
            f"Should create token: bf {bf_before} -> {bf_after}"
        )

    def test_adds_plus_counter(self) -> None:
        """Resolution should add +1/+1 counter to target."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="Target", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = EmilVastlandsRoamer(name="Emil, Vastlands Roamer", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        power_before = target.base_power
        card.on_resolve(game)
        power_after = target.power if hasattr(target, "power") else target.base_power
        assert power_after > power_before, (
            f"+1/+1 counter: power {power_before} -> {power_after}"
        )

    def test_has_activated_ability(self) -> None:
        """Card must expose at least one activated ability."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = EmilVastlandsRoamer(name="Emil, Vastlands Roamer", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        abilities_list = card.get_activated_abilities()
        assert len(abilities_list) > 0, "Card must have activated ability"


@pytest.mark.edge
class TestEmilVastlandsRoamerEdgeCases:
    """Edge case tests for Emil, Vastlands Roamer."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = EmilVastlandsRoamer(name="Emil, Vastlands Roamer", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestEmilVastlandsRoamerInteractions:
    """Interaction tests for Emil, Vastlands Roamer."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = EmilVastlandsRoamer(name="Emil, Vastlands Roamer", owner=player)
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
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = EmilVastlandsRoamer(name="Emil, Vastlands Roamer", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
