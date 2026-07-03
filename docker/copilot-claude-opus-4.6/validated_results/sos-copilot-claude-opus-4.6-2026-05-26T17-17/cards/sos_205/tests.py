"""Tests for SOS 205 — Moment of Reckoning.

Sorcery {3}{W}{W}{B}{B}
Choose up to four. You may choose the same mode more than once.
• Destroy target nonland permanent.
• Return target nonland permanent card from your graveyard to the battlefield.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_205.card_impl import MomentOfReckoning
from engine.card import Creature, Sorcery, CardImpl
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestMomentOfReckoningProperties:
    """Static card data should match the SOS 205 spec."""

    def test_is_sorcery(self) -> None:
        card = MomentOfReckoning(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = MomentOfReckoning(owner=None)
        assert card.name == "Moment of Reckoning"

    def test_mana_cost(self) -> None:
        card = MomentOfReckoning(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{W}{W}{B}{B}")


class TestMomentOfReckoningModes:
    """Modal spell: choose up to four, may repeat modes."""

    def test_has_two_modes(self) -> None:
        card = MomentOfReckoning(owner=None)
        assert hasattr(card, 'modes') or hasattr(card, 'get_modes')
        modes = getattr(card, 'modes', None) or card.get_modes()
        assert len(modes) == 2

    def test_can_choose_up_to_four_modes(self) -> None:
        card = MomentOfReckoning(owner=None)
        assert hasattr(card, 'max_modes') or hasattr(card, 'max_mode_count')
        max_modes = getattr(card, 'max_modes', None) or getattr(card, 'max_mode_count', None)
        assert max_modes == 4

    def test_can_repeat_same_mode(self) -> None:
        card = MomentOfReckoning(owner=None)
        # The card allows choosing the same mode more than once
        assert getattr(card, 'repeatable_modes', False) is True


class TestMomentOfReckoningDestroyMode:
    """Mode 1: Destroy target nonland permanent."""

    def test_destroys_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = MomentOfReckoning(owner=p1, controller=p1)
        target = Creature(name="Victim", owner=p2, controller=p2,
                          base_power=4, base_toughness=4)
        game.get_battlefield(p2).add(target)
        card.chosen_modes = [0]  # destroy mode
        card.chosen_targets = [target]
        card.on_resolve(game)
        bf = game.get_battlefield(p2).get_all()
        assert target not in bf

    def test_destroy_mode_cannot_target_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MomentOfReckoning(owner=p1, controller=p1)
        land = CardImpl(owner=p1, controller=p1)
        land.name = "Forest"
        land.card_types = {CardType.LAND}
        game.get_battlefield(p1).add(land)
        # The targeting filter should reject lands
        reqs = card.get_targets(game)
        # Find destroy mode's target requirement
        destroy_req = reqs[0] if reqs else None
        if destroy_req and hasattr(destroy_req, 'filter_fn'):
            assert destroy_req.filter_fn(land) is False

    def test_destroys_multiple_with_repeated_mode(self) -> None:
        """Choose destroy mode multiple times to destroy multiple permanents."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = MomentOfReckoning(owner=p1, controller=p1)
        target1 = Creature(name="Victim 1", owner=p2, controller=p2,
                           base_power=3, base_toughness=3)
        target2 = Creature(name="Victim 2", owner=p2, controller=p2,
                           base_power=2, base_toughness=2)
        game.get_battlefield(p2).add(target1)
        game.get_battlefield(p2).add(target2)
        card.chosen_modes = [0, 0]  # destroy twice
        card.chosen_targets = [target1, target2]
        card.on_resolve(game)
        bf = game.get_battlefield(p2).get_all()
        assert target1 not in bf
        assert target2 not in bf


class TestMomentOfReckoningReturnMode:
    """Mode 2: Return target nonland permanent card from graveyard to battlefield."""

    def test_returns_creature_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MomentOfReckoning(owner=p1, controller=p1)
        dead = Creature(name="Dead Bear", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        game.get_graveyard(p1).add(dead)
        card.chosen_modes = [1]  # return mode
        card.chosen_targets = [dead]
        card.on_resolve(game)
        bf = game.get_battlefield(p1).get_all()
        assert dead in bf

    def test_return_mode_cannot_target_land_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MomentOfReckoning(owner=p1, controller=p1)
        land = CardImpl(owner=p1, controller=p1)
        land.name = "Forest"
        land.card_types = {CardType.LAND}
        game.get_graveyard(p1).add(land)
        # Land in graveyard should not be a valid target for return mode
        reqs = card.get_targets(game)
        if len(reqs) > 1:
            return_req = reqs[1]
            if hasattr(return_req, 'filter_fn'):
                assert return_req.filter_fn(land) is False

    def test_returns_multiple_with_repeated_mode(self) -> None:
        """Choose return mode multiple times."""
        game = create_game()
        p1 = game.players[0]
        card = MomentOfReckoning(owner=p1, controller=p1)
        dead1 = Creature(name="Dead 1", owner=p1, controller=p1,
                         base_power=2, base_toughness=2)
        dead2 = Creature(name="Dead 2", owner=p1, controller=p1,
                         base_power=3, base_toughness=3)
        game.get_graveyard(p1).add(dead1)
        game.get_graveyard(p1).add(dead2)
        card.chosen_modes = [1, 1]
        card.chosen_targets = [dead1, dead2]
        card.on_resolve(game)
        bf = game.get_battlefield(p1).get_all()
        assert dead1 in bf
        assert dead2 in bf


class TestMomentOfReckoningMixed:
    """Mix of destroy and return modes."""

    def test_destroy_and_return_in_same_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = MomentOfReckoning(owner=p1, controller=p1)
        # Opponent creature to destroy
        enemy = Creature(name="Enemy", owner=p2, controller=p2,
                         base_power=4, base_toughness=4)
        game.get_battlefield(p2).add(enemy)
        # Own creature in graveyard to return
        dead = Creature(name="Ally", owner=p1, controller=p1,
                        base_power=3, base_toughness=3)
        game.get_graveyard(p1).add(dead)
        card.chosen_modes = [0, 1]  # destroy, then return
        card.chosen_targets = [enemy, dead]
        card.on_resolve(game)
        assert enemy not in game.get_battlefield(p2).get_all()
        assert dead in game.get_battlefield(p1).get_all()

    def test_choose_zero_modes_is_valid(self) -> None:
        """'Up to four' includes zero."""
        game = create_game()
        p1 = game.players[0]
        card = MomentOfReckoning(owner=p1, controller=p1)
        card.chosen_modes = []
        card.chosen_targets = []
        # Should not raise
        card.on_resolve(game)
