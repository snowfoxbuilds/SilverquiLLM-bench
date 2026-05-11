"""Audited tests for Disenchant (FDN collector number 572)."""

from __future__ import annotations

import pytest

from card_impl import Disenchant

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestDisenchantProperties:
    def test_is_instant(self):
        card = Disenchant()
        assert isinstance(card, Instant)

    def test_name(self):
        card = Disenchant()
        assert card.name == "Disenchant"


@pytest.mark.ability
class TestDisenchantResolution:
    def test_destroys_artifact(self):
        game = create_game()
        p1, p2 = game.players
        art = Artifact(name="Sol Ring", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[art])
        spell = Disenchant(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Disenchant", targets=[art])
        bf = list(game.get_battlefield(p2).get_all())
        assert art not in bf

    def test_destroys_enchantment(self):
        game = create_game()
        p1, p2 = game.players
        ench = Enchantment(name="Test Ench", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[ench])
        spell = Disenchant(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Disenchant", targets=[ench])
        bf = list(game.get_battlefield(p2).get_all())
        assert ench not in bf


@pytest.mark.edge
class TestDisenchantEdge:
    def test_target_left_battlefield(self):
        game = create_game()
        p1 = game.players[0]
        art = Artifact(name="Sol Ring", owner=p1, controller=p1)
        spell = Disenchant(owner=p1, controller=p1)
        spell.chosen_targets = [art]
        spell.on_resolve(game)
