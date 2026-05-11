"""Audited tests for Eaten Alive (FDN collector number 172)."""

from __future__ import annotations

import pytest

from card_impl import EatenAlive

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestEatenAliveProperties:
    def test_is_sorcery(self):
        card = EatenAlive()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = EatenAlive()
        assert card.name == "Eaten Alive"


@pytest.mark.ability
class TestEatenAliveResolution:
    def test_exiles_creature(self):
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])
        spell = EatenAlive(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p2).get_all())
        assert creature not in bf


@pytest.mark.edge
class TestEatenAliveEdge:
    def test_no_target_no_crash(self):
        game = create_game()
        spell = EatenAlive(owner=game.players[0], controller=game.players[0])
        spell.chosen_targets = []
        spell.on_resolve(game)
