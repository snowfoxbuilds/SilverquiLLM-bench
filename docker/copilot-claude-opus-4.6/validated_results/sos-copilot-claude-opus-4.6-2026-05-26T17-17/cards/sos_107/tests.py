"""Tests for SOS 107 — Archaic's Agony."""

from __future__ import annotations

import pytest

from cards.sos.sos_107.card_impl import ArchaicsAgony
from engine.card import Creature, Sorcery
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class TestArchaicsAgonyProperties:
    """Static card data should match SOS 107 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(ArchaicsAgony(owner=None), Sorcery)

    def test_name(self) -> None:
        assert ArchaicsAgony(owner=None).name == "Archaic's Agony"

    def test_mana_cost(self) -> None:
        assert ArchaicsAgony(owner=None).mana_cost == ManaCost.parse("{4}{R}")


class TestArchaicsAgonyTargeting:
    """Archaic's Agony targets a creature."""

    def test_returns_single_target_requirement(self) -> None:
        game = create_game()
        reqs = ArchaicsAgony(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        req = ArchaicsAgony(owner=None).get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD


class TestArchaicsAgonyResolution:
    """Converge — deals X damage where X is number of colors spent."""

    def test_deals_damage_equal_to_colors_spent(self) -> None:
        """With 3 colors spent, deals 3 damage to target creature."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Big Beast", owner=p2, controller=p2, base_power=5, base_toughness=5)
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        spell = ArchaicsAgony(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.colors_spent = 3  # converge count
        spell.on_resolve(game)
        # 3 damage to a 5-toughness creature => toughness effectively 2
        assert target.damage_taken == 3

    def test_one_color_deals_one_damage(self) -> None:
        """With only 1 color (red) spent, deals 1 damage."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Small Beast", owner=p2, controller=p2, base_power=2, base_toughness=3)
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        spell = ArchaicsAgony(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.colors_spent = 1
        spell.on_resolve(game)
        assert target.damage_taken == 1

    def test_excess_damage_exiles_from_library(self) -> None:
        """If creature has 2 toughness and 5 damage dealt, excess = 3, exile 3 cards."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Small", owner=p2, controller=p2, base_power=1, base_toughness=2)
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        # Add cards to p1's library
        for i in range(5):
            card = Creature(name=f"LibCard{i}", owner=p1, base_power=1, base_toughness=1)
            game.get_library(p1).add(card)

        spell = ArchaicsAgony(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.colors_spent = 5  # 5 damage to 2 toughness creature = 3 excess
        spell.on_resolve(game)
        # 3 cards should be exiled
        exile = game.get_exile(p1)
        assert len(exile) == 3

    def test_no_excess_no_exile(self) -> None:
        """If damage equals toughness exactly, no excess, no exile."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Beast", owner=p2, controller=p2, base_power=3, base_toughness=3)
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        # Add cards to p1's library
        for i in range(5):
            card = Creature(name=f"LibCard{i}", owner=p1, base_power=1, base_toughness=1)
            game.get_library(p1).add(card)

        spell = ArchaicsAgony(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.colors_spent = 3  # 3 damage to 3 toughness = 0 excess
        spell.on_resolve(game)
        exile = game.get_exile(p1)
        assert len(exile) == 0
