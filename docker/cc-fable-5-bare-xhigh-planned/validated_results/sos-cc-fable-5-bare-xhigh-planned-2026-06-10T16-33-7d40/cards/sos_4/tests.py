"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Instant, Sorcery
from engine.types import ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _stock_library(player, count: int) -> None:
    """Put *count* filler cards into a player's library."""
    library = player.zones[Zone.LIBRARY]
    for i in range(count):
        card = Instant(name=f"Filler{i}", mana_cost=ManaCost.parse("{U}"))
        card.owner = player
        card.controller = player
        library.add(card)


class TestTogetherAsOneProperties:
    def test_static_data(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)
        assert card.name == "Together as One"
        assert card.mana_cost == ManaCost.parse("{6}")


class TestTogetherAsOneConverge:
    def test_three_colors_draw_damage_life(self) -> None:
        game = create_game()
        p0, p1 = game.players
        bear = Creature(name="Ox", base_power=4, base_toughness=4)
        set_board_state(
            game, 0,
            hand=[TogetherAsOne(owner=None)],
            mana={ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.BLACK: 2},
        )
        set_board_state(game, 1, battlefield=[bear])
        _stock_library(p1, 5)

        cast_spell(game, 0, "Together as One", targets=[p1, bear])

        # X = 3 (white, blue, black spent on the {6} cost)
        assert len(p1.zones[Zone.HAND]) == 3
        assert bear.damage_marked == 3
        assert p0.life == 23

    def test_colorless_cast_is_x_zero(self) -> None:
        game = create_game()
        p0, p1 = game.players
        bear = Creature(name="Ox", base_power=4, base_toughness=4)
        set_board_state(
            game, 0,
            hand=[TogetherAsOne(owner=None)],
            mana={ManaType.COLORLESS: 6},
        )
        set_board_state(game, 1, battlefield=[bear])
        _stock_library(p1, 5)

        cast_spell(game, 0, "Together as One", targets=[p1, bear])

        assert len(p1.zones[Zone.HAND]) == 0
        assert bear.damage_marked == 0
        assert p0.life == 20

    def test_any_target_can_be_a_player(self) -> None:
        game = create_game()
        p0, p1 = game.players
        set_board_state(
            game, 0,
            hand=[TogetherAsOne(owner=None)],
            mana={ManaType.RED: 3, ManaType.GREEN: 3},
        )
        _stock_library(p0, 5)

        # Controller targets themself for the draw and the opponent for damage.
        cast_spell(game, 0, "Together as One", targets=[p0, p1])

        # X = 2 (red + green)
        assert len(p0.zones[Zone.HAND]) == 2
        assert p1.life == 18
        assert p0.life == 22

    def test_x_counts_distinct_colors_not_amount(self) -> None:
        game = create_game()
        p0, p1 = game.players
        bear = Creature(name="Ox", base_power=4, base_toughness=4)
        set_board_state(
            game, 0,
            hand=[TogetherAsOne(owner=None)],
            mana={ManaType.GREEN: 6},
        )
        set_board_state(game, 1, battlefield=[bear])
        _stock_library(p1, 5)

        cast_spell(game, 0, "Together as One", targets=[p1, bear])

        # Six green mana paid, but only one distinct color: X = 1.
        assert len(p1.zones[Zone.HAND]) == 1
        assert bear.damage_marked == 1
        assert p0.life == 21

    def test_goes_to_graveyard_after_resolving(self) -> None:
        game = create_game()
        p0, p1 = game.players
        set_board_state(
            game, 0,
            hand=[TogetherAsOne(owner=None)],
            mana={ManaType.COLORLESS: 6},
        )
        cast_spell(game, 0, "Together as One", targets=[p1, p1])
        graveyard_names = [c.name for c in p0.zones[Zone.GRAVEYARD].get_all()]
        assert "Together as One" in graveyard_names
