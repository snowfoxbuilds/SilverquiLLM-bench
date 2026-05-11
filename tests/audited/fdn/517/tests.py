"""Audited tests for Cemetery Recruitment (FDN collector number 517)."""

from __future__ import annotations

import pytest

from card_impl import CemeteryRecruitment

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestCemeteryRecruitmentProperties:
    def test_is_sorcery(self):
        card = CemeteryRecruitment()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = CemeteryRecruitment()
        assert card.name == "Cemetery Recruitment"


@pytest.mark.ability
class TestCemeteryRecruitmentResolution:
    def test_returns_creature_from_graveyard_to_hand(self):
        game = create_game()
        p1 = game.players[0]
        dead = _make_creature(name="Dead Bear", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[dead])
        spell = CemeteryRecruitment(owner=p1, controller=p1)
        spell.chosen_targets = [dead]
        spell.on_resolve(game)
        hand = list(game.get_hand(p1).get_all())
        assert dead in hand
        gy = list(game.get_graveyard(p1).get_all())
        assert dead not in gy


@pytest.mark.edge
class TestCemeteryRecruitmentEdge:
    def test_cannot_cast_empty_graveyard(self):
        game = create_game()
        p1 = game.players[0]
        spell = CemeteryRecruitment(owner=p1, controller=p1)
        assert not spell.can_cast(game)
