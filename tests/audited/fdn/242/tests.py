"""Audited tests for Visionary's Dance (FDN collector number 242)."""

from __future__ import annotations

import pytest

from card_impl import VisionarysDance

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestVisionarysDanceProperties:
    def test_is_sorcery(self):
        card = VisionarysDance()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = VisionarysDance()
        assert card.name == "Visionary\'s Dance"


@pytest.mark.ability
class TestVisionarysDanceResolution:
    def test_creates_tokens(self):
        game = create_game()
        p1 = game.players[0]
        spell = VisionarysDance(owner=p1, controller=p1)
        initial_bf = len(list(game.get_battlefield(p1).get_all()))
        spell.on_resolve(game)
        final_bf = len(list(game.get_battlefield(p1).get_all()))
        assert final_bf >= initial_bf + 2
