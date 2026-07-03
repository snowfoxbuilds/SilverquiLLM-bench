"""Tests for SOS 4 — Together as One (converge)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


def _deck(n: int) -> list[Creature]:
    return [
        Creature(name=f"Filler {i}", base_power=1, base_toughness=1)
        for i in range(n)
    ]


class TestTogetherAsOneProperties:
    def test_static_data(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)
        assert card.name == "Together as One"
        assert card.mana_cost == ManaCost.parse("{6}")


class TestTogetherAsOneConverge:
    def test_five_colors_draw_damage_life(self) -> None:
        game = create_game(deck1=_deck(20))
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1)
        set_board_state(
            game, 0, hand=[spell],
            mana={
                ManaType.COLORLESS: 1, ManaType.WHITE: 1, ManaType.BLUE: 1,
                ManaType.BLACK: 1, ManaType.RED: 1, ManaType.GREEN: 1,
            },
        )
        hand_before = len(game.get_hand(p1).get_all())
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        # X = 5: p1 draws 5, p2 takes 5 damage, p1 gains 5 life.
        assert len(game.get_hand(p1).get_all()) == hand_before - 1 + 5
        assert p2.life == 15
        assert p1.life == 25

    def test_two_colors(self) -> None:
        game = create_game(deck1=_deck(20))
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1)
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.COLORLESS: 4, ManaType.WHITE: 1, ManaType.BLUE: 1},
        )
        hand_before = len(game.get_hand(p1).get_all())
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        assert len(game.get_hand(p1).get_all()) == hand_before - 1 + 2
        assert p2.life == 18
        assert p1.life == 22

    def test_colorless_cast_is_all_zeroes(self) -> None:
        game = create_game(deck1=_deck(20))
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})
        hand_before = len(game.get_hand(p1).get_all())
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        assert len(game.get_hand(p1).get_all()) == hand_before - 1
        assert p2.life == 20
        assert p1.life == 20

    def test_any_target_can_be_a_creature(self) -> None:
        game = create_game(deck1=_deck(20), deck2=_deck(20))
        p1, p2 = game.players
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[bear])
        spell = TogetherAsOne(owner=p1)
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.COLORLESS: 4, ManaType.RED: 1, ManaType.GREEN: 1},
        )
        cast_spell(game, 0, "Together as One", targets=[p2, bear])
        # 2 damage to the 2/2 — lethal; SBAs put it into the graveyard.
        assert not game.get_battlefield(p2).contains(bear)
        assert game.get_graveyard(p2).contains(bear)
        assert p1.life == 22
