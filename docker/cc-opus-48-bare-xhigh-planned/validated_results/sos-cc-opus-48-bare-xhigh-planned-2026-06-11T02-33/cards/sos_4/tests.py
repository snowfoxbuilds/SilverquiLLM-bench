"""Tests for SOS 4 — Together as One (Converge)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import CardImpl, Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, cast_spell, set_board_state


def _fill_library(game, player_index, n):
    lib = game.players[player_index].zones[Zone.LIBRARY]
    for i in range(n):
        lib.add(CardImpl(name=f"Filler{i}"))


class TestProperties:
    def test_is_sorcery(self):
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_name_and_cost(self):
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"
        assert card.mana_cost == ManaCost.parse("{6}")


class TestConverge:
    def test_three_colors(self):
        game = create_game()
        p0, p1 = game.players
        _fill_library(game, 0, 5)
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)],
                        mana={ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.BLACK: 2})
        # Target player p0 draws, damage target p1.
        cast_spell(game, 0, "Together as One", targets=[p0, p1])
        assert len(game.get_hand(p0).get_all()) == 3   # drew X=3
        assert p1.life == 17                            # dealt 3
        assert p0.life == 23                            # gained 3

    def test_zero_colors_all_colorless(self):
        game = create_game()
        p0, p1 = game.players
        _fill_library(game, 0, 5)
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)],
                        mana={ManaType.COLORLESS: 6})
        cast_spell(game, 0, "Together as One", targets=[p0, p1])
        assert len(game.get_hand(p0).get_all()) == 0   # X=0 draws nothing
        assert p1.life == 20
        assert p0.life == 20

    def test_two_colors_damage_kills_creature(self):
        game = create_game()
        p0, p1 = game.players
        _fill_library(game, 0, 5)
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[bear])
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)],
                        mana={ManaType.WHITE: 3, ManaType.BLUE: 3})
        cast_spell(game, 0, "Together as One", targets=[p0, bear])
        # X=2: 2 damage to a 2-toughness creature → dies (SBA after resolve).
        assert not game.get_battlefield(p1).contains(bear)
        assert game.get_graveyard(p1).contains(bear)
        assert len(game.get_hand(p0).get_all()) == 2
        assert p0.life == 22

    def test_target_opponent_draws(self):
        game = create_game()
        p0, p1 = game.players
        _fill_library(game, 1, 5)
        set_board_state(game, 0, hand=[TogetherAsOne(owner=None)],
                        mana={ManaType.WHITE: 3, ManaType.BLUE: 3})
        # Opponent p1 is the target player who draws; damage to p1 too.
        cast_spell(game, 0, "Together as One", targets=[p1, p1])
        assert len(game.get_hand(p1).get_all()) == 2   # opponent drew X=2
        assert p1.life == 18                            # dealt 2
        assert p0.life == 22                            # caster gained 2
