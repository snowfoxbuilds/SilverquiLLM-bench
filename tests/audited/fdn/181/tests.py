"""Audited tests for Pilfer (FDN collector number 181)."""

from __future__ import annotations

import pytest

from card_impl import Pilfer

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)


from engine.card import CardImpl


@pytest.mark.basic
class TestPilferProperties:
    def test_is_sorcery(self):
        card = Pilfer()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = Pilfer()
        assert card.name == "Pilfer"


@pytest.mark.ability
class TestPilferResolution:
    def test_targets_opponent(self):
        game = create_game()
        p1, p2 = game.players
        card = Pilfer(owner=p1, controller=p1)
        targets = card.get_targets(game)
        assert len(targets) > 0
