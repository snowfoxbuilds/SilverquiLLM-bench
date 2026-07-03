"""Tests for Together as One (sos_4)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.types import CardType, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


def _setup_cast(game, player_index, card, target1, target2, mana):
    """Script targets and mana, set sorcery-speed timing, cast."""
    from engine.casting import cast_spell as _cast
    p = game.players[player_index]
    set_board_state(game, player_index, hand=[card], mana=mana)
    game.active_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    # Append in reverse order so first popleft returns target1
    p._script.appendleft(target2)
    p._script.appendleft(target1)
    _cast(game, p, card)
    from test_utils import _resolve_top_of_stack
    _resolve_top_of_stack(game)


class TestTogetherAsOneBasic:
    def test_name_and_type(self) -> None:
        card = TogetherAsOne()
        assert card.name == "Together as One"
        assert CardType.SORCERY in card.card_types

    def test_x_zero_colorless_cast(self) -> None:
        """X=0 when only colorless mana spent — nothing happens."""
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne()
        _setup_cast(game, 0, card, p2, p2, {ManaType.COLORLESS: 6})
        assert p2.life == 20
        assert p1.life == 20

    def test_x_two_two_colors(self) -> None:
        """X=2: target player draws 2, damage target takes 2, controller gains 2."""
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne()
        # p2 draws, p2 takes damage; p1 (controller) gains life
        _setup_cast(game, 0, card, p2, p2, {ManaType.WHITE: 3, ManaType.BLUE: 3})
        assert p1.life == 22   # gained 2
        assert p2.life == 18   # took 2 damage

    def test_x_three_three_colors(self) -> None:
        """X=3 with 3 colors: p2 draws, p2 takes 3 damage, p1 gains 3."""
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne()
        # p2 draws (from empty library - harmless), p2 takes damage
        _setup_cast(
            game, 0, card, p2, p2,
            {ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.BLACK: 2},
        )
        assert p1.life == 23   # gained 3
        assert p2.life == 17   # took 3 damage

    def test_damage_to_creature(self) -> None:
        """Can deal X damage to a creature target."""
        from engine.card import Creature
        game = create_game()
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[bear])
        card = TogetherAsOne()
        # target player = p2 (draws), damage target = bear
        _setup_cast(game, 0, card, p2, bear, {ManaType.WHITE: 3, ManaType.GREEN: 3})
        assert bear.damage_marked == 2   # X=2 damage to creature
        assert p1.life == 22             # gained 2

    def test_life_gain_goes_to_controller(self) -> None:
        """Controller gains life even when p1 is also the target player."""
        game = create_game()
        p1, p2 = game.players
        card = TogetherAsOne()
        # Controller (p1) is also the drawing player; p2 takes damage
        _setup_cast(game, 0, card, p1, p2, {ManaType.RED: 3, ManaType.GREEN: 3})
        assert p1.life == 22
        assert p2.life == 18
