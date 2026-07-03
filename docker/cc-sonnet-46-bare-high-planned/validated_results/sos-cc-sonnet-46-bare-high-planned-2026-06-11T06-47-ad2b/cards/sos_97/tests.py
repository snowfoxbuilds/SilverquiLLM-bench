"""Tests for Ral Zarek, Guest Lecturer (sos_97)."""

from __future__ import annotations

import cards.sos.sos_97.card_impl as ral_impl
from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import LoyaltyAbilityInstance, activate_ability
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, Zone
from test_utils import _resolve_top_of_stack, create_game


def _put_on_battlefield(game, player_index, card):
    p = game.players[player_index]
    card.owner = p
    card.controller = p
    p.zones[Zone.BATTLEFIELD].add(card)
    if hasattr(card, "register_triggers"):
        card.register_triggers(game)


def _activate_loyalty(game, player_index, ral, ability_index):
    p = game.players[player_index]
    abilities = ral.get_loyalty_abilities()
    ab = abilities[ability_index]
    instance = LoyaltyAbilityInstance(
        source=ral, controller=p, loyalty_cost=ab.loyalty_cost, effect=ab.effect
    )
    activate_ability(game, p, instance)


class TestRalProperties:
    def test_name(self) -> None:
        assert RalZarekGuestLecturer().name == "Ral Zarek, Guest Lecturer"

    def test_starting_loyalty(self) -> None:
        assert RalZarekGuestLecturer().starting_loyalty == 3

    def test_is_planeswalker(self) -> None:
        assert CardType.PLANESWALKER in RalZarekGuestLecturer().card_types

    def test_mana_cost(self) -> None:
        ral = RalZarekGuestLecturer()
        assert ral.mana_cost == ManaCost.parse("{1}{B}{B}")


class TestSurveil:
    def test_plus1_puts_card_in_graveyard(self) -> None:
        """Surveil 2: choosing yes sends cards to graveyard."""
        game = create_game()
        p1, p2 = game.players
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        ral = RalZarekGuestLecturer()
        _put_on_battlefield(game, 0, ral)

        # Put 2 cards on top of library
        c1 = Instant(name="C1", mana_cost=ManaCost.parse("{1}"))
        c2 = Instant(name="C2", mana_cost=ManaCost.parse("{2}"))
        c1.owner = p1; c1.controller = p1
        c2.owner = p1; c2.controller = p1
        p1.zones[Zone.LIBRARY].add(c1)  # bottom
        p1.zones[Zone.LIBRARY].add(c2)  # top (drawn first when surveiling)

        # Script: yes to gy for top card (c2), no for c1
        p1._script.appendleft(False)  # c1: keep
        p1._script.appendleft(True)   # c2: graveyard

        _activate_loyalty(game, 0, ral, 0)  # +1
        _resolve_top_of_stack(game)

        assert p1.zones[Zone.GRAVEYARD].contains(c2)
        assert p1.zones[Zone.LIBRARY].contains(c1)
        assert ral.loyalty == 4  # 3 + 1

    def test_plus1_keep_all(self) -> None:
        """Surveil 2: choosing no keeps both cards in library."""
        game = create_game()
        p1, p2 = game.players
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        ral = RalZarekGuestLecturer()
        _put_on_battlefield(game, 0, ral)

        c1 = Instant(name="C1", mana_cost=ManaCost.parse("{1}"))
        c2 = Instant(name="C2", mana_cost=ManaCost.parse("{2}"))
        for c in [c1, c2]:
            c.owner = p1; c.controller = p1
            p1.zones[Zone.LIBRARY].add(c)

        p1._script.appendleft(False)  # keep c1
        p1._script.appendleft(False)  # keep c2

        _activate_loyalty(game, 0, ral, 0)
        _resolve_top_of_stack(game)

        assert p1.zones[Zone.LIBRARY].contains(c1)
        assert p1.zones[Zone.LIBRARY].contains(c2)


