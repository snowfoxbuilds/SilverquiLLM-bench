"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from engine.card import Creature, Instant
from engine.types import ManaType, Zone
from cards.sos.sos_4.card_impl import TogetherAsOne
from test_utils import create_game, set_board_state, cast_spell


def _library_filler(n: int) -> list[Instant]:
    return [Instant(name=f"Filler {i}") for i in range(n)]


class TestTogetherAsOne:
    def test_three_colors_draw_damage_lifegain(self) -> None:
        """X=3: target player draws 3, damage target takes 3, you gain 3."""
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne()
        set_board_state(
            game, 0, hand=[card],
            mana={ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1,
                  ManaType.COLORLESS: 3},
        )
        for c in _library_filler(5):
            c.owner = p2
            p2.zones[Zone.LIBRARY].add(c)
        cast_spell(game, 0, "Together as One", targets=[p2, p2])
        assert len(p2.zones[Zone.HAND]) == 3
        assert p2.life == 20 - 3
        assert p1.life == 20 + 3
        assert p1.zones[Zone.GRAVEYARD].contains(card)

    def test_colorless_only_x_zero(self) -> None:
        """All-colorless payment → X=0: no draws, no damage, no life gain."""
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne()
        set_board_state(game, 0, hand=[card], mana={ManaType.COLORLESS: 6})
        for c in _library_filler(3):
            c.owner = p2
            p2.zones[Zone.LIBRARY].add(c)
        cast_spell(game, 0, "Together as One", targets=[p2, p2])
        assert len(p2.zones[Zone.HAND]) == 0
        assert p2.life == 20
        assert p1.life == 20

    def test_damage_kills_creature(self) -> None:
        """'Any target' may be a creature; lethal X damage puts it in the graveyard."""
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne()
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(
            game, 0, hand=[card],
            mana={ManaType.RED: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 4},
        )
        set_board_state(game, 1, battlefield=[bear])
        cast_spell(game, 0, "Together as One", targets=[p1, bear])
        assert p2.zones[Zone.GRAVEYARD].contains(bear)
        assert not p2.zones[Zone.BATTLEFIELD].contains(bear)
        assert p1.life == 20 + 2

    def test_controller_can_be_the_drawing_player(self) -> None:
        """'Target player' can be the caster."""
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne()
        set_board_state(
            game, 0, hand=[card],
            mana={ManaType.GREEN: 1, ManaType.COLORLESS: 5},
        )
        for c in _library_filler(2):
            c.owner = p1
            p1.zones[Zone.LIBRARY].add(c)
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        assert len(p1.zones[Zone.HAND]) == 1
        assert p2.life == 19
        assert p1.life == 21
