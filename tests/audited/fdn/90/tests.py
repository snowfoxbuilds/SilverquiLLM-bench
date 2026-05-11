"""Audited tests for Incinerating Blast (FDN collector number 90)."""

from __future__ import annotations

import pytest

from card_impl import IncineratingBlast

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestIncineratingBlastProperties:
    def test_is_sorcery(self):
        card = IncineratingBlast()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = IncineratingBlast()
        assert card.name == "Incinerating Blast"

    def test_mana_cost(self):
        card = IncineratingBlast()
        assert card.mana_cost == ManaCost.parse("{4}{R}")


@pytest.mark.ability
class TestIncineratingBlastResolution:
    def test_deals_6_to_creature(self):
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(owner=p2, controller=p2, toughness=7)
        set_board_state(game, 1, battlefield=[creature])
        spell = IncineratingBlast(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.RED: 1, ManaType.COLORLESS: 4})
        cast_spell(game, 0, "Incinerating Blast", targets=[creature])
        assert creature.damage_marked == 6


@pytest.mark.edge
class TestIncineratingBlastEdgeCases:
    def test_no_target_no_crash(self):
        game = create_game()
        p1 = game.players[0]
        spell = IncineratingBlast(owner=p1, controller=p1)
        spell.chosen_targets = []
        spell.on_resolve(game)
        # No crash

    def test_target_left_battlefield(self):
        """If target creature left battlefield, spell does nothing."""
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(owner=p2, controller=p2)
        spell = IncineratingBlast(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        # creature not on any battlefield
        spell.on_resolve(game)
        assert creature.damage_marked == 0
