"""Tests for SOS 189 — Fractal Mascot.

Fractal Mascot is a {4}{G}{U} Creature — Fractal Elk (6/6):
"Trample
When this creature enters, tap target creature an opponent controls.
Put a stun counter on it."
"""

from __future__ import annotations

from cards.sos.sos_189.card_impl import FractalMascot
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestFractalMascotProperties:
    """Static card data should match the SOS 189 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(FractalMascot(owner=None), Creature)

    def test_name(self) -> None:
        assert FractalMascot(owner=None).name == "Fractal Mascot"

    def test_mana_cost(self) -> None:
        assert FractalMascot(owner=None).mana_cost == ManaCost.parse("{4}{G}{U}")

    def test_power_toughness(self) -> None:
        card = FractalMascot(owner=None)
        assert card.base_power == 6
        assert card.base_toughness == 6

    def test_has_trample(self) -> None:
        card = FractalMascot(owner=None)
        assert Keyword.TRAMPLE in card.keywords


class TestFractalMascotETB:
    """When enters, tap target opponent creature and put a stun counter on it."""

    def test_taps_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        mascot = FractalMascot(owner=p1, controller=p1)
        target = Creature(name="Enemy Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        target.card_types = {CardType.CREATURE}
        target.tapped = False

        set_board_state(game, 0, battlefield=[mascot])
        set_board_state(game, 1, battlefield=[target])

        mascot.chosen_targets = [target]
        mascot.on_enter_battlefield(game)

        assert target.tapped is True

    def test_puts_stun_counter_on_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        mascot = FractalMascot(owner=p1, controller=p1)
        target = Creature(name="Enemy Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        target.card_types = {CardType.CREATURE}
        target.tapped = False

        set_board_state(game, 0, battlefield=[mascot])
        set_board_state(game, 1, battlefield=[target])

        mascot.chosen_targets = [target]
        mascot.on_enter_battlefield(game)

        stun_counters = getattr(target, "stun_counters", 0)
        assert stun_counters >= 1

    def test_no_target_is_noop(self) -> None:
        """If no valid target (or no target chosen), resolution doesn't crash."""
        game = create_game()
        p1 = game.players[0]

        mascot = FractalMascot(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[mascot])

        # No chosen targets
        mascot.chosen_targets = []
        mascot.on_enter_battlefield(game)  # should not raise
