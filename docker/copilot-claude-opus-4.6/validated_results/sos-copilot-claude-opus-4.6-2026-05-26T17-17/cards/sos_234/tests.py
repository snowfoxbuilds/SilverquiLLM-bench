"""Tests for SOS 234 — Stirring Honormancer.

Creature — Rhino Bard {2}{W}{W/B}{B} 4/5
When this creature enters, look at the top X cards of your library,
where X is the number of creatures you control. Put one of those cards
into your hand and the rest into your graveyard.
"""

from __future__ import annotations

from cards.sos.sos_234.card_impl import StirringHonormancer
from engine.card import Creature
from engine.types import ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestStirringHonormancerProperties:
    """Static card data should match the SOS 234 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(StirringHonormancer(owner=None), Creature)

    def test_name(self) -> None:
        assert StirringHonormancer(owner=None).name == "Stirring Honormancer"

    def test_mana_cost(self) -> None:
        assert StirringHonormancer(owner=None).mana_cost == ManaCost.parse("{2}{W}{W/B}{B}")

    def test_power_toughness(self) -> None:
        card = StirringHonormancer(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 5


class TestStirringHonormancerETB:
    """ETB: look at top X cards (X = creatures you control), put 1 to hand rest to graveyard."""

    def test_with_one_creature_looks_at_one_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        honormancer = StirringHonormancer(owner=p1, controller=p1)
        # Honormancer itself is on battlefield (counts as 1 creature)
        set_board_state(game, 0, battlefield=[honormancer])
        hand_before = len(game.get_hand(p1).get_all())
        honormancer.on_enter(game)
        hand_after = len(game.get_hand(p1).get_all())
        # Should put 1 card into hand (look at 1, put that 1 into hand)
        assert hand_after - hand_before == 1

    def test_with_three_creatures_puts_two_into_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        honormancer = StirringHonormancer(owner=p1, controller=p1)
        bear1 = Creature(name="Bear A", base_power=2, base_toughness=2)
        bear2 = Creature(name="Bear B", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[honormancer, bear1, bear2])
        gy_before = len(game.get_graveyard(p1).get_all())
        honormancer.on_enter(game)
        gy_after = len(game.get_graveyard(p1).get_all())
        # Look at 3 cards, 1 to hand, 2 to graveyard
        assert gy_after - gy_before == 2

    def test_zero_creatures_does_nothing(self) -> None:
        """If somehow X=0, no cards are looked at."""
        game = create_game()
        p1 = game.players[0]
        honormancer = StirringHonormancer(owner=p1, controller=p1)
        # Not on battlefield yet, so 0 creatures controlled
        set_board_state(game, 0, battlefield=[])
        hand_before = len(game.get_hand(p1).get_all())
        honormancer.on_enter(game)
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after == hand_before
