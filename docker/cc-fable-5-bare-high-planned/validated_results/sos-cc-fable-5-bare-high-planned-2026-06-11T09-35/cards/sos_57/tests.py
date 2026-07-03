"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.casting import (
    CastingError,
    cast_spell as engine_cast,
    cast_spell_free,
    resolve_top,
)
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from test_utils import advance_to_phase, create_game, set_board_state


class _Boom(Instant):
    """Test instant ({2}): deal 5 damage to the opponent of its controller."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Boom")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        for p in game.players:
            if p is not self.controller:
                p.life -= 5


def _wizard():
    return Creature(name="Apprentice", base_power=1, base_toughness=1,
                    subtypes={"Wizard"})


def _counter_setup(game, *, wizard, free_cast=False):
    """P2 casts Boom; P1 counters it with Mana Sculpt. Returns the sculpt."""
    p1, p2 = game.players
    boom = _Boom(owner=None)
    if free_cast:
        set_board_state(game, 1, graveyard=[boom])
        cast_spell_free(game, p2, boom, Zone.GRAVEYARD)
    else:
        set_board_state(game, 1, hand=[boom], mana={ManaType.COLORLESS: 2})
        engine_cast(game, p2, boom)

    sculpt = ManaSculpt(owner=None)
    bf = [_wizard()] if wizard else []
    set_board_state(game, 0, battlefield=bf, hand=[sculpt],
                    mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
    p1._script.append(game.stack.peek())  # target: Boom on the stack
    engine_cast(game, p1, sculpt)
    while not game.stack.is_empty():
        resolve_top(game)
    return boom, sculpt


class TestManaSculptCounter:
    def test_counters_target_spell(self):
        game = create_game()
        p1, p2 = game.players
        advance_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
        boom, sculpt = _counter_setup(game, wizard=True)

        assert p1.life == 20, "Boom was countered"
        assert p2.zones[Zone.GRAVEYARD].contains(boom)
        assert p1.zones[Zone.GRAVEYARD].contains(sculpt)

    def test_cannot_cast_with_empty_stack(self):
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt(owner=None)
        set_board_state(game, 0, hand=[sculpt],
                        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        with pytest.raises(CastingError):
            engine_cast(game, p1, sculpt)


class TestManaSculptDelayedMana:
    def test_wizard_grants_colorless_at_next_main(self):
        game = create_game()
        p1 = game.players[0]
        advance_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
        boom, sculpt = _counter_setup(game, wizard=True)

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        while not game.stack.is_empty():
            resolve_top(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 2, \
            "Boom cost {2} — add that much {C}"
        assert game.trigger_manager.get_triggers_for_source(sculpt) == []

    def test_one_shot_does_not_repeat_next_turn(self):
        game = create_game()
        p1 = game.players[0]
        advance_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
        boom, sculpt = _counter_setup(game, wizard=True)

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        while not game.stack.is_empty():
            resolve_top(game)
        assert game.trigger_manager.get_triggers_for_source(sculpt) == []

        # Two more turns to P1's next precombat main: no more mana.
        for _ in range(2):
            advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
            advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        while not game.stack.is_empty():
            resolve_top(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_no_wizard_no_delayed_mana(self):
        game = create_game()
        p1 = game.players[0]
        advance_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
        boom, sculpt = _counter_setup(game, wizard=False)

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        while not game.stack.is_empty():
            resolve_top(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
        assert game.trigger_manager.get_triggers_for_source(sculpt) == [], \
            "delayed trigger is consumed even without a Wizard"

    def test_free_cast_spell_grants_nothing(self):
        """Mana spent is the amount actually paid — 0 for a free cast."""
        game = create_game()
        p1 = game.players[0]
        advance_to_phase(game, Phase.BEGINNING, Step.UPKEEP)
        boom, sculpt = _counter_setup(game, wizard=True, free_cast=True)

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        while not game.stack.is_empty():
            resolve_top(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
