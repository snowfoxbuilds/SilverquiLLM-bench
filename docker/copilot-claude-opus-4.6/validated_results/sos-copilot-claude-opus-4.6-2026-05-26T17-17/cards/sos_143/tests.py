"""Tests for SOS 143 — Comforting Counsel.

Comforting Counsel is a {1}{G} Enchantment:
  Whenever you gain life, put a growth counter on this enchantment.
  As long as there are five or more growth counters on this enchantment,
  creatures you control get +3/+3.
"""

from __future__ import annotations

from cards.sos.sos_143.card_impl import ComfortingCounsel
from engine.card import Creature, Enchantment
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestComfortingCounselProperties:
    """Static card data should match spec."""

    def test_is_enchantment(self) -> None:
        assert isinstance(ComfortingCounsel(owner=None), Enchantment)

    def test_name(self) -> None:
        assert ComfortingCounsel(owner=None).name == "Comforting Counsel"

    def test_mana_cost(self) -> None:
        assert ComfortingCounsel(owner=None).mana_cost == ManaCost.parse("{1}{G}")


class TestComfortingCounselTriggeredAbility:
    """Gaining life adds growth counters."""

    def _setup_game(self):
        game = create_game()
        p1 = game.players[0]

        counsel = ComfortingCounsel(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[counsel])
        return game, p1, counsel

    def test_starts_with_zero_counters(self) -> None:
        """Enchantment starts with no growth counters."""
        game, p1, counsel = self._setup_game()
        counters = getattr(counsel, 'growth_counters', 0)
        assert counters == 0

    def test_life_gain_adds_counter(self) -> None:
        """Gaining life puts one growth counter on the enchantment."""
        game, p1, counsel = self._setup_game()

        # Simulate life gain event
        p1.life += 3  # Gain 3 life (single event)
        counsel.on_life_gained(game, p1, 3)

        assert counsel.growth_counters == 1

    def test_multiple_life_gain_events_add_multiple_counters(self) -> None:
        """Each life gain event adds one counter (not one per life point)."""
        game, p1, counsel = self._setup_game()

        counsel.on_life_gained(game, p1, 2)
        counsel.on_life_gained(game, p1, 5)
        counsel.on_life_gained(game, p1, 1)

        assert counsel.growth_counters == 3


class TestComfortingCounselStaticAbility:
    """Five+ growth counters grants +3/+3 to creatures you control."""

    def _setup_game_with_counters(self, count):
        game = create_game()
        p1 = game.players[0]

        counsel = ComfortingCounsel(owner=p1, controller=p1)
        counsel.growth_counters = count

        bear = Creature(
            name="Test Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[counsel, bear])
        return game, p1, counsel, bear

    def test_four_counters_no_buff(self) -> None:
        """With fewer than 5 counters, no buff is applied."""
        game, p1, counsel, bear = self._setup_game_with_counters(4)
        assert bear.get_power() == 2
        assert bear.get_toughness() == 2

    def test_five_counters_grants_buff(self) -> None:
        """With exactly 5 counters, creatures get +3/+3."""
        game, p1, counsel, bear = self._setup_game_with_counters(5)
        assert bear.get_power() == 5
        assert bear.get_toughness() == 5

    def test_more_than_five_counters_still_grants_buff(self) -> None:
        """With more than 5 counters, buff still applies (not scaled)."""
        game, p1, counsel, bear = self._setup_game_with_counters(10)
        assert bear.get_power() == 5
        assert bear.get_toughness() == 5

    def test_opponent_creatures_not_buffed(self) -> None:
        """Only your creatures get the buff."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        counsel = ComfortingCounsel(owner=p1, controller=p1)
        counsel.growth_counters = 5

        enemy = Creature(
            name="Enemy Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        enemy.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[counsel])
        set_board_state(game, 1, battlefield=[enemy])

        assert enemy.get_power() == 2
        assert enemy.get_toughness() == 2
