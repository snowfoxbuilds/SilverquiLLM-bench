"""Tests for SOS 225 — Silverquill Charm.

Instant, {W}{B}. Choose one —
• Put two +1/+1 counters on target creature.
• Exile target creature with power 2 or less.
• Each opponent loses 3 life and you gain 3 life.
"""

from __future__ import annotations

from cards.sos.sos_225.card_impl import SilverquillCharm
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestSilverquillCharmProperties:
    """Static card data should match the SOS 225 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(SilverquillCharm(owner=None), Instant)

    def test_name(self) -> None:
        assert SilverquillCharm(owner=None).name == "Silverquill Charm"

    def test_mana_cost(self) -> None:
        assert SilverquillCharm(owner=None).mana_cost == ManaCost.parse("{W}{B}")


class TestSilverquillCharmModeOne:
    """Mode 1: Put two +1/+1 counters on target creature."""

    def test_adds_two_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(name="Bear", owner=p1, controller=p1,
                          base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(target)

        spell = SilverquillCharm(owner=p1, controller=p1)
        spell.chosen_mode = 1
        spell.chosen_targets = [target]
        spell.on_resolve(game)
        assert target.plus_one_counters == 2

    def test_can_target_any_creature(self) -> None:
        """Mode 1 can target any creature, regardless of power."""
        game = create_game()
        p1 = game.players[0]
        big = Creature(name="Big", owner=p1, controller=p1,
                       base_power=10, base_toughness=10)
        game.get_battlefield(p1).add(big)

        spell = SilverquillCharm(owner=p1, controller=p1)
        spell.chosen_mode = 1
        spell.chosen_targets = [big]
        spell.on_resolve(game)
        assert big.plus_one_counters == 2


class TestSilverquillCharmModeTwo:
    """Mode 2: Exile target creature with power 2 or less."""

    def test_exiles_creature_power_two_or_less(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        small = Creature(name="Small", owner=p2, controller=p2,
                         base_power=2, base_toughness=2)
        game.get_battlefield(p2).add(small)

        spell = SilverquillCharm(owner=p1, controller=p1)
        spell.chosen_mode = 2
        spell.chosen_targets = [small]
        spell.on_resolve(game)

        # Creature should be exiled (not on battlefield)
        bf_cards = [c for c in game.get_battlefield(p2).cards]
        assert small not in bf_cards

    def test_exiles_creature_power_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        tiny = Creature(name="Tiny", owner=p2, controller=p2,
                        base_power=0, base_toughness=4)
        game.get_battlefield(p2).add(tiny)

        spell = SilverquillCharm(owner=p1, controller=p1)
        spell.chosen_mode = 2
        spell.chosen_targets = [tiny]
        spell.on_resolve(game)

        bf_cards = [c for c in game.get_battlefield(p2).cards]
        assert tiny not in bf_cards

    def test_cannot_target_creature_power_greater_than_two(self) -> None:
        """Mode 2 should only be valid for power <= 2."""
        game = create_game()
        p1 = game.players[0]
        big = Creature(name="Big", owner=p1, controller=p1,
                       base_power=5, base_toughness=5)
        game.get_battlefield(p1).add(big)

        spell = SilverquillCharm(owner=p1, controller=p1)
        spell.chosen_mode = 2
        # Validate targeting restriction
        valid = spell.is_valid_target_for_mode(game, 2, big)
        assert valid is False


class TestSilverquillCharmModeThree:
    """Mode 3: Each opponent loses 3 life and you gain 3 life."""

    def test_opponent_loses_three_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        spell = SilverquillCharm(owner=p1, controller=p1)
        spell.chosen_mode = 3
        spell.chosen_targets = []
        spell.on_resolve(game)

        assert p2.life == 17  # 20 - 3

    def test_caster_gains_three_life(self) -> None:
        game = create_game()
        p1 = game.players[0]

        spell = SilverquillCharm(owner=p1, controller=p1)
        spell.chosen_mode = 3
        spell.chosen_targets = []
        spell.on_resolve(game)

        assert p1.life == 23  # 20 + 3

    def test_mode_three_no_target_required(self) -> None:
        """Mode 3 doesn't target, just affects opponents and controller."""
        game = create_game()
        p1 = game.players[0]

        spell = SilverquillCharm(owner=p1, controller=p1)
        spell.chosen_mode = 3
        spell.chosen_targets = []
        # Should not raise
        spell.on_resolve(game)
