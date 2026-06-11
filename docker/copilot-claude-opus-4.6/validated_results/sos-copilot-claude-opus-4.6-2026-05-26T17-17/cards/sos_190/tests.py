"""Tests for SOS 190 — Fractal Tender.

Fractal Tender is a {3}{G}{U} Creature — Elf Wizard (3/3):
"Ward {2}
Increment (Whenever you cast a spell, if the amount of mana you spent is greater
than this creature's power or toughness, put a +1/+1 counter on this creature.)
At the beginning of each end step, if you put a counter on this creature this turn,
create a 0/0 green and blue Fractal creature token and put three +1/+1 counters on it."
"""

from __future__ import annotations

from cards.sos.sos_190.card_impl import FractalTender
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestFractalTenderProperties:
    """Static card data should match the SOS 190 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(FractalTender(owner=None), Creature)

    def test_name(self) -> None:
        assert FractalTender(owner=None).name == "Fractal Tender"

    def test_mana_cost(self) -> None:
        assert FractalTender(owner=None).mana_cost == ManaCost.parse("{3}{G}{U}")

    def test_power_toughness(self) -> None:
        card = FractalTender(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_has_ward(self) -> None:
        card = FractalTender(owner=None)
        assert Keyword.WARD in card.keywords


class TestFractalTenderIncrement:
    """Increment triggers when a spell is cast with mana > power or toughness."""

    def test_gets_counter_when_spell_costs_more_than_power(self) -> None:
        game = create_game()
        p1 = game.players[0]

        tender = FractalTender(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[tender])

        # Simulate casting a spell that cost 4 mana (> 3 power)
        before_counters = getattr(tender, "plus_one_counters", 0)
        tender.on_spell_cast(game, mana_spent=4)

        assert tender.plus_one_counters == before_counters + 1

    def test_no_counter_when_spell_costs_equal_to_power(self) -> None:
        game = create_game()
        p1 = game.players[0]

        tender = FractalTender(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[tender])

        before_counters = getattr(tender, "plus_one_counters", 0)
        tender.on_spell_cast(game, mana_spent=3)

        assert tender.plus_one_counters == before_counters

    def test_no_counter_when_spell_costs_less_than_power(self) -> None:
        game = create_game()
        p1 = game.players[0]

        tender = FractalTender(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[tender])

        before_counters = getattr(tender, "plus_one_counters", 0)
        tender.on_spell_cast(game, mana_spent=2)

        assert tender.plus_one_counters == before_counters


class TestFractalTenderEndStep:
    """At end step, if counter was placed this turn, create a 0/0 Fractal with 3 +1/+1 counters."""

    def test_creates_fractal_token_if_counter_placed(self) -> None:
        game = create_game()
        p1 = game.players[0]

        tender = FractalTender(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[tender])

        # Simulate that a counter was placed this turn
        tender.counter_placed_this_turn = True
        tender.on_end_step(game)

        bf = game.get_battlefield(p1).get_all()
        fractals = [c for c in bf if "Fractal" in getattr(c, "name", "") and c is not tender]
        assert len(fractals) >= 1

    def test_fractal_token_has_three_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]

        tender = FractalTender(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[tender])

        tender.counter_placed_this_turn = True
        tender.on_end_step(game)

        bf = game.get_battlefield(p1).get_all()
        fractals = [c for c in bf if "Fractal" in getattr(c, "name", "") and c is not tender]
        assert len(fractals) >= 1
        fractal = fractals[0]
        assert fractal.plus_one_counters == 3

    def test_no_token_if_no_counter_placed(self) -> None:
        game = create_game()
        p1 = game.players[0]

        tender = FractalTender(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[tender])

        tender.counter_placed_this_turn = False
        tender.on_end_step(game)

        bf = game.get_battlefield(p1).get_all()
        fractals = [c for c in bf if "Fractal" in getattr(c, "name", "") and c is not tender]
        assert len(fractals) == 0
