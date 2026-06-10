"""Tests for SOS 4 — Together as One (Converge)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import ManaCost, ManaType, Zone
from test_utils import create_game, cast_spell, set_board_state


def _stock_library(player, n: int) -> None:
    """Put *n* filler cards into a player's library."""
    library = player.zones[Zone.LIBRARY]
    for i in range(n):
        library.add(Creature(name=f"Filler {i}", base_power=1, base_toughness=1))


class TestTogetherAsOneProperties:
    def test_name_and_cost(self) -> None:
        card = TogetherAsOne()
        assert card.name == "Together as One"
        assert card.mana_cost == ManaCost.parse("{6}")


class TestConverge:
    def test_three_colors_draw_damage_life(self) -> None:
        """Paying WWUUBB → X=3: opponent draws 3, other opponent target takes 3, you gain 3."""
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne()
        set_board_state(
            game, 0, hand=[card],
            mana={ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.BLACK: 2},
        )
        _stock_library(p2, 5)
        p1_life, p2_life = p1.life, p2.life

        # Target player = p2 (draws), any target = p2 (damage).
        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(p2.zones[Zone.HAND]) == 3
        assert p2.life == p2_life - 3
        assert p1.life == p1_life + 3
        assert p1.zones[Zone.GRAVEYARD].contains(card)

    def test_colorless_cast_is_x_zero(self) -> None:
        """Paying with 6 colorless → X=0: nothing happens."""
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne()
        set_board_state(game, 0, hand=[card], mana={ManaType.COLORLESS: 6})
        _stock_library(p2, 5)
        p1_life, p2_life = p1.life, p2.life

        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(p2.zones[Zone.HAND]) == 0
        assert p2.life == p2_life
        assert p1.life == p1_life

    def test_any_target_creature_lethal(self) -> None:
        """X=2 damage to a 2-toughness creature kills it via SBAs."""
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne()
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(
            game, 0, hand=[card],
            mana={ManaType.RED: 3, ManaType.GREEN: 3},
        )
        set_board_state(game, 1, battlefield=[bear])
        _stock_library(p1, 5)

        # Target player = self (draws 2), any target = Bear.
        cast_spell(game, 0, "Together as One", targets=[p1, bear])

        assert len(p1.zones[Zone.HAND]) == 2
        assert not p2.zones[Zone.BATTLEFIELD].contains(bear)
        assert p2.zones[Zone.GRAVEYARD].contains(bear)

    def test_two_colors_counts_distinct(self) -> None:
        """WWWWUU → only two distinct colors → X=2."""
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne()
        set_board_state(
            game, 0, hand=[card],
            mana={ManaType.WHITE: 4, ManaType.BLUE: 2},
        )
        _stock_library(p2, 5)
        p1_life = p1.life

        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        assert len(p2.zones[Zone.HAND]) == 2
        assert p1.life == p1_life + 2
