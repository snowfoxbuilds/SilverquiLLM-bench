"""Tests for SOS 4 — Together as One (Converge)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


def _filler(name: str) -> Creature:
    c = Creature(name=name, base_power=0, base_toughness=1)
    return c


class TestProperties:
    def test_is_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_name_and_cost(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"
        assert card.mana_cost == ManaCost.parse("{6}")


class TestConverge:
    def test_two_colors_draws_damages_gains(self) -> None:
        """{6} paid with 2C+2W+2U → X=2: draw 2, deal 2, gain 2."""
        game = create_game()
        p0, p1 = game.players
        # Fill p1's library so it can draw.
        for i in range(3):
            p1.zones[Zone.LIBRARY].add(_filler(f"Lib{i}"))
        big = Creature(name="Wall", base_power=0, base_toughness=5)
        set_board_state(game, 1, battlefield=[big])
        spell = TogetherAsOne(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[spell],
                        mana={ManaType.COLORLESS: 2, ManaType.WHITE: 2, ManaType.BLUE: 2})
        before_hand = len(p1.zones[Zone.HAND].get_all())
        cast_spell(game, 0, "Together as One", targets=[p1, big])
        assert len(p1.zones[Zone.HAND].get_all()) - before_hand == 2
        assert big.damage_marked == 2
        assert p0.life == 22

    def test_colorless_only_is_x_zero(self) -> None:
        """{6} paid with only colorless → X=0: no draw, no damage, no life."""
        game = create_game()
        p0, p1 = game.players
        for i in range(3):
            p1.zones[Zone.LIBRARY].add(_filler(f"Lib{i}"))
        big = Creature(name="Wall", base_power=0, base_toughness=5)
        set_board_state(game, 1, battlefield=[big])
        spell = TogetherAsOne(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})
        cast_spell(game, 0, "Together as One", targets=[p1, big])
        assert len(p1.zones[Zone.HAND].get_all()) == 0
        assert big.damage_marked == 0
        assert p0.life == 20

    def test_damage_to_player(self) -> None:
        """X=3 damage dealt to a player target reduces their life."""
        game = create_game()
        p0, p1 = game.players
        spell = TogetherAsOne(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[spell],
                        mana={ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.BLACK: 2})
        # Target player for draw = p0 (empty library, drawing 3 from empty is
        # harmless here — we only assert damage/life). any-target = p1.
        cast_spell(game, 0, "Together as One", targets=[p0, p1])
        assert p1.life == 17  # 20 - 3
        assert p0.life == 23  # gained 3

    def test_five_colors(self) -> None:
        """All five colors spent → X=5 (converge max)."""
        game = create_game()
        p0, p1 = game.players
        for i in range(6):
            p0.zones[Zone.LIBRARY].add(_filler(f"Lib{i}"))
        spell = TogetherAsOne(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[spell], mana={
            ManaType.WHITE: 2, ManaType.BLUE: 1, ManaType.BLACK: 1,
            ManaType.RED: 1, ManaType.GREEN: 1,
        })
        cast_spell(game, 0, "Together as One", targets=[p0, p1])
        assert p0.life == 25  # gained 5
        assert p1.life == 15  # took 5
        assert len(p0.zones[Zone.HAND].get_all()) == 5  # drew 5

    def test_spell_goes_to_graveyard(self) -> None:
        game = create_game()
        p0, p1 = game.players
        spell = TogetherAsOne(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[spell], mana={ManaType.WHITE: 6})
        cast_spell(game, 0, "Together as One", targets=[p0, p1])
        assert game.get_graveyard(p0).contains(spell)
