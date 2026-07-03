"""Tests for SOS 164 — Thornfist Striker.

A 3/3 Elf Druid for {2}{G} with:
- Ward {1}
- Infusion — Creatures you control get +1/+0 and have trample as long as
  you gained life this turn.
"""

from __future__ import annotations

from cards.sos.sos_164.card_impl import ThornfistStriker
from engine.card import Creature
from engine.types import Keyword, ManaCost
from test_utils import create_game


class TestThornfistStrikerProperties:
    """Static card data should match the SOS 164 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(ThornfistStriker(owner=None), Creature)

    def test_name(self) -> None:
        assert ThornfistStriker(owner=None).name == "Thornfist Striker"

    def test_mana_cost(self) -> None:
        assert ThornfistStriker(owner=None).mana_cost == ManaCost.parse("{2}{G}")

    def test_power_toughness(self) -> None:
        card = ThornfistStriker(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_has_ward(self) -> None:
        card = ThornfistStriker(owner=None)
        assert Keyword.WARD in card.keywords


class TestThornfistStrikerInfusion:
    """Infusion — all your creatures get +1/+0 and trample if gained life."""

    def test_no_bonus_without_life_gain(self) -> None:
        """Without life gain this turn, creatures have normal power."""
        game = create_game()
        p1 = game.players[0]
        striker = ThornfistStriker(owner=p1, controller=p1)
        game.get_battlefield(p1).add(striker)

        other = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2
        )
        game.get_battlefield(p1).add(other)

        assert other.get_power(game) == 2
        assert Keyword.TRAMPLE not in other.get_keywords(game)

    def test_plus_one_power_after_life_gain(self) -> None:
        """After gaining life this turn, all your creatures get +1/+0."""
        game = create_game()
        p1 = game.players[0]
        striker = ThornfistStriker(owner=p1, controller=p1)
        game.get_battlefield(p1).add(striker)

        other = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2
        )
        game.get_battlefield(p1).add(other)

        p1.life_gained_this_turn = 1
        assert other.get_power(game) == 3
        assert striker.get_power(game) == 4

    def test_trample_granted_after_life_gain(self) -> None:
        """After gaining life this turn, all your creatures have trample."""
        game = create_game()
        p1 = game.players[0]
        striker = ThornfistStriker(owner=p1, controller=p1)
        game.get_battlefield(p1).add(striker)

        other = Creature(
            name="Grizzly Bears", owner=p1, controller=p1,
            base_power=2, base_toughness=2
        )
        game.get_battlefield(p1).add(other)

        p1.life_gained_this_turn = 2
        assert Keyword.TRAMPLE in other.get_keywords(game)
        assert Keyword.TRAMPLE in striker.get_keywords(game)

    def test_opponent_creatures_not_affected(self) -> None:
        """Opponent's creatures should NOT get the infusion bonus."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        striker = ThornfistStriker(owner=p1, controller=p1)
        game.get_battlefield(p1).add(striker)

        opp_creature = Creature(
            name="Opp Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2
        )
        game.get_battlefield(p2).add(opp_creature)

        p1.life_gained_this_turn = 1
        assert opp_creature.get_power(game) == 2
        assert Keyword.TRAMPLE not in opp_creature.get_keywords(game)

    def test_toughness_unaffected_by_infusion(self) -> None:
        """Infusion gives +1/+0 only, toughness unchanged."""
        game = create_game()
        p1 = game.players[0]
        striker = ThornfistStriker(owner=p1, controller=p1)
        game.get_battlefield(p1).add(striker)
        p1.life_gained_this_turn = 1
        assert striker.get_toughness(game) == 3
