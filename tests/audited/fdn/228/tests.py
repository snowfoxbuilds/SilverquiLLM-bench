"""Audited tests for Social Snub (FDN collector number 228)."""

from __future__ import annotations

import pytest

from card_impl import SocialSnub

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestSocialSnubProperties:
    def test_is_sorcery(self):
        card = SocialSnub()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = SocialSnub()
        assert card.name == "Social Snub"

    def test_mana_cost(self):
        card = SocialSnub()
        assert card.mana_cost == ManaCost.parse("{1}{W}{B}")


@pytest.mark.ability
class TestSocialSnubResolution:
    def test_each_player_sacrifices_a_creature(self):
        """Each player sacrifices a creature."""
        game = create_game()
        p1, p2 = game.players
        c1 = _make_creature(name="Bear1", power=2, toughness=2, owner=p1, controller=p1)
        c2 = _make_creature(name="Bear2", power=2, toughness=2, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[c1])
        set_board_state(game, 1, battlefield=[c2])
        spell = SocialSnub(owner=p1, controller=p1)
        spell.on_resolve(game)
        p1_bf = list(game.get_battlefield(p1).get_all())
        p2_bf = list(game.get_battlefield(p2).get_all())
        # Both players should have lost a creature
        p1_creatures = [c for c in p1_bf if CardType.CREATURE in getattr(c, "card_types", set())]
        p2_creatures = [c for c in p2_bf if CardType.CREATURE in getattr(c, "card_types", set())]
        assert len(p1_creatures) == 0
        assert len(p2_creatures) == 0

    def test_opponent_loses_1_life(self):
        """Each opponent loses 1 life."""
        game = create_game()
        p1, p2 = game.players
        c1 = _make_creature(name="Bear1", power=2, toughness=2, owner=p1, controller=p1)
        c2 = _make_creature(name="Bear2", power=2, toughness=2, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[c1])
        set_board_state(game, 1, battlefield=[c2])
        initial_life_p2 = p2.life
        spell = SocialSnub(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert p2.life == initial_life_p2 - 1

    def test_caster_gains_1_life(self):
        """Caster gains 1 life for each opponent."""
        game = create_game()
        p1, p2 = game.players
        c1 = _make_creature(name="Bear1", power=2, toughness=2, owner=p1, controller=p1)
        c2 = _make_creature(name="Bear2", power=2, toughness=2, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[c1])
        set_board_state(game, 1, battlefield=[c2])
        initial_life_p1 = p1.life
        spell = SocialSnub(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert p1.life == initial_life_p1 + 1

    def test_no_creatures_no_sacrifice(self):
        """If no player has creatures, no sacrifice but life changes still apply."""
        game = create_game()
        p1, p2 = game.players
        initial_life_p1 = p1.life
        initial_life_p2 = p2.life
        spell = SocialSnub(owner=p1, controller=p1)
        spell.on_resolve(game)
        # Life changes still apply
        assert p2.life == initial_life_p2 - 1
        assert p1.life == initial_life_p1 + 1
