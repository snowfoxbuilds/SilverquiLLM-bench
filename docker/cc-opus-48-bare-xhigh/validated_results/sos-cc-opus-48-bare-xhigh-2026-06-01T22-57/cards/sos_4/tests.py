"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game


def _bear(name: str = "Bear") -> Creature:
    c = Creature(name=name, base_power=4, base_toughness=4)
    c.card_types = {CardType.CREATURE}
    return c


class TestProperties:
    def test_basics(self) -> None:
        c = TogetherAsOne(owner=None)
        assert c.name == "Together as One"
        assert c.mana_cost == ManaCost.parse("{6}")
        assert isinstance(c, Sorcery)


class TestResolve:
    def test_converge_draw_damage_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        # Library cards for p1 to draw.
        lib = p1.zones[Zone.LIBRARY]
        for i in range(3):
            lib.add(Sorcery(name=f"Card{i}", mana_cost=ManaCost.parse("{1}")))

        bear = _bear("Target")
        bear.owner = p2
        bear.controller = p2
        game.get_battlefield(p2).add(bear)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 2  # X = 2
        spell.chosen_targets = [p1, bear]

        p1.life = 20
        hand_before = len(p1.zones[Zone.HAND])
        spell.on_resolve(game)

        assert len(p1.zones[Zone.HAND]) == hand_before + 2
        assert bear.damage_marked == 2
        assert p1.life == 22

    def test_converge_zero_is_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bear = _bear("Target")
        bear.owner = p2
        bear.controller = p2
        game.get_battlefield(p2).add(bear)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = 0
        spell.chosen_targets = [p1, bear]
        p1.life = 20
        spell.on_resolve(game)
        assert bear.damage_marked == 0
        assert p1.life == 20

    def test_colors_spent_as_list(self) -> None:
        from engine.types import ManaType
        game = create_game()
        p1, p2 = game.players
        bear = _bear("Target")
        bear.owner = p2
        bear.controller = p2
        game.get_battlefield(p2).add(bear)

        spell = TogetherAsOne(owner=p1, controller=p1)
        # Pipeline supplies a list of Color/ManaType.
        spell.colors_spent = [ManaType.WHITE, ManaType.BLUE, ManaType.RED]
        spell.chosen_targets = [p1, bear]
        p1.life = 20
        spell.on_resolve(game)
        assert bear.damage_marked == 3
        assert p1.life == 23
