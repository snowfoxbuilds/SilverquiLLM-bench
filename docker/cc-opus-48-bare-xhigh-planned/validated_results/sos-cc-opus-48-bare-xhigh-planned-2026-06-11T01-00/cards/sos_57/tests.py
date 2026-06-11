"""Tests for Mana Sculpt (sos_57)."""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Sorcery
from engine.casting import cast_spell as engine_cast_spell
from engine.state_based_actions import resolve_state_based_actions
from engine.types import ManaCost, ManaType, Phase
from test_utils import create_game, set_board_state


class _GainLifeSorcery(Sorcery):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Big Heal")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 5


def _drain(game):
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _setup_counter(game, *, with_wizard: bool):
    """p0 casts a {3} sorcery, then counters it with Mana Sculpt in response."""
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0
    p0 = game.players[0]
    sculpt = ManaSculpt(owner=p0, controller=p0)
    target = _GainLifeSorcery(owner=p0, controller=p0)
    bf = []
    if with_wizard:
        bf = [Creature(name="Wiz", subtypes={"Wizard"}, base_power=1, base_toughness=1)]
    set_board_state(game, 0, battlefield=bf, hand=[sculpt, target])
    # Cast the target sorcery (mana value 3 spent).
    p0.mana_pool.empty()
    p0.mana_pool.add(ManaType.COLORLESS, 3)
    engine_cast_spell(game, p0, target)
    target_so = game.stack.peek()
    # Cast Mana Sculpt in response, targeting the sorcery on the stack.
    p0.mana_pool.add(ManaType.COLORLESS, 1)
    p0.mana_pool.add(ManaType.BLUE, 2)
    p0._script.append(target_so)
    engine_cast_spell(game, p0, sculpt)
    _drain(game)
    return p0, target


def _advance_to_p0_next_main(game, p0, after_turn, max_steps=40):
    for _ in range(max_steps):
        game.advance_phase()
        if (game.phase == Phase.PRECOMBAT_MAIN
                and game.active_player is p0
                and game.turn_number > after_turn):
            return
    raise AssertionError("did not reach p0's next precombat main")


class TestCounter:
    def test_counters_target_spell(self):
        game = create_game()
        p0, target = _setup_counter(game, with_wizard=False)
        # Target was countered: it's in the graveyard and never gained life.
        assert game.get_graveyard(p0).contains(target)
        assert p0.life == 20

    def test_cannot_cast_without_spell_on_stack(self):
        game = create_game()
        sculpt = ManaSculpt(owner=None)
        set_board_state(game, 0, hand=[sculpt],
                        mana={ManaType.COLORLESS: 1, ManaType.BLUE: 2})
        assert sculpt.can_cast(game) is False


class TestDelayedMana:
    def test_wizard_adds_mana_next_main(self):
        game = create_game()
        p0, _ = _setup_counter(game, with_wizard=True)
        cast_turn = game.turn_number
        _advance_to_p0_next_main(game, p0, cast_turn)
        _drain(game)  # resolve the delayed trigger
        assert p0.mana_pool.get(ManaType.COLORLESS) == 3  # mana spent on target

    def test_no_wizard_no_mana(self):
        game = create_game()
        p0, _ = _setup_counter(game, with_wizard=False)
        cast_turn = game.turn_number
        _advance_to_p0_next_main(game, p0, cast_turn)
        _drain(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0

    def test_one_shot_does_not_fire_twice(self):
        game = create_game()
        p0, _ = _setup_counter(game, with_wizard=True)
        cast_turn = game.turn_number
        _advance_to_p0_next_main(game, p0, cast_turn)
        _drain(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 3
        # Advance to a later p0 main phase; the one-shot must not fire again.
        later = game.turn_number
        p0.mana_pool.empty()
        _advance_to_p0_next_main(game, p0, later)
        _drain(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0
