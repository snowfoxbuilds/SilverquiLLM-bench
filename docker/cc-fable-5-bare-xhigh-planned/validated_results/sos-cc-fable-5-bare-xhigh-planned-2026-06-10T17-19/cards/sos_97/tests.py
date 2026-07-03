"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    AbilityError,
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import Creature
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import (
    _resolve_top_of_stack,
    advance_to_phase,
    cast_spell,
    create_game,
    set_board_state,
)


@pytest.fixture(autouse=True)
def _fresh_loyalty_tracking():
    clear_loyalty_tracking()
    yield
    clear_loyalty_tracking()


def _game_with_ral():
    game = create_game()
    p1 = game.players[0]
    ral = RalZarekGuestLecturer(owner=None)
    set_board_state(
        game, 0, hand=[ral],
        mana={ManaType.COLORLESS: 1, ManaType.BLACK: 2},
    )
    cast_spell(game, 0, "Ral Zarek, Guest Lecturer")
    assert game.get_battlefield(p1).contains(ral)
    return game, p1, ral


def _activate(game, ral, index, player, targets=None):
    if game.phase is not Phase.PRECOMBAT_MAIN:
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    ability = ral.get_loyalty_abilities()[index]
    instance = LoyaltyAbilityInstance(
        source=ral,
        controller=player,
        loyalty_cost=ability.loyalty_cost,
        effect=ability.effect,
        description=ability.description,
        targets=list(targets or []),
    )
    activate_ability(game, player, instance)
    _resolve_top_of_stack(game)


def _stock_library(player, cards):
    for card in cards:
        card.owner = card.controller = player
        player.zones[Zone.LIBRARY].add(card)


class TestRalStatics:
    def test_card_data(self):
        ral = RalZarekGuestLecturer(owner=None)
        assert ral.name == "Ral Zarek, Guest Lecturer"
        assert ral.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert ral.starting_loyalty == 3
        assert ral.loyalty == 3
        assert len(ral.get_loyalty_abilities()) == 4


class TestRalPlusOneSurveil:
    def test_surveil_two_bins_chosen_cards(self):
        game, p1, ral = _game_with_ral()
        deep = Creature(name="Deep", base_power=1, base_toughness=1)
        second = Creature(name="Second", base_power=1, base_toughness=1)
        top = Creature(name="Top", base_power=1, base_toughness=1)
        _stock_library(p1, [deep, second, top])
        p1._script.append(True)   # bin Top
        p1._script.append(False)  # keep Second
        _activate(game, ral, 0, p1)
        assert ral.loyalty == 4
        assert game.get_graveyard(p1).contains(top)
        library = game.get_library(p1)
        assert library.top(1)[0] is second
        assert library.contains(deep)


class TestRalMinusOneDiscard:
    def test_each_target_player_discards(self):
        game, p1, ral = _game_with_ral()
        p2 = game.players[1]
        mine = Creature(name="Mine", base_power=1, base_toughness=1)
        theirs = Creature(name="Theirs", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[mine])
        set_board_state(game, 1, hand=[theirs])
        p1._script.append(mine)    # my discard choice
        p2._script.append(theirs)  # their discard choice
        _activate(game, ral, 1, p1, targets=[p1, p2])
        assert ral.loyalty == 2
        assert game.get_graveyard(p1).contains(mine)
        assert game.get_graveyard(p2).contains(theirs)

    def test_zero_target_players(self):
        game, p1, ral = _game_with_ral()
        _activate(game, ral, 1, p1, targets=[])
        assert ral.loyalty == 2  # cost paid, nothing else happens


class TestRalMinusTwoReanimate:
    def test_returns_cheap_creature_from_graveyard(self):
        game, p1, ral = _game_with_ral()
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{1}{G}"))
        set_board_state(game, 0, graveyard=[bear])
        _activate(game, ral, 2, p1, targets=[bear])
        assert ral.loyalty == 1
        assert game.get_battlefield(p1).contains(bear)
        assert not game.get_graveyard(p1).contains(bear)

    def test_mana_value_above_three_stays_dead(self):
        game, p1, ral = _game_with_ral()
        giant = Creature(name="Giant", base_power=4, base_toughness=4,
                         mana_cost=ManaCost.parse("{3}{R}"))
        set_board_state(game, 0, graveyard=[giant])
        _activate(game, ral, 2, p1, targets=[giant])
        assert game.get_graveyard(p1).contains(giant)
        assert not game.get_battlefield(p1).contains(giant)


class TestRalUltimate:
    def test_requires_seven_loyalty(self):
        game, p1, ral = _game_with_ral()
        p2 = game.players[1]
        assert ral.loyalty == 3
        with pytest.raises(AbilityError):
            _activate(game, ral, 3, p1, targets=[p2])

    def test_opponent_skips_turns_equal_to_heads(self):
        game, p1, ral = _game_with_ral()
        p2 = game.players[1]
        ral.loyalty = 7  # test setup
        game.rng.seed(0)  # five flips → 4 heads
        _activate(game, ral, 3, p1, targets=[p2])
        assert ral.loyalty == 0
        assert getattr(p2, "skip_turns", 0) == 4
        # Drive the turn rotation: p2's next turns are skipped, so p1 is
        # active again on the following turn.
        from engine.types import Step

        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        game.advance_phase()
        assert game.active_player is p1
        assert p2.skip_turns == 3

    def test_zero_heads_skips_nothing(self):
        game, p1, ral = _game_with_ral()
        p2 = game.players[1]
        ral.loyalty = 7
        game.rng.seed(15)  # five flips → 0 heads
        _activate(game, ral, 3, p1, targets=[p2])
        assert getattr(p2, "skip_turns", 0) == 0
        from engine.types import Step

        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        game.advance_phase()
        assert game.active_player is p2  # normal rotation
