"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _stock_library(game, player_index: int, count: int) -> list:
    """Put *count* filler cards into a player's library."""
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    cards = []
    for i in range(count):
        filler = Creature(name=f"Filler {i}", base_power=1, base_toughness=1)
        filler.owner = player
        filler.controller = player
        library.add(filler)
        cards.append(filler)
    return cards


class TestProperties:
    def test_static_data(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"
        assert card.mana_cost == ManaCost.parse("{6}")
        assert isinstance(card, Sorcery)


class TestConvergeThreeColors:
    def test_draw_damage_and_lifegain_scale_with_colors(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 1, 5)

        bear = Creature(name="Bear", base_power=4, base_toughness=4)
        set_board_state(game, 1, battlefield=[bear], life=20)

        spell = TogetherAsOne()
        # {6} paid with W+U+B+3 colorless → 3 colors spent.
        set_board_state(
            game, 0, hand=[spell], life=20,
            mana={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1,
                  ManaType.COLORLESS: 3},
        )

        cast_spell(game, 0, "Together as One", targets=[p2, bear])

        assert len(game.get_hand(p2)) == 3       # target player drew X
        assert bear.damage_marked == 3           # X damage to any target
        assert p1.life == 23                     # you gain X life
        assert game.get_graveyard(p1).contains(spell)


class TestConvergeZeroColors:
    def test_colorless_cast_does_nothing(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 1, 5)

        spell = TogetherAsOne()
        set_board_state(game, 0, hand=[spell], life=20,
                        mana={ManaType.COLORLESS: 6})
        set_board_state(game, 1, life=20)

        # "any target" may be a player too.
        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(game.get_hand(p2)) == 0
        assert p2.life == 20
        assert p1.life == 20


class TestConvergeFiveColorsPlayerTarget:
    def test_five_colors_damage_to_player(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, 1, 7)

        spell = TogetherAsOne()
        set_board_state(
            game, 0, hand=[spell], life=20,
            mana={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1,
                  ManaType.RED: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1},
        )
        set_board_state(game, 1, life=20)

        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(game.get_hand(p2)) == 5
        assert p2.life == 15
        assert p1.life == 25