class TestDiscard:
    def test_minus1_discards_targeted_player_card(self) -> None:
        """−1: targeted player discards a card."""
        game = create_game()
        p1, p2 = game.players
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        ral = RalZarekGuestLecturer()
        ral.loyalty = 5  # enough for -1
        _put_on_battlefield(game, 0, ral)

        hand_card = Instant(name="Card", mana_cost=ManaCost.parse("{1}"))
        hand_card.owner = p2; hand_card.controller = p2
        p2.zones[Zone.HAND].add(hand_card)

        # Script: skip p1, target p2
        p1._script.appendleft(hand_card)  # p2 choose_card
        p1._script.appendleft(True)       # target p2
        p1._script.appendleft(False)      # don't target p1

        _activate_loyalty(game, 0, ral, 1)  # -1
        _resolve_top_of_stack(game)

        assert not p2.zones[Zone.HAND].contains(hand_card)
        assert p2.zones[Zone.GRAVEYARD].contains(hand_card)

    def test_minus1_skipping_all_no_discard(self) -> None:
        """−1: choosing no targets means no one discards."""
        game = create_game()
        p1, p2 = game.players
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        ral = RalZarekGuestLecturer()
        ral.loyalty = 5
        _put_on_battlefield(game, 0, ral)

        hand_card = Instant(name="Card", mana_cost=ManaCost.parse("{1}"))
        hand_card.owner = p1; hand_card.controller = p1
        p1.zones[Zone.HAND].add(hand_card)

        # Script: skip both players
        p1._script.appendleft(False)  # skip p2
        p1._script.appendleft(False)  # skip p1

        _activate_loyalty(game, 0, ral, 1)
        _resolve_top_of_stack(game)

        assert p1.zones[Zone.HAND].contains(hand_card)


class TestReanimate:
    def test_minus2_returns_creature_from_graveyard(self) -> None:
        """−2: returns a creature card with MV ≤ 3 from graveyard."""
        game = create_game()
        p1, p2 = game.players
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        ral = RalZarekGuestLecturer()
        ral.loyalty = 5
        _put_on_battlefield(game, 0, ral)

        target = Creature(name="Squire", base_power=1, base_toughness=1,
                          mana_cost=ManaCost.parse("{W}"))
        target.owner = p1; target.controller = p1
        p1.zones[Zone.GRAVEYARD].add(target)

        p1._script.appendleft(target)
        _activate_loyalty(game, 0, ral, 2)  # -2
        _resolve_top_of_stack(game)

        assert game.get_battlefield(p1).contains(target)
        assert not p1.zones[Zone.GRAVEYARD].contains(target)

    def test_minus2_ignores_high_mv_creatures(self) -> None:
        """−2: creature with MV > 3 is not eligible."""
        game = create_game()
        p1, p2 = game.players
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        ral = RalZarekGuestLecturer()
        ral.loyalty = 5
        _put_on_battlefield(game, 0, ral)

        big = Creature(name="Dragon", base_power=5, base_toughness=5,
                       mana_cost=ManaCost.parse("{5}{R}{R}"))
        big.owner = p1; big.controller = p1
        p1.zones[Zone.GRAVEYARD].add(big)

        # No eligible targets → ability fizzles
        _activate_loyalty(game, 0, ral, 2)
        _resolve_top_of_stack(game)

        # Big creature stays in graveyard
        assert p1.zones[Zone.GRAVEYARD].contains(big)


class TestCoinFlipSkipTurns:
    def test_minus7_all_heads_skips_5_turns(self) -> None:
        """−7: all heads → opponent skips 5 turns."""
        game = create_game()
        p1, p2 = game.players
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        ral = RalZarekGuestLecturer()
        ral.loyalty = 10  # enough for -7
        _put_on_battlefield(game, 0, ral)

        # Override coin flip to always return heads
        original_fn = ral_impl._coin_flip_fn
        ral_impl._coin_flip_fn = lambda: True

        try:
            p1._script.appendleft(p2)  # choose p2 as target
            _activate_loyalty(game, 0, ral, 3)  # -7
            _resolve_top_of_stack(game)
        finally:
            ral_impl._coin_flip_fn = original_fn

        assert getattr(p2, "turns_to_skip", 0) == 5

    def test_minus7_all_tails_skips_0_turns(self) -> None:
        """−7: all tails → no turns skipped."""
        game = create_game()
        p1, p2 = game.players
        game.phase = __import__("engine.types", fromlist=["Phase"]).Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        ral = RalZarekGuestLecturer()
        ral.loyalty = 10
        _put_on_battlefield(game, 0, ral)

        original_fn = ral_impl._coin_flip_fn
        ral_impl._coin_flip_fn = lambda: False  # all tails

        try:
            p1._script.appendleft(p2)
            _activate_loyalty(game, 0, ral, 3)
            _resolve_top_of_stack(game)
        finally:
            ral_impl._coin_flip_fn = original_fn

        assert getattr(p2, "turns_to_skip", 0) == 0
