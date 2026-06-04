"""Tests for Ral Zarek, Guest Lecturer (SOS 97)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Sorcery
from engine.turn import run_turn
from engine.types import CardType, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


def _abilities(ral):
    return {ab.loyalty_cost: ab for ab in ral.get_loyalty_abilities()}


def _set_library(player, cards_bottom_to_top):
    lib = player.zones[Zone.LIBRARY]
    for c in lib.get_all():
        lib.remove(c)
    for c in cards_bottom_to_top:
        c.owner = player
        c.controller = player
        lib.add(c)  # appends -> last is top


class TestProperties:
    def test_static_data(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert card.starting_loyalty == 3
        assert card.loyalty == 3
        assert CardType.PLANESWALKER in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Ral" in card.subtypes

    def test_loyalty_abilities(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        costs = [ab.loyalty_cost for ab in card.get_loyalty_abilities()]
        assert costs == [1, -1, -2, -7]


class TestSurveil:
    def test_puts_both_cards_in_graveyard(self) -> None:
        game = create_game()
        p1, _ = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        a = Creature(name="A", base_power=1, base_toughness=1)
        b = Creature(name="B", base_power=1, base_toughness=1)
        _set_library(p1, [a, b])  # b is top
        p1._script.extend([True, True])  # graveyard the top (b), then a
        _abilities(ral)[1].effect(game)
        assert p1.zones[Zone.GRAVEYARD].contains(a)
        assert p1.zones[Zone.GRAVEYARD].contains(b)
        assert len(p1.zones[Zone.LIBRARY]) == 0

    def test_keeps_cards_on_top(self) -> None:
        game = create_game()
        p1, _ = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        a = Creature(name="A", base_power=1, base_toughness=1)
        b = Creature(name="B", base_power=1, base_toughness=1)
        _set_library(p1, [a, b])
        p1._script.extend([False, False])  # keep both
        _abilities(ral)[1].effect(game)
        assert len(p1.zones[Zone.LIBRARY]) == 2
        assert not p1.zones[Zone.GRAVEYARD].contains(a)

    def test_empty_library_noop(self) -> None:
        game = create_game()
        p1, _ = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        _set_library(p1, [])
        _abilities(ral)[1].effect(game)
        assert p1.remaining_choices == 0


class TestDiscard:
    def test_target_player_discards(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        card = Creature(name="Pitch", base_power=1, base_toughness=1)
        set_board_state(game, 1, hand=[card])
        ral.chosen_targets = [p2]
        p2._script.append(card)
        _abilities(ral)[-1].effect(game)
        assert p2.zones[Zone.GRAVEYARD].contains(card)
        assert not p2.zones[Zone.HAND].contains(card)

    def test_multiple_players_discard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        c1 = Creature(name="C1", base_power=1, base_toughness=1)
        c2 = Creature(name="C2", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[c1])
        set_board_state(game, 1, hand=[c2])
        ral.chosen_targets = [p1, p2]
        p1._script.append(c1)
        p2._script.append(c2)
        _abilities(ral)[-1].effect(game)
        assert p1.zones[Zone.GRAVEYARD].contains(c1)
        assert p2.zones[Zone.GRAVEYARD].contains(c2)

    def test_empty_targets_noop(self) -> None:
        game = create_game()
        p1, _ = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.chosen_targets = []
        _abilities(ral)[-1].effect(game)  # no error, no discards
        assert p1.remaining_choices == 0


class TestReanimate:
    def test_returns_low_mv_creature(self) -> None:
        game = create_game()
        p1, _ = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        bear = Creature(name="Bear", mana_cost=ManaCost.parse("{1}{G}"),
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[bear])
        ral._resolve_target = bear
        _abilities(ral)[-2].effect(game)
        assert game.get_battlefield(p1).contains(bear)
        assert not p1.zones[Zone.GRAVEYARD].contains(bear)

    def test_rejects_high_mv_creature(self) -> None:
        game = create_game()
        p1, _ = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        giant = Creature(name="Giant", mana_cost=ManaCost.parse("{3}{G}"),
                         base_power=4, base_toughness=4)
        set_board_state(game, 0, graveyard=[giant])
        ral._resolve_target = giant
        _abilities(ral)[-2].effect(game)
        assert p1.zones[Zone.GRAVEYARD].contains(giant)
        assert not game.get_battlefield(p1).contains(giant)

    def test_rejects_noncreature(self) -> None:
        game = create_game()
        p1, _ = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        spell = Sorcery(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, graveyard=[spell])
        ral._resolve_target = spell
        _abilities(ral)[-2].effect(game)
        assert p1.zones[Zone.GRAVEYARD].contains(spell)


class TestUltimate:
    def test_heads_set_skip_counter(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        p1._script.extend([True, True, True, False, False])  # 3 heads
        _abilities(ral)[-7].effect(game)
        assert getattr(p2, "_turns_to_skip", 0) == 3

    def test_zero_heads_no_skip(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        p1._script.extend([False, False, False, False, False])
        _abilities(ral)[-7].effect(game)
        assert getattr(p2, "_turns_to_skip", 0) == 0

    def test_explicit_target_opponent(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.chosen_targets = [p2]
        p1._script.extend([True, False, True, False, True])  # 3 heads
        _abilities(ral)[-7].effect(game)
        assert p2._turns_to_skip == 3

    def test_skip_counter_consumed_by_run_turn(self) -> None:
        game = create_game()
        p1, _ = game.players
        game.active_player_index = 0
        p1._turns_to_skip = 1
        start = game.turn_number
        run_turn(game)
        assert p1._turns_to_skip == 0
        assert game.turn_number == start + 1
