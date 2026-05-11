"""Audited tests for Make Your Move (FDN collector number 143)."""

from __future__ import annotations

import pytest

from card_impl import MakeYourMove

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestMakeYourMoveProperties:
    def test_is_instant(self):
        card = MakeYourMove()
        assert isinstance(card, Instant)

    def test_name(self):
        card = MakeYourMove()
        assert card.name == "Make Your Move"


@pytest.mark.ability
class TestMakeYourMoveResolution:
    def test_destroys_artifact(self):
        game = create_game()
        p1, p2 = game.players
        art = Artifact(name="Test Art", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[art])
        spell = MakeYourMove(owner=p1, controller=p1)
        spell.chosen_targets = [art]
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p2).get_all())
        assert art not in bf

    def test_destroys_enchantment(self):
        game = create_game()
        p1, p2 = game.players
        ench = Enchantment(name="Test Ench", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[ench])
        spell = MakeYourMove(owner=p1, controller=p1)
        spell.chosen_targets = [ench]
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p2).get_all())
        assert ench not in bf
