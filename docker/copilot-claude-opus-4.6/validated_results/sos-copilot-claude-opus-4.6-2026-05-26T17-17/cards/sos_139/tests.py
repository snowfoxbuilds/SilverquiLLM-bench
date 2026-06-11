"""Tests for SOS 139 — Additive Evolution.

A {3}{G}{G} Enchantment with two abilities:
1. ETB: Create a 0/0 green and blue Fractal creature token with three +1/+1 counters.
2. At the beginning of combat on your turn, put a +1/+1 counter on target
   creature you control. It gains vigilance until end of turn.
"""

from __future__ import annotations

from cards.sos.sos_139.card_impl import AdditiveEvolution
from engine.card import Creature, Enchantment
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestAdditiveEvolutionProperties:
    """Static card data should match the SOS 139 spec."""

    def test_is_enchantment(self) -> None:
        card = AdditiveEvolution(owner=None)
        assert isinstance(card, Enchantment)

    def test_name(self) -> None:
        card = AdditiveEvolution(owner=None)
        assert card.name == "Additive Evolution"

    def test_mana_cost(self) -> None:
        card = AdditiveEvolution(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{G}{G}")


class TestAdditiveEvolutionETB:
    """ETB creates a 0/0 green/blue Fractal token with three +1/+1 counters."""

    def test_creates_fractal_token_on_etb(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = AdditiveEvolution(owner=p1, controller=p1)
        bf_before = len(game.get_battlefield(p1).get_all())
        card.on_enter_battlefield(game)
        bf_after = len(game.get_battlefield(p1).get_all())

        # One token created
        assert bf_after - bf_before == 1

    def test_fractal_token_has_three_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = AdditiveEvolution(owner=p1, controller=p1)
        card.on_enter_battlefield(game)

        # Find the fractal token
        bf = game.get_battlefield(p1).get_all()
        fractals = [c for c in bf if "Fractal" in getattr(c, "subtypes", set())
                    or "Fractal" in getattr(c, "name", "")]
        assert len(fractals) >= 1
        fractal = fractals[0]

        # Should have 3 +1/+1 counters
        assert fractal.plus_one_counters == 3

    def test_fractal_token_base_stats_are_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = AdditiveEvolution(owner=p1, controller=p1)
        card.on_enter_battlefield(game)

        bf = game.get_battlefield(p1).get_all()
        fractals = [c for c in bf if "Fractal" in getattr(c, "subtypes", set())
                    or "Fractal" in getattr(c, "name", "")]
        assert len(fractals) >= 1
        fractal = fractals[0]

        assert fractal.base_power == 0
        assert fractal.base_toughness == 0


class TestAdditiveEvolutionCombatTrigger:
    """Beginning of combat: +1/+1 counter and vigilance on target creature."""

    def test_puts_counter_on_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = AdditiveEvolution(owner=p1, controller=p1)
        bear = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        bear.plus_one_counters = 0
        game.get_battlefield(p1).add(bear)

        card.chosen_targets = [bear]
        card.on_combat_begin(game)

        assert bear.plus_one_counters == 1

    def test_grants_vigilance_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]

        card = AdditiveEvolution(owner=p1, controller=p1)
        bear = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        bear.plus_one_counters = 0
        game.get_battlefield(p1).add(bear)

        card.chosen_targets = [bear]
        card.on_combat_begin(game)

        assert Keyword.VIGILANCE in bear.keywords
