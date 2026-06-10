"""Tests for SOS 97 — Ral Zarek, Guest Lecturer (planeswalker)."""

from __future__ import annotations

import random

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    AbilityError,
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import CardImpl, Creature
from engine.state_based_actions import resolve_state_based_actions
from engine.types import ManaCost, Phase, Supertype, Zone
from test_utils import create_game, set_board_state


def _resolve_all(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _setup(loyalty=None):
    clear_loyalty_tracking()
    game = create_game()
    p0, p1 = game.players
    pw = RalZarekGuestLecturer(owner=p0, controller=p0)
    if loyalty is not None:
        pw.loyalty = loyalty
    set_board_state(game, 0, battlefield=[pw])
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0
    return game, p0, p1, pw


def _activate(game, player, pw, index, targets=None, scripts=None):
    ab = pw.get_loyalty_abilities()[index]
    if targets is not None:
        pw.chosen_targets = targets
    if scripts:
        player._script.extend(scripts)
    inst = LoyaltyAbilityInstance(source=pw, controller=player,
                                  loyalty_cost=ab.loyalty_cost, effect=ab.effect)
    activate_ability(game, player, inst)
    _resolve_all(game)


def _lib_add(game, idx, cards_bottom_to_top):
    lib = game.players[idx].zones[Zone.LIBRARY]
    for c in cards_bottom_to_top:
        c.owner = game.players[idx]
        c.controller = game.players[idx]
        lib.add(c)


class TestProperties:
    def test_static(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.starting_loyalty == 3 and card.loyalty == 3
        assert "Ral" in card.subtypes
        assert Supertype.LEGENDARY in card.supertypes
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert len(card.get_loyalty_abilities()) == 4


class TestPlusOneSurveil:
    def test_surveil_bins_one_keeps_one(self) -> None:
        game, p0, p1, pw = _setup()
        cardB = CardImpl(name="Keep")
        cardA = CardImpl(name="Bin")
        _lib_add(game, 0, [cardB, cardA])  # top = cardA
        _activate(game, p0, pw, 0, scripts=[True, False])  # bin A, keep B
        assert game.get_graveyard(p0).contains(cardA)
        assert game.get_library(p0).contains(cardB)
        assert pw.loyalty == 4  # +1


class TestMinusOneDiscard:
    def test_target_player_discards(self) -> None:
        game, p0, p1, pw = _setup()
        card = CardImpl(name="Gone")
        set_board_state(game, 1, hand=[card])
        pw.chosen_targets = [p1]
        p1._script.extend([card])  # p1 chooses what to discard
        ab = pw.get_loyalty_abilities()[1]
        inst = LoyaltyAbilityInstance(source=pw, controller=p0,
                                      loyalty_cost=ab.loyalty_cost, effect=ab.effect)
        activate_ability(game, p0, inst)
        _resolve_all(game)
        assert game.get_graveyard(p1).contains(card)
        assert pw.loyalty == 2  # -1

    def test_zero_targets_no_discard(self) -> None:
        game, p0, p1, pw = _setup()
        set_board_state(game, 1, hand=[CardImpl(name="Safe")])
        _activate(game, p0, pw, 1, targets=[])
        assert len(game.get_graveyard(p1).get_all()) == 0
        assert pw.loyalty == 2


class TestMinusTwoReanimate:
    def test_returns_small_creature(self) -> None:
        game, p0, p1, pw = _setup()
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{2}"))
        set_board_state(game, 0, graveyard=[bear])
        _activate(game, p0, pw, 2, targets=[bear])
        assert game.get_battlefield(p0).contains(bear)
        assert not game.get_graveyard(p0).contains(bear)
        assert pw.loyalty == 1  # -2

    def test_high_mv_not_returned(self) -> None:
        game, p0, p1, pw = _setup()
        giant = Creature(name="Giant", base_power=7, base_toughness=7,
                         mana_cost=ManaCost.parse("{6}{G}"))
        set_board_state(game, 0, graveyard=[giant])
        _activate(game, p0, pw, 2, targets=[giant])
        assert game.get_graveyard(p0).contains(giant)  # MV 7 > 3 → stays
        assert not game.get_battlefield(p0).contains(giant)


class TestUltimate:
    def test_requires_seven_loyalty(self) -> None:
        game, p0, p1, pw = _setup(loyalty=3)
        pw.chosen_targets = [p1]
        ab = pw.get_loyalty_abilities()[3]
        inst = LoyaltyAbilityInstance(source=pw, controller=p0,
                                      loyalty_cost=ab.loyalty_cost, effect=ab.effect)
        with pytest.raises(AbilityError):
            activate_ability(game, p0, inst)

    def test_skip_turns_equals_heads(self) -> None:
        game, p0, p1, pw = _setup(loyalty=7)
        seed = 42
        ref = random.Random(seed)
        expected = sum(ref.randint(0, 1) for _ in range(5))
        game.rng = random.Random(seed)
        _activate(game, p0, pw, 3, targets=[p1])
        assert p1.skip_turns == expected
        assert 0 <= expected <= 5
        assert pw.loyalty == 0  # -7

    def test_zero_heads_skips_nothing(self) -> None:
        game, p0, p1, pw = _setup(loyalty=7)

        class _AllTails:
            def randint(self, a, b):
                return 0

        game.rng = _AllTails()
        _activate(game, p0, pw, 3, targets=[p1])
        assert p1.skip_turns == 0
