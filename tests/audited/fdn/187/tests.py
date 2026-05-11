"""Audited tests for Zombify (FDN collector number 187)."""

from __future__ import annotations

import pytest

from card_impl import Zombify

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestZombifyProperties:
    def test_is_sorcery(self):
        card = Zombify()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = Zombify()
        assert card.name == "Zombify"


@pytest.mark.ability
class TestZombifyResolution:
    def test_returns_creature_to_battlefield(self):
        game = create_game()
        p1 = game.players[0]
        dead = _make_creature(name="Dead Bear", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[dead])
        spell = Zombify(owner=p1, controller=p1)
        spell.chosen_targets = [dead]
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p1).get_all())
        assert dead in bf
        gy = list(game.get_graveyard(p1).get_all())
        assert dead not in gy


@pytest.mark.edge
class TestZombifyEdge:
    def test_no_target_no_crash(self):
        game = create_game()
        spell = Zombify(owner=game.players[0], controller=game.players[0])
        spell.chosen_targets = []
        spell.on_resolve(game)
