"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

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
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, create_game, set_board_state


@pytest.fixture(autouse=True)
def _clear_loyalty():
    clear_loyalty_tracking()
    yield
    clear_loyalty_tracking()


def _cast_ral(game):
    ral = RalZarekGuestLecturer()
    set_board_state(
        game, 0, hand=[ral],
        mana={ManaType.BLACK: 2, ManaType.COLORLESS: 1},
    )
    cast_spell(game, 0, "Ral Zarek, Guest Lecturer")
    return ral


def _activate(game, ral, index, p1_choices=(), p2_choices=()):
    """Activate the printed loyalty ability and resolve it.

    Effect choices are scripted *after* the priority passes, matching the
    order the engine asks for them.
    """
    p1, p2 = game.players
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    ability = ral.get_loyalty_abilities()[index]
    inst = LoyaltyAbilityInstance(
        source=ral, controller=p1,
        loyalty_cost=ability.loyalty_cost, effect=ability.effect,
    )
    activate_ability(game, p1, inst)
    p1._script.extend(["pass", *p1_choices])
    p2._script.extend(["pass", *p2_choices])
    priority_loop(game)


class TestRalZarek:
    def test_enters_with_three_loyalty(self):
        game = create_game()
        ral = _cast_ral(game)
        assert game.get_battlefield(game.players[0]).contains(ral)
        assert ral.loyalty == 3

    def test_plus1_surveil_two(self):
        game = create_game()
        p1 = game.players[0]
        ral = _cast_ral(game)
        bottom = Instant(name="Beneath", mana_cost=ManaCost.parse("{1}"))
        top = Instant(name="Topmost", mana_cost=ManaCost.parse("{1}"))
        for c in (bottom, top):
            c.owner = c.controller = p1
            p1.zones[Zone.LIBRARY].add(c)
        # Looking top-down: bin Topmost, keep Beneath.
        _activate(game, ral, 0, p1_choices=[True, False])
        assert ral.loyalty == 4
        assert game.get_graveyard(p1).contains(top)
        assert p1.zones[Zone.LIBRARY].top(1)[0] is bottom

    def test_minus1_each_target_player_discards(self):
        game = create_game()
        p1, p2 = game.players
        ral = _cast_ral(game)
        mine = Instant(name="Mine", mana_cost=ManaCost.parse("{1}"))
        theirs = Instant(name="Theirs", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[mine])
        set_board_state(game, 1, hand=[theirs])
        ral._resolve_targets = [p1, p2]
        _activate(game, ral, 1, p1_choices=[mine], p2_choices=[theirs])
        assert ral.loyalty == 2
        assert game.get_graveyard(p1).contains(mine)
        assert game.get_graveyard(p2).contains(theirs)

    def test_minus1_zero_targets(self):
        game = create_game()
        p1 = game.players[0]
        ral = _cast_ral(game)
        keep = Instant(name="Keep", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[keep])
        ral._resolve_targets = []
        _activate(game, ral, 1)
        assert ral.loyalty == 2
        assert game.get_hand(p1).contains(keep)

    def test_minus2_reanimates_cheap_creature(self):
        game = create_game()
        p1 = game.players[0]
        ral = _cast_ral(game)
        bear = Creature(name="Bear", mana_cost=ManaCost.parse("{1}{G}"),
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[bear])
        ral._resolve_target = bear
        _activate(game, ral, 2)
        assert ral.loyalty == 1
        assert game.get_battlefield(p1).contains(bear)
        assert not game.get_graveyard(p1).contains(bear)

    def test_minus2_rejects_mana_value_above_three(self):
        game = create_game()
        p1 = game.players[0]
        ral = _cast_ral(game)
        giant = Creature(name="Giant", mana_cost=ManaCost.parse("{3}{R}"),
                         base_power=5, base_toughness=5)
        set_board_state(game, 0, graveyard=[giant])
        ral._resolve_target = giant
        _activate(game, ral, 2)
        assert game.get_graveyard(p1).contains(giant)  # MV 4 — not returned
        assert ral.loyalty == 1  # loyalty still paid; ability did nothing

    def test_ultimate_requires_seven_loyalty(self):
        game = create_game()
        p1 = game.players[0]
        ral = _cast_ral(game)
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        ability = ral.get_loyalty_abilities()[3]
        inst = LoyaltyAbilityInstance(
            source=ral, controller=p1,
            loyalty_cost=ability.loyalty_cost, effect=ability.effect,
        )
        with pytest.raises(AbilityError):
            activate_ability(game, p1, inst)
        assert ral.loyalty == 3

    def test_ultimate_coin_flips_skip_turns(self):
        game = create_game()
        p1, p2 = game.players
        ral = _cast_ral(game)
        ral.loyalty = 8
        game.rng = random.Random(7)
        _expected_rng = random.Random(7)
        expected_heads = sum(_expected_rng.randint(0, 1) for _ in range(5))
        assert expected_heads > 0  # seed sanity for this test
        ral._resolve_target = p2
        _activate(game, ral, 3)
        assert ral.loyalty == 1
        assert game.skip_turns[1] == expected_heads

        # Behavioral check: every wrap hands the turn back to p1 until the
        # skips are used up, then p2 finally gets a turn.
        from engine.game_state import _TURN_SEQUENCE

        for _ in range(expected_heads):
            for _ in range(len(_TURN_SEQUENCE)):
                game.advance_phase()
            assert game.active_player is p1
        for _ in range(len(_TURN_SEQUENCE)):
            game.advance_phase()
        assert game.active_player is p2
