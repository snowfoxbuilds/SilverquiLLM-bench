"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import AbilityError, LoyaltyAbilityInstance, activate_ability
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase
from test_utils import create_game, set_board_state


def _activate(game, player, walker, index, targets=None):
    """Activate the walker's printed loyalty ability *index* and resolve it."""
    game.active_player_index = game.players.index(player)
    game.priority_player_index = game.players.index(player)
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    ability = walker.get_loyalty_abilities()[index]
    activate_ability(
        game,
        player,
        LoyaltyAbilityInstance(
            source=walker,
            controller=player,
            loyalty_cost=ability.loyalty_cost,
            effect=ability.effect,
            targets=list(targets or []),
        ),
    )
    # Priority passes happen before the resolving effect's own choices.
    for p in game.players:
        p._script.appendleft("pass")
    priority_loop(game)


def _put_on_top(game, player_index, card) -> None:
    player = game.players[player_index]
    card.owner = player
    card.controller = player
    game.get_library(player).add(card)


class TestStaticProperties:
    def test_walker_basics(self) -> None:
        ral = RalZarekGuestLecturer()
        assert ral.starting_loyalty == 3
        assert ral.loyalty == 3
        assert ral.mana_cost == ManaCost.parse("{1}{B}{B}")


class TestPlusOneSurveil:
    def test_surveil_two_bin_one_keep_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer()
        set_board_state(game, 0, battlefield=[ral])
        bottom = Instant(name="Bottom", mana_cost=ManaCost.parse("{1}"))
        keeper = Instant(name="Keeper", mana_cost=ManaCost.parse("{1}"))
        binned = Instant(name="Binned", mana_cost=ManaCost.parse("{1}"))
        for c in (bottom, keeper, binned):
            _put_on_top(game, 0, c)  # Binned ends on top
        # Top card (Binned) -> graveyard, second (Keeper) -> keep.
        p1._script.extend([True, False])
        _activate(game, p1, ral, 0)
        assert ral.loyalty == 4
        assert game.get_graveyard(p1).contains(binned)
        library = game.get_library(p1)
        assert library.top(1)[0] is keeper
        assert library.contains(bottom)


class TestMinusOneDiscard:
    def test_both_players_discard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer()
        set_board_state(game, 0, battlefield=[ral])
        c1 = Instant(name="P1 Card", mana_cost=ManaCost.parse("{1}"))
        c2 = Instant(name="P2 Card", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[c1])
        set_board_state(game, 1, hand=[c2])
        p1._script.extend([c1])
        p2._script.extend([c2])
        _activate(game, p1, ral, 1, targets=[p1, p2])
        assert ral.loyalty == 2
        assert game.get_graveyard(p1).contains(c1)
        assert game.get_graveyard(p2).contains(c2)

    def test_zero_target_players(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer()
        set_board_state(game, 0, battlefield=[ral])
        _activate(game, p1, ral, 1, targets=[])
        assert ral.loyalty == 2  # cost still paid; nothing else happens


class TestMinusTwoReanimate:
    def test_returns_cheap_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer()
        bear = Creature(name="Bear", mana_cost=ManaCost.parse("{1}{G}"), base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[ral], graveyard=[bear])
        _activate(game, p1, ral, 2, targets=[bear])
        assert ral.loyalty == 1
        assert game.get_battlefield(p1).contains(bear)
        assert not game.get_graveyard(p1).contains(bear)

    def test_mana_value_4_is_not_returned(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer()
        big = Creature(name="Big", mana_cost=ManaCost.parse("{3}{G}"), base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[ral], graveyard=[big])
        _activate(game, p1, ral, 2, targets=[big])
        assert game.get_graveyard(p1).contains(big)
        assert not game.get_battlefield(p1).contains(big)


class TestMinusSevenUltimate:
    def test_needs_seven_loyalty(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer()  # loyalty 3
        set_board_state(game, 0, battlefield=[ral])
        ability = ral.get_loyalty_abilities()[3]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        with pytest.raises(AbilityError):
            activate_ability(
                game,
                p1,
                LoyaltyAbilityInstance(
                    source=ral,
                    controller=p1,
                    loyalty_cost=ability.loyalty_cost,
                    effect=ability.effect,
                    targets=[p2],
                ),
            )

    def test_opponent_skips_x_turns(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer()
        ral.loyalty = 7
        set_board_state(game, 0, battlefield=[ral])
        game.rng = random.Random(7)
        reference = random.Random(7)
        expected_heads = sum(reference.randint(0, 1) for _ in range(5))
        assert expected_heads > 0  # seed sanity
        _activate(game, p1, ral, 3, targets=[p2])
        assert ral.loyalty == 0
        assert getattr(p2, "skip_turns", 0) == expected_heads

        # Drive the turn rotation: p1 stays active for the skipped turns.
        skipped = expected_heads
        for _ in range(skipped):
            from test_utils import advance_to_phase
            from engine.types import Step

            advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
            game.advance_phase()  # wrap to next turn
            assert game.active_player is p1  # p2's turn was skipped
        advance_again = game
        from test_utils import advance_to_phase
        from engine.types import Step

        advance_to_phase(advance_again, Phase.ENDING, Step.CLEANUP)
        game.advance_phase()
        assert game.active_player is p2  # skips exhausted
        assert getattr(p2, "skip_turns", 0) == 0

    def test_zero_heads_skips_nothing(self) -> None:
        game = create_game()
        p1, p2 = game.players

        class AllTails(random.Random):
            def randint(self, a, b):  # noqa: ARG002
                return 0

        ral = RalZarekGuestLecturer()
        ral.loyalty = 7
        set_board_state(game, 0, battlefield=[ral])
        game.rng = AllTails()
        _activate(game, p1, ral, 3, targets=[p2])
        assert getattr(p2, "skip_turns", 0) == 0
