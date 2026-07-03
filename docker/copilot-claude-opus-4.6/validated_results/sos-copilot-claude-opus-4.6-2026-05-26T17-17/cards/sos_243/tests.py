"""Tests for SOS 243 — Wilt in the Heat.

Instant {2}{R}{W}
This spell costs {2} less to cast if one or more cards left your graveyard this turn.
Wilt in the Heat deals 5 damage to target creature. If that creature
would die this turn, exile it instead.
"""

from __future__ import annotations

from cards.sos.sos_243.card_impl import WiltInTheHeat
from engine.card import Creature, Instant
from engine.types import ManaCost, Zone
from test_utils import create_game, set_board_state


class TestWiltInTheHeatProperties:
    """Static card data should match the SOS 243 spec."""

    def test_name(self) -> None:
        card = WiltInTheHeat(owner=None)
        assert card.name == "Wilt in the Heat"

    def test_mana_cost(self) -> None:
        card = WiltInTheHeat(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{R}{W}")

    def test_is_instant(self) -> None:
        card = WiltInTheHeat(owner=None)
        assert isinstance(card, Instant)


class TestWiltInTheHeatDamage:
    """Deals 5 damage to target creature."""

    def test_deals_5_damage_to_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = WiltInTheHeat(owner=p1, controller=p1)
        target = Creature(name="Giant", base_power=4, base_toughness=7)
        target.owner = p2
        target.controller = p2
        set_board_state(game, 1, battlefield=[target])
        card.targets = [target]
        card.on_resolve(game)
        # 7 toughness - 5 damage = effectively 2 remaining
        assert target.damage_taken == 5

    def test_kills_creature_with_5_or_less_toughness(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = WiltInTheHeat(owner=p1, controller=p1)
        target = Creature(name="Bear", base_power=2, base_toughness=2)
        target.owner = p2
        target.controller = p2
        set_board_state(game, 1, battlefield=[target])
        card.targets = [target]
        card.on_resolve(game)
        bf = game.get_battlefield(p2).get_all()
        assert target not in bf


class TestWiltInTheHeatExileReplacement:
    """If that creature would die this turn, exile it instead."""

    def test_creature_killed_goes_to_exile_not_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = WiltInTheHeat(owner=p1, controller=p1)
        target = Creature(name="Bear", base_power=2, base_toughness=2)
        target.owner = p2
        target.controller = p2
        set_board_state(game, 1, battlefield=[target])
        card.targets = [target]
        card.on_resolve(game)
        # Target should be exiled, not in graveyard
        exile = p2.zones[Zone.EXILE].get_all()
        graveyard = p2.zones[Zone.GRAVEYARD].get_all()
        assert target in exile
        assert target not in graveyard

    def test_creature_survives_if_toughness_above_5(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = WiltInTheHeat(owner=p1, controller=p1)
        target = Creature(name="Wurm", base_power=6, base_toughness=6)
        target.owner = p2
        target.controller = p2
        set_board_state(game, 1, battlefield=[target])
        card.targets = [target]
        card.on_resolve(game)
        bf = game.get_battlefield(p2).get_all()
        assert target in bf


class TestWiltInTheHeatCostReduction:
    """Costs {2} less if a card left your graveyard this turn."""

    def test_cost_reduced_when_card_left_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WiltInTheHeat(owner=p1, controller=p1)
        # Simulate a card having left graveyard this turn
        game.cards_left_graveyard_this_turn = {p1: 1}
        effective_cost = card.get_effective_cost(game)
        expected = ManaCost.parse("{R}{W}")
        assert effective_cost == expected

    def test_no_reduction_when_no_card_left_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WiltInTheHeat(owner=p1, controller=p1)
        game.cards_left_graveyard_this_turn = {p1: 0}
        effective_cost = card.get_effective_cost(game)
        expected = ManaCost.parse("{2}{R}{W}")
        assert effective_cost == expected
