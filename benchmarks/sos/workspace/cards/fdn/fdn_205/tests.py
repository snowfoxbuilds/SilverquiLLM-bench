"""Reference test for FDN 205 — Wardens of the Cycle.

Illustrative test covering the **converge** / mana-color tracking mechanic.
The number of distinct colors of mana spent to cast this creature
determines how many Saproling tokens enter the battlefield. The engine
records this on the card as ``colors_spent`` during cost payment; the
card's ``on_resolve`` reads that value to drive token creation.
"""

from __future__ import annotations

from cards.fdn.fdn_205.card_impl import WardensOfTheCycle
from engine.card import Creature
from engine.types import ManaCost, Zone
from test_utils import create_game


class TestWardensProperties:
    """Static card data should match the FDN 205 spec."""

    def test_name(self) -> None:
        card = WardensOfTheCycle(owner=None)
        assert card.name == "Wardens of the Cycle"

    def test_mana_cost(self) -> None:
        card = WardensOfTheCycle(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{B}{G}")

    def test_power_toughness(self) -> None:
        card = WardensOfTheCycle(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4


class TestWardensConverge:
    """Converge: one Saproling per distinct color spent.

    The cast pipeline writes ``colors_spent`` onto the card from the
    payer's ``mana_pool.last_payment_colors``; the card reads it on
    resolution. These tests bypass the cast pipeline and set
    ``colors_spent`` directly so the converge logic can be exercised
    in isolation.
    """

    def test_colors_spent_defaults_to_zero(self) -> None:
        card = WardensOfTheCycle(owner=None)
        assert card.colors_spent == 0

    def test_two_colors_creates_two_saprolings(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WardensOfTheCycle(owner=p1, controller=p1)
        card.colors_spent = 2  # BG payment example
        before = len(game.get_battlefield(p1).get_all())
        card.on_resolve(game)
        after = len(game.get_battlefield(p1).get_all())
        assert after - before == 2

    def test_five_colors_creates_five_saprolings(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WardensOfTheCycle(owner=p1, controller=p1)
        card.colors_spent = 5  # WUBRG payment example
        before = len(game.get_battlefield(p1).get_all())
        card.on_resolve(game)
        after = len(game.get_battlefield(p1).get_all())
        assert after - before == 5

    def test_tokens_are_one_one_saprolings(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WardensOfTheCycle(owner=p1, controller=p1)
        card.colors_spent = 1
        card.on_resolve(game)
        bf_creatures = [
            obj for obj in game.get_battlefield(p1).get_all()
            if isinstance(obj, Creature) and "Saproling" in getattr(obj, "subtypes", set())
        ]
        assert len(bf_creatures) == 1
        tok = bf_creatures[0]
        assert tok.base_power == 1
        assert tok.base_toughness == 1
