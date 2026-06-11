"""Tests for SOS 4 — Together as One."""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


def _vanilla(n: int) -> list[Creature]:
    return [
        Creature(name=f"Filler {i}", mana_cost=ManaCost(generic=1),
                 base_power=1, base_toughness=1)
        for i in range(n)
    ]


class TestTogetherAsOneProperties:
    def test_name_and_cost(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"
        assert card.mana_cost == ManaCost.parse("{6}")
        assert CardType.SORCERY in card.card_types


class TestConverge:
    def test_three_colors_draw_damage_gain(self) -> None:
        """X=3: target player draws 3, opponent takes 3, controller gains 3."""
        game = create_game(deck1=_vanilla(12))
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1)
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.WHITE: 2, ManaType.BLUE: 2, ManaType.BLACK: 2},
        )
        library_before = len(p1.zones[Zone.LIBRARY])
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        assert len(p1.zones[Zone.HAND]) == 3  # hand was just the spell
        assert len(p1.zones[Zone.LIBRARY]) == library_before - 3
        assert p2.life == 17
        assert p1.life == 23
        assert p1.zones[Zone.GRAVEYARD].contains(spell)

    def test_colorless_cast_is_x_zero(self) -> None:
        """All-colorless payment: no draws, no damage, no life gain."""
        game = create_game(deck1=_vanilla(12))
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.COLORLESS: 6})
        library_before = len(p1.zones[Zone.LIBRARY])
        cast_spell(game, 0, "Together as One", targets=[p1, p2])
        assert len(p1.zones[Zone.HAND]) == 0
        assert len(p1.zones[Zone.LIBRARY]) == library_before
        assert p2.life == 20
        assert p1.life == 20

    def test_duplicate_colors_count_once(self) -> None:
        """{W}{W}{W}{U}{U}{U} spent is two colors, not six."""
        game = create_game(deck1=_vanilla(12))
        p1, p2 = game.players
        spell = TogetherAsOne(owner=p1)
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.WHITE: 3, ManaType.BLUE: 3},
        )
        cast_spell(game, 0, "Together as One", targets=[p2, p2])
        assert p2.life == 18
        assert p1.life == 22

    def test_damage_to_creature_target(self) -> None:
        """'Any target' may be a creature; X damage is lethal to a 3/3."""
        game = create_game(deck1=_vanilla(12))
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[bear])
        spell = TogetherAsOne(owner=p1)
        set_board_state(
            game, 0, hand=[spell],
            mana={ManaType.RED: 2, ManaType.GREEN: 2, ManaType.BLACK: 2},
        )
        cast_spell(game, 0, "Together as One", targets=[p1, bear])
        assert p2.zones[Zone.GRAVEYARD].contains(bear)
        assert not game.get_battlefield(p2).contains(bear)
        assert p1.life == 23
