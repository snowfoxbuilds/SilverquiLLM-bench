"""Audited tests for Withering Curse (FDN collector number 105)."""

from __future__ import annotations

import pytest

from card_impl import WitheringCurse

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestWitheringCurseProperties:
    def test_is_sorcery(self):
        card = WitheringCurse()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = WitheringCurse()
        assert card.name == "Withering Curse"


@pytest.mark.ability
class TestWitheringCurseResolution:
    def test_applies_minus_2_2(self):
        """All creatures get -2/-2 until end of turn."""
        game = create_game()
        p1, p2 = game.players
        c1 = _make_creature(name="Bear1", power=2, toughness=2, owner=p1, controller=p1)
        c2 = _make_creature(name="Bear2", power=3, toughness=3, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[c1])
        set_board_state(game, 1, battlefield=[c2])
        spell = WitheringCurse(owner=p1, controller=p1)
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert c2.power == 1
        assert c2.toughness == 1
