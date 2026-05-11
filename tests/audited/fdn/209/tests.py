"""Audited tests for Sure Strike (FDN collector number 209)."""

from __future__ import annotations

import pytest

from card_impl import SureStrike

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)


from engine.types import Keyword


@pytest.mark.basic
class TestSureStrikeProperties:
    def test_is_instant(self):
        card = SureStrike()
        assert isinstance(card, Instant)

    def test_name(self):
        card = SureStrike()
        assert card.name == "Sure Strike"


@pytest.mark.ability
class TestSureStrikeResolution:
    def test_gives_plus_3_0(self):
        game = create_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1, power=2, toughness=2)
        set_board_state(game, 0, battlefield=[creature])
        spell = SureStrike(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert creature.power == 5
        assert creature.toughness == 2


@pytest.mark.edge
class TestSureStrikeEdge:
    def test_no_target_no_crash(self):
        game = create_game()
        spell = SureStrike(owner=game.players[0], controller=game.players[0])
        spell.chosen_targets = []
        spell.on_resolve(game)
