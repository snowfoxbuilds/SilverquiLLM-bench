"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.casting import cast_spell as ecast
from engine.state_based_actions import resolve_state_based_actions
from engine.types import ManaCost, ManaType, Phase
from test_utils import create_game, set_board_state


class _OppGain(Instant):
    """Opponent instant: its controller gains 5 life. No targets."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Opp Gain")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 5


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _advance_to_p0_precombat_main(game):
    for _ in range(40):
        game.advance_phase()
        if game.active_player_index == 0 and game.phase == Phase.PRECOMBAT_MAIN:
            return
    raise AssertionError("did not reach p0 precombat main")


def _opp_spell_on_stack(game):
    p1 = game.players[1]
    opp = _OppGain(owner=p1, controller=p1)
    set_board_state(game, 1, hand=[opp], mana={ManaType.COLORLESS: 2, ManaType.RED: 1},
                    life=20)
    ecast(game, p1, opp)  # instant — goes on the stack, not resolved
    return opp, game.stack.peek()


class TestProperties:
    def test_is_instant_cost(self):
        c = ManaSculpt(owner=None)
        assert isinstance(c, Instant)
        assert c.mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_cannot_cast_empty_stack(self):
        game = create_game()
        assert ManaSculpt(owner=None).can_cast(game) is False


class TestCounter:
    def test_counters_target_spell(self):
        game = create_game()
        p0, p1 = game.players
        opp, target_so = _opp_spell_on_stack(game)
        ms = ManaSculpt(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[ms],
                        mana={ManaType.COLORLESS: 1, ManaType.BLUE: 2})
        p0._script.appendleft(target_so)
        ecast(game, p0, ms)
        _resolve_stack(game)
        # Opp spell countered → in graveyard, did NOT resolve (no life gain).
        assert game.get_graveyard(p1).contains(opp)
        assert p1.life == 20


class TestDelayedMana:
    def test_refund_with_wizard(self):
        game = create_game()
        p0, p1 = game.players
        wizard = Creature(name="Mentor", base_power=1, base_toughness=1,
                          subtypes={"Wizard"})
        opp, target_so = _opp_spell_on_stack(game)
        ms = ManaSculpt(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[wizard], hand=[ms],
                        mana={ManaType.COLORLESS: 1, ManaType.BLUE: 2})
        p0._script.appendleft(target_so)
        ecast(game, p0, ms)
        _resolve_stack(game)
        # Opp spell cost {2}{R} → 3 mana spent.
        _advance_to_p0_precombat_main(game)
        _resolve_stack(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 3

    def test_no_refund_without_wizard(self):
        game = create_game()
        p0, p1 = game.players
        opp, target_so = _opp_spell_on_stack(game)
        ms = ManaSculpt(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[ms],
                        mana={ManaType.COLORLESS: 1, ManaType.BLUE: 2})
        p0._script.appendleft(target_so)
        ecast(game, p0, ms)
        _resolve_stack(game)
        _advance_to_p0_precombat_main(game)
        _resolve_stack(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0
