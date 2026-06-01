"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, Supertype
from test_utils import create_game, set_board_state


def _add_to_library(game, player, card) -> None:
    card.owner = player
    card.controller = player
    game.get_library(player).add(card)


def _abilities(ral):
    return ral.get_loyalty_abilities()


class TestRalProperties:
    def test_name_and_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert card.starting_loyalty == 3
        assert card.loyalty == 3

    def test_types(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert CardType.PLANESWALKER in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Ral" in card.subtypes

    def test_loyalty_costs(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        costs = [a.loyalty_cost for a in card.get_loyalty_abilities()]
        assert costs == [1, -1, -2, -7]


class TestRalSurveil:
    def test_surveil_2_bins_one_keeps_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        c1 = Creature(name="c1", base_power=1, base_toughness=1)
        c2 = Creature(name="c2", base_power=1, base_toughness=1)
        c3 = Creature(name="c3", base_power=1, base_toughness=1)
        for c in (c1, c2, c3):  # c3 ends on top, then c2, then c1
            _add_to_library(game, p1, c)

        # Surveil examines c3 (top) first, then c2.
        p1._script.append(True)   # bin c3
        p1._script.append(False)  # keep c2
        _abilities(ral)[0].effect(game)

        assert c3 in game.get_graveyard(p1).get_all()
        library = game.get_library(p1)
        assert library.top(1)[0] is c2  # kept card stays on top
        assert c1 in library.get_all()
        assert len(library.get_all()) == 2


class TestRalDiscard:
    def test_targeted_players_each_discard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        a = Creature(name="a", base_power=1, base_toughness=1)
        b = Creature(name="b", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[ral], hand=[a])
        set_board_state(game, 1, hand=[b])

        ral._resolve_targets = [p1, p2]
        p1._script.append(a)  # p1 discards a
        p2._script.append(b)  # p2 discards b
        _abilities(ral)[1].effect(game)

        assert a in game.get_graveyard(p1).get_all()
        assert b in game.get_graveyard(p2).get_all()
        assert len(game.get_hand(p1).get_all()) == 0
        assert len(game.get_hand(p2).get_all()) == 0

    def test_only_targeted_player_discards(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        keep = Creature(name="keep", base_power=1, base_toughness=1)
        gone = Creature(name="gone", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[keep])
        set_board_state(game, 1, hand=[gone])

        ral._resolve_targets = [p2]  # only p2 is targeted
        p2._script.append(gone)
        _abilities(ral)[1].effect(game)

        assert gone in game.get_graveyard(p2).get_all()
        assert keep in game.get_hand(p1).get_all()  # untargeted, unaffected


class TestRalReanimate:
    def test_returns_small_creature_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        small = Creature(
            name="Small", mana_cost=ManaCost.parse("{2}"), base_power=2, base_toughness=2
        )
        set_board_state(game, 0, battlefield=[ral], graveyard=[small])

        ral._resolve_target = small
        _abilities(ral)[2].effect(game)

        assert small in game.get_battlefield(p1).get_all()
        assert small not in game.get_graveyard(p1).get_all()

    def test_does_not_return_mv_4_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        big = Creature(
            name="Big", mana_cost=ManaCost.parse("{3}{G}"), base_power=4, base_toughness=4
        )
        set_board_state(game, 0, graveyard=[big])

        ral._resolve_target = big
        _abilities(ral)[2].effect(game)

        assert big in game.get_graveyard(p1).get_all()
        assert big not in game.get_battlefield(p1).get_all()

    def test_does_not_return_noncreature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        spell = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, graveyard=[spell])

        ral._resolve_target = spell
        _abilities(ral)[2].effect(game)

        assert spell in game.get_graveyard(p1).get_all()
        assert spell not in game.get_battlefield(p1).get_all()


class TestRalUltimate:
    def test_forced_heads_sets_skip_turns(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ral])

        ral._resolve_target = p2
        ral._forced_heads = 3
        _abilities(ral)[3].effect(game)

        assert game.skip_turns[1] == 3

    def test_zero_heads_no_skips(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        ral._resolve_target = p2
        ral._forced_heads = 0
        _abilities(ral)[3].effect(game)

        assert game.skip_turns[1] == 0

    def test_skips_accumulate_and_default_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        game.skip_turns[1] = 1  # already skipping one

        # No explicit target — defaults to the opponent.
        ral._forced_heads = 2
        _abilities(ral)[3].effect(game)

        assert game.skip_turns[1] == 3
