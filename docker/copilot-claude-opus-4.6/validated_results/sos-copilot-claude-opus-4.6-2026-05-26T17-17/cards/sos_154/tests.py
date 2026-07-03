"""Tests for SOS 154 — Mindful Biomancer.

Creature — Dryad Druid, 2/2 for {1}{G}.
ETB: You gain 1 life.
{2}{G}: This creature gets +2/+2 until end of turn. Activate only once each turn.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_154.card_impl import MindfulBiomancer
from engine.card import Creature
from engine.types import Keyword, ManaCost, ManaType
from test_utils import create_game, set_board_state


class TestMindfulBiomancerProperties:
    """Static card data should match the SOS 154 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(MindfulBiomancer(owner=None), Creature)

    def test_name(self) -> None:
        assert MindfulBiomancer(owner=None).name == "Mindful Biomancer"

    def test_mana_cost(self) -> None:
        assert MindfulBiomancer(owner=None).mana_cost == ManaCost.parse("{1}{G}")

    def test_power_toughness(self) -> None:
        card = MindfulBiomancer(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestMindfulBiomancerETB:
    """When this creature enters, you gain 1 life."""

    def test_gains_one_life_on_enter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        biomancer = MindfulBiomancer(owner=p1, controller=p1)
        initial_life = p1.life
        game.get_battlefield(p1).add(biomancer)
        biomancer.on_enter_battlefield(game)
        assert p1.life == initial_life + 1


class TestMindfulBiomancerActivatedAbility:
    """{2}{G}: Gets +2/+2 until end of turn. Activate only once each turn."""

    def test_activated_ability_grants_plus_2_plus_2(self) -> None:
        game = create_game()
        p1 = game.players[0]
        biomancer = MindfulBiomancer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(biomancer)
        set_board_state(game, 0, mana={ManaType.GREEN: 1, ManaType.COLORLESS: 2})

        biomancer.activate_ability(game, 0)
        assert biomancer.power == 4  # 2 + 2
        assert biomancer.toughness == 4  # 2 + 2

    def test_cannot_activate_twice_in_same_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        biomancer = MindfulBiomancer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(biomancer)
        set_board_state(game, 0, mana={ManaType.GREEN: 2, ManaType.COLORLESS: 4})

        biomancer.activate_ability(game, 0)
        # Second activation should fail or be disallowed
        assert biomancer.can_activate_ability(game, 0) is False

    def test_can_activate_again_next_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        biomancer = MindfulBiomancer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(biomancer)
        set_board_state(game, 0, mana={ManaType.GREEN: 1, ManaType.COLORLESS: 2})

        biomancer.activate_ability(game, 0)
        # Simulate new turn
        biomancer.on_new_turn(game)
        assert biomancer.can_activate_ability(game, 0) is True
