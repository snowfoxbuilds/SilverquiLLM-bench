"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

import pytest

from engine.card import Creature
from engine.casting import CastingError, cast_spell as engine_cast
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Zone
from cards.sos.sos_57.card_impl import ManaSculpt
from test_utils import advance_to_phase, create_game, set_board_state


def _counter_setup(*, with_wizard: bool):
    """P2 casts a Bear; P1 counters it with Mana Sculpt. Returns game, cards."""
    game = create_game(scripts=(["pass"] * 4, ["pass"] * 4))
    p1, p2 = game.players
    sculpt = ManaSculpt()
    bear = Creature(name="Bear", mana_cost=ManaCost.parse("{2}"),
                    base_power=2, base_toughness=2)
    bf = []
    if with_wizard:
        bf.append(Creature(name="Wiz", base_power=1, base_toughness=1,
                           subtypes={"Wizard"}))
    set_board_state(game, 0, hand=[sculpt], battlefield=bf,
                    mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
    set_board_state(game, 1, hand=[bear], mana={ManaType.COLORLESS: 2})

    # P2 is the active player casting at sorcery speed.
    game.active_player_index = 1
    game.priority_player_index = 1
    game._normal_next_index = 0  # next turn belongs to P1
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    engine_cast(game, p2, bear)

    target_so = game.stack.peek()
    p1._script.appendleft(target_so)
    engine_cast(game, p1, sculpt)
    priority_loop(game)
    return game, p1, p2, sculpt, bear


class TestManaSculpt:
    def test_counters_target_spell(self) -> None:
        game, p1, p2, sculpt, bear = _counter_setup(with_wizard=True)
        assert p2.zones[Zone.GRAVEYARD].contains(bear)
        assert not p2.zones[Zone.BATTLEFIELD].contains(bear)
        assert p1.zones[Zone.GRAVEYARD].contains(sculpt)
        assert game.stack.is_empty()

    def test_delayed_mana_with_wizard(self) -> None:
        """At the beginning of your next main phase you get {C} equal to the
        mana spent on the countered spell (2 for the Bear)."""
        game, p1, p2, sculpt, bear = _counter_setup(with_wizard=True)
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)  # leave P2's main
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # P1's next main phase
        assert game.active_player is p1
        priority_loop(game)  # resolve the delayed trigger
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2

    def test_no_wizard_no_mana(self) -> None:
        game, p1, p2, sculpt, bear = _counter_setup(with_wizard=False)
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        priority_loop(game)
        assert p1.mana_pool.total() == 0

    def test_delayed_mana_is_one_shot(self) -> None:
        game, p1, p2, sculpt, bear = _counter_setup(with_wizard=True)
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        priority_loop(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2
        # Trigger unregistered — nothing fires on later main phases.
        assert game.trigger_manager.get_triggers_for_source(sculpt) == []
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # next turn's main
        priority_loop(game)
        assert p1.mana_pool.total() == 0

    def test_cannot_cast_with_empty_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt()
        set_board_state(game, 0, hand=[sculpt],
                        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        with pytest.raises(CastingError):
            engine_cast(game, p1, sculpt)
