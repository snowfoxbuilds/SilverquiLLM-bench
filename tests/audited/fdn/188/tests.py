"""Audited tests for Abrade (FDN collector number 188)."""

from __future__ import annotations

import pytest

from card_impl import Abrade

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestAbradeProperties:
    def test_is_instant(self):
        card = Abrade()
        assert isinstance(card, Instant)

    def test_name(self):
        card = Abrade()
        assert card.name == "Abrade"


@pytest.mark.ability
class TestAbradeResolution:
    def test_mode_0_deals_3_damage(self):
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(owner=p2, controller=p2, toughness=5)
        set_board_state(game, 1, battlefield=[creature])
        spell = Abrade(owner=p1, controller=p1)
        spell.chosen_mode = 0
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        assert creature.damage_marked == 3

    def test_mode_1_destroys_artifact(self):
        game = create_game()
        p1, p2 = game.players
        art = Artifact(name="Art", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[art])
        spell = Abrade(owner=p1, controller=p1)
        spell.chosen_mode = 1
        spell.chosen_targets = [art]
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p2).get_all())
        assert art not in bf


@pytest.mark.edge
class TestAbradeEdge:
    def test_no_mode_state_unchanged(self):
        """No mode selected: state should remain unchanged."""
        game = create_game()
        p1 = game.players[0]
        initial_life = p1.life
        initial_bf = len(list(game.get_battlefield(p1).get_all()))
        spell = Abrade(owner=p1, controller=p1)
        spell.chosen_mode = None
        spell.on_resolve(game)
        assert p1.life == initial_life
        assert len(list(game.get_battlefield(p1).get_all())) == initial_bf
