"""Tests for SOS 4 — Together as One (Converge sorcery)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


def _stock_library(game, player, n: int = 6) -> None:
    """Give *player* a library of vanilla creatures to draw from."""
    lib = player.zones[Zone.LIBRARY]
    for obj in lib.get_all():
        lib.remove(obj)
    for i in range(n):
        lib.add(Creature(name=f"Bear{i}", owner=player, controller=player,
                          base_power=1, base_toughness=1))


class TestProperties:
    def test_is_sorcery(self) -> None:
        assert isinstance(TogetherAsOne(owner=None), Sorcery)

    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")


class TestConverge:
    def test_three_colors_draws_damages_and_gains(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, p1, 6)

        together = TogetherAsOne(owner=p1, controller=p1)
        set_board_state(
            game, 0,
            hand=[together],
            mana={ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.RED: 2},
            life=20,
        )
        set_board_state(game, 1, life=20)

        # Target player to draw = p1; "any target" for damage = p2.
        cast_spell(game, 0, "Together as One", targets=[p1, p2])

        assert len(getattr(together, "colors_spent", [])) == 3
        assert len(p1.zones[Zone.HAND].get_all()) == 3   # drew X=3
        assert p2.life == 17                              # took X=3 damage
        assert p1.life == 23                              # gained X=3 life

    def test_zero_colors_is_harmless(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, p1, 6)

        together = TogetherAsOne(owner=p1, controller=p1)
        # Pay the full {6} with colorless mana → X = 0.
        set_board_state(
            game, 0,
            hand=[together],
            mana={ManaType.COLORLESS: 6},
            life=20,
        )
        set_board_state(game, 1, life=20)

        cast_spell(game, 0, "Together as One", targets=[p1, p2])

        assert len(getattr(together, "colors_spent", [])) == 0
        assert len(p1.zones[Zone.HAND].get_all()) == 0   # drew nothing
        assert p2.life == 20                             # no damage
        assert p1.life == 20                             # no life gain

    def test_damage_can_target_a_creature(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _stock_library(game, p1, 6)

        bear = Creature(name="Grizzly", owner=p2, controller=p2,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        set_board_state(game, 1, battlefield=[bear])

        together = TogetherAsOne(owner=p1, controller=p1)
        set_board_state(
            game, 0,
            hand=[together],
            mana={ManaType.WHITE: 3, ManaType.BLUE: 3},
            life=20,
        )

        cast_spell(game, 0, "Together as One", targets=[p1, bear])

        assert len(getattr(together, "colors_spent", [])) == 2
        assert bear.damage_marked == 2
