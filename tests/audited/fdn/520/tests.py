"""Audited tests for Deadly Plot (FDN collector number 520)."""

from __future__ import annotations

import pytest

from card_impl import DeadlyPlot

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None,
                   subtypes=None):
    c = Creature(name=name, base_power=power, base_toughness=toughness,
                 owner=owner, controller=controller)
    if subtypes:
        c.subtypes = subtypes
    return c



@pytest.mark.basic
class TestDeadlyPlotProperties:
    def test_is_instant(self):
        card = DeadlyPlot()
        assert isinstance(card, Instant)

    def test_name(self):
        card = DeadlyPlot()
        assert card.name == "Deadly Plot"


@pytest.mark.ability
class TestDeadlyPlotResolution:
    def test_mode_0_destroys_creature(self):
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])
        spell = DeadlyPlot(owner=p1, controller=p1)
        spell.chosen_mode = 0
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p2).get_all())
        assert creature not in bf

    def test_mode_0_target_gone_fizzles(self):
        """Mode 0: If target creature left battlefield, nothing happens."""
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(owner=p2, controller=p2)
        # Don't put creature on battlefield — simulates it leaving
        spell = DeadlyPlot(owner=p1, controller=p1)
        spell.chosen_mode = 0
        spell.chosen_targets = [creature]
        initial_p2_bf = len(list(game.get_battlefield(p2).get_all()))
        spell.on_resolve(game)
        # State should be unchanged
        assert len(list(game.get_battlefield(p2).get_all())) == initial_p2_bf

    def test_mode_1_returns_zombie_from_graveyard(self):
        """Mode 1: Return target Zombie creature card from graveyard to battlefield tapped."""
        game = create_game()
        p1 = game.players[0]
        zombie = _make_creature(name="Zombie", power=2, toughness=2,
                                owner=p1, controller=p1, subtypes={"Zombie"})
        # Put zombie in graveyard
        p1.zones[Zone.GRAVEYARD].add(zombie)
        spell = DeadlyPlot(owner=p1, controller=p1)
        spell.chosen_mode = 1
        spell.chosen_targets = [zombie]
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p1).get_all())
        assert zombie in bf

    def test_mode_1_zombie_enters_tapped(self):
        """Mode 1: The reanimated Zombie should enter the battlefield tapped."""
        game = create_game()
        p1 = game.players[0]
        zombie = _make_creature(name="Zombie", power=3, toughness=3,
                                owner=p1, controller=p1, subtypes={"Zombie"})
        p1.zones[Zone.GRAVEYARD].add(zombie)
        spell = DeadlyPlot(owner=p1, controller=p1)
        spell.chosen_mode = 1
        spell.chosen_targets = [zombie]
        spell.on_resolve(game)
        assert zombie.is_tapped

    def test_mode_1_zombie_not_in_graveyard_does_nothing(self):
        """Mode 1: If the target Zombie is no longer in graveyard, nothing happens."""
        game = create_game()
        p1 = game.players[0]
        zombie = _make_creature(name="Zombie", power=2, toughness=2,
                                owner=p1, controller=p1, subtypes={"Zombie"})
        # Do NOT add zombie to graveyard
        spell = DeadlyPlot(owner=p1, controller=p1)
        spell.chosen_mode = 1
        spell.chosen_targets = [zombie]
        initial_bf = len(list(game.get_battlefield(p1).get_all()))
        spell.on_resolve(game)
        assert len(list(game.get_battlefield(p1).get_all())) == initial_bf


@pytest.mark.edge
class TestDeadlyPlotEdge:
    def test_no_mode_state_unchanged(self):
        """No mode selected: state should remain unchanged."""
        game = create_game()
        p1 = game.players[0]
        initial_bf = len(list(game.get_battlefield(p1).get_all()))
        initial_life = p1.life
        spell = DeadlyPlot(owner=p1, controller=p1)
        spell.chosen_mode = None
        spell.on_resolve(game)
        assert len(list(game.get_battlefield(p1).get_all())) == initial_bf
        assert p1.life == initial_life
