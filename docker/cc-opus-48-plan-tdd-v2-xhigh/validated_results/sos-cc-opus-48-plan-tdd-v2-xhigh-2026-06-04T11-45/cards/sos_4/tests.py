"""Tests for SOS 4 — Together as One (Converge sorcery)."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import ManaCost, Zone
from test_utils import create_game, set_board_state


def _vanilla(name: str) -> Creature:
    return Creature(name=name, base_power=1, base_toughness=1)


class TestTogetherAsOneProperties:
    def test_name(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"

    def test_mana_cost(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}")


class TestTogetherAsOneConverge:
    def test_three_colors(self) -> None:
        game = create_game()
        p1, p2 = game.players
        # Target player (p2) needs a library to draw from.
        lib = [_vanilla(f"L{i}") for i in range(5)]
        for c in lib:
            c.owner = p2
            c.controller = p2
            p2.zones[Zone.LIBRARY].add(c)
        target_creature = Creature(name="Bear", base_power=4, base_toughness=4)
        set_board_state(game, 1, battlefield=[target_creature])

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p2, target_creature]

        p1_life_before = p1.life
        p2_hand_before = len(p2.zones[Zone.HAND].get_all())
        card.on_resolve(game)

        assert len(p2.zones[Zone.HAND].get_all()) - p2_hand_before == 3
        assert target_creature.damage_marked == 3
        assert p1.life - p1_life_before == 3
