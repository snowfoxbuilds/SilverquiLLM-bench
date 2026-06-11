"""Tests for Mana Sculpt (sos_57)."""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.casting import cast_spell as engine_cast
from engine.state_based_actions import resolve_state_based_actions
from engine.types import ManaCost, ManaType, Phase
from test_utils import create_game, set_board_state


class DamageInstant(Instant):
    """{2}{R} — deal 4 damage to the non-active player (mana value/spent = 3)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Damage Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        from engine.game import deal_damage
        deal_damage(game, self, game.non_active_player, 4)


def _resolve_stack(game):
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _advance_to_my_next_precombat(game, player_index, after_turn):
    for _ in range(60):
        game.advance_phase()
        if (game.phase is Phase.PRECOMBAT_MAIN
                and game.active_player_index == player_index
                and game.turn_number > after_turn):
            break
    _resolve_stack(game)


def _setup_counter(wizard=False):
    """p1 casts a DamageInstant; p0 casts Mana Sculpt targeting it."""
    game = create_game()
    p0, p1 = game.players
    bf = []
    if wizard:
        bf.append(Creature(name="Adept", base_power=1, base_toughness=1, subtypes={"Wizard"}))
    set_board_state(game, 0, battlefield=bf, hand=[ManaSculpt(owner=None)],
                    mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
    set_board_state(game, 1, hand=[DamageInstant(owner=None)],
                    mana={ManaType.RED: 1, ManaType.COLORLESS: 2})
    # p1 casts the target spell (goes on the stack with mana_spent = 3).
    p1_spell = game.get_hand(p1).get_all()[0]
    engine_cast(game, p1, p1_spell)
    target_so = game.stack.peek()
    # p0 counters it.
    p0._script.append(target_so)
    sculpt = game.get_hand(p0).get_all()[0]
    engine_cast(game, p0, sculpt)
    _resolve_stack(game)
    return game, p0, p1, p1_spell


class TestProperties:
    def test_static(self):
        c = ManaSculpt(owner=None)
        assert c.name == "Mana Sculpt"
        assert c.mana_cost == ManaCost.parse("{1}{U}{U}")


class TestCounter:
    def test_counters_target_spell(self):
        game, p0, p1, p1_spell = _setup_counter(wizard=False)
        # Spell was countered → in graveyard, never dealt damage.
        assert game.get_graveyard(p1).contains(p1_spell)
        assert p0.life == 20

    def test_cannot_cast_without_target(self):
        game = create_game()
        p0 = game.players[0]
        set_board_state(game, 0, hand=[ManaSculpt(owner=None)],
                        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        sculpt = game.get_hand(p0).get_all()[0]
        with pytest.raises(Exception):
            engine_cast(game, p0, sculpt)


class TestDelayedMana:
    def test_wizard_adds_mana_next_main(self):
        game, p0, p1, _ = _setup_counter(wizard=True)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0  # not yet
        _advance_to_my_next_precombat(game, 0, after_turn=1)
        # mana spent on the countered spell was 3 → add {C}{C}{C}
        assert p0.mana_pool.get(ManaType.COLORLESS) == 3

    def test_no_wizard_no_mana(self):
        game, p0, p1, _ = _setup_counter(wizard=False)
        _advance_to_my_next_precombat(game, 0, after_turn=1)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0
