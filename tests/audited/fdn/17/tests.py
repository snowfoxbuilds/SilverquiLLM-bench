"""Audited tests for Group Project (FDN collector number 17)."""

from __future__ import annotations

import pytest

from card_impl import GroupProject

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestGroupProjectProperties:
    def test_is_sorcery(self):
        card = GroupProject()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = GroupProject()
        assert card.name == "Group Project"


@pytest.mark.ability
class TestGroupProjectResolution:
    def test_creates_token(self):
        game = create_game()
        p1 = game.players[0]
        spell = GroupProject(owner=p1, controller=p1)
        initial_bf = len(list(game.get_battlefield(p1).get_all()))
        spell.on_resolve(game)
        final_bf = len(list(game.get_battlefield(p1).get_all()))
        assert final_bf > initial_bf
