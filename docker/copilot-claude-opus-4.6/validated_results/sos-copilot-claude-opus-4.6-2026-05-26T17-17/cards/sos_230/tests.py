"""Tests for SOS 230 — Spirit Mascot.

A 2/2 Spirit Ox for {R}{W}.
Whenever one or more cards leave your graveyard, put a +1/+1 counter on this creature.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_230.card_impl import SpiritMascot
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestSpiritMascotProperties:
    """Static card data should match the SOS 230 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(SpiritMascot(owner=None), Creature)

    def test_name(self) -> None:
        assert SpiritMascot(owner=None).name == "Spirit Mascot"

    def test_mana_cost(self) -> None:
        assert SpiritMascot(owner=None).mana_cost == ManaCost.parse("{R}{W}")

    def test_power_toughness(self) -> None:
        card = SpiritMascot(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_no_keywords(self) -> None:
        """Spirit Mascot has no keywords."""
        card = SpiritMascot(owner=None)
        # Should have no special keywords (Flying, etc.)
        assert Keyword.FLYING not in card.keywords


class TestSpiritMascotTrigger:
    """Whenever one or more cards leave your graveyard, put a +1/+1 counter."""

    def test_gains_counter_when_card_leaves_graveyard(self) -> None:
        """Moving a card out of the graveyard should trigger +1/+1 counter."""
        game = create_game()
        p1 = game.players[0]

        mascot = SpiritMascot(owner=p1, controller=p1)
        game.get_battlefield(p1).add(mascot)

        # Put a card in graveyard
        card_in_gy = Creature(name="Dead Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        game.get_graveyard(p1).add(card_in_gy)

        counters_before = getattr(mascot, 'plus_one_counters', 0)

        # Remove card from graveyard (exile it)
        game.get_graveyard(p1).remove(card_in_gy)
        game.process_triggers()

        assert getattr(mascot, 'plus_one_counters', 0) == counters_before + 1

    def test_multiple_cards_leaving_gives_one_counter(self) -> None:
        """One or more cards leaving at once = only one +1/+1 counter."""
        game = create_game()
        p1 = game.players[0]

        mascot = SpiritMascot(owner=p1, controller=p1)
        game.get_battlefield(p1).add(mascot)

        # Put multiple cards in graveyard
        card1 = Creature(name="Dead Bear 1", owner=p1, controller=p1, base_power=2, base_toughness=2)
        card2 = Creature(name="Dead Bear 2", owner=p1, controller=p1, base_power=2, base_toughness=2)
        game.get_graveyard(p1).add(card1)
        game.get_graveyard(p1).add(card2)

        counters_before = getattr(mascot, 'plus_one_counters', 0)

        # Remove both cards simultaneously
        game.get_graveyard(p1).remove(card1)
        game.get_graveyard(p1).remove(card2)
        game.process_triggers()

        # Should only get ONE counter for the batch
        assert getattr(mascot, 'plus_one_counters', 0) == counters_before + 1

    def test_no_counter_when_opponent_graveyard(self) -> None:
        """Cards leaving the opponent's graveyard should NOT trigger."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        mascot = SpiritMascot(owner=p1, controller=p1)
        game.get_battlefield(p1).add(mascot)

        # Put card in opponent's graveyard
        opp_card = Creature(name="Opp Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        game.get_graveyard(p2).add(opp_card)

        counters_before = getattr(mascot, 'plus_one_counters', 0)

        # Remove from opponent's graveyard
        game.get_graveyard(p2).remove(opp_card)
        game.process_triggers()

        # No counter should be added
        assert getattr(mascot, 'plus_one_counters', 0) == counters_before

    def test_triggers_separately_for_separate_events(self) -> None:
        """Two separate leave-graveyard events should give two counters."""
        game = create_game()
        p1 = game.players[0]

        mascot = SpiritMascot(owner=p1, controller=p1)
        game.get_battlefield(p1).add(mascot)

        card1 = Creature(name="Dead Bear 1", owner=p1, controller=p1, base_power=2, base_toughness=2)
        card2 = Creature(name="Dead Bear 2", owner=p1, controller=p1, base_power=2, base_toughness=2)
        game.get_graveyard(p1).add(card1)
        game.get_graveyard(p1).add(card2)

        counters_before = getattr(mascot, 'plus_one_counters', 0)

        # First event
        game.get_graveyard(p1).remove(card1)
        game.process_triggers()

        # Second separate event
        game.get_graveyard(p1).remove(card2)
        game.process_triggers()

        # Two separate events = two counters
        assert getattr(mascot, 'plus_one_counters', 0) == counters_before + 2
