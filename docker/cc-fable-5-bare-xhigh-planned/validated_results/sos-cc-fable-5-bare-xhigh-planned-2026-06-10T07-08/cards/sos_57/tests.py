"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature
from engine.casting import cast_spell as engine_cast_spell
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import TestSetupError, create_game, set_board_state


def _counter_setup(*, wizard: bool):
    """p2 casts a {2} Wolf; p1 counters it with Mana Sculpt.

    Returns the game with the stack fully resolved and the delayed
    trigger (if any) registered.
    """
    game = create_game(scripts=(["pass"], ["pass"]))
    p1, p2 = game.players

    wolf = Creature(name="Wolf", base_power=2, base_toughness=2,
                    mana_cost=ManaCost.parse("{2}"))
    sculpt = ManaSculpt()
    p1_bf = [Creature(name="Sage", base_power=1, base_toughness=1,
                      subtypes={"Wizard"})] if wizard else []
    set_board_state(
        game, 0, battlefield=p1_bf, hand=[sculpt],
        mana={ManaType.COLORLESS: 1, ManaType.BLUE: 2},
    )
    set_board_state(game, 1, hand=[wolf], mana={ManaType.COLORLESS: 2})

    # p2 (active) casts the Wolf; it stays on the stack.
    game.active_player_index = 1
    game.priority_player_index = 1
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    engine_cast_spell(game, p2, wolf)

    # p1 responds with Mana Sculpt targeting the Wolf spell.
    wolf_so = game.stack.peek()
    p1._script.appendleft(wolf_so)
    engine_cast_spell(game, p1, sculpt)

    priority_loop(game)
    return game, wolf, sculpt


def _advance_to_p1_main(game) -> None:
    """Advance phases until p1's precombat main begins (E2 fires there)."""
    for _ in range(30):
        game.advance_phase()
        if (game.phase is Phase.PRECOMBAT_MAIN
                and game.active_player is game.players[0]):
            return
    raise AssertionError("never reached p1's precombat main")


class TestProperties:
    def test_static_data(self) -> None:
        card = ManaSculpt()
        assert card.name == "Mana Sculpt"
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")


class TestCounter:
    def test_counters_target_spell(self) -> None:
        game, wolf, sculpt = _counter_setup(wizard=False)
        p1, p2 = game.players

        assert game.stack.is_empty()
        assert p2.zones[Zone.GRAVEYARD].contains(wolf)
        assert not p2.zones[Zone.BATTLEFIELD].contains(wolf)
        assert p1.zones[Zone.GRAVEYARD].contains(sculpt)

    def test_cannot_cast_with_empty_stack(self) -> None:
        game = create_game()
        sculpt = ManaSculpt()
        set_board_state(
            game, 0, hand=[sculpt],
            mana={ManaType.COLORLESS: 1, ManaType.BLUE: 2},
        )
        from test_utils import cast_spell

        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Mana Sculpt")


class TestDelayedMana:
    def test_wizard_grants_mana_at_next_main(self) -> None:
        """With a Wizard, p1 gets {C}{C} at their next precombat main."""
        game, _, _ = _counter_setup(wizard=True)
        p1 = game.players[0]

        _advance_to_p1_main(game)
        assert len(game.stack) == 1  # the delayed trigger
        p1._script.extend(["pass", "pass"])
        game.players[1]._script.extend(["pass", "pass"])
        priority_loop(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 2

    def test_no_wizard_no_mana(self) -> None:
        game, _, _ = _counter_setup(wizard=False)
        p1 = game.players[0]

        _advance_to_p1_main(game)
        p1._script.extend(["pass", "pass"])
        game.players[1]._script.extend(["pass", "pass"])
        priority_loop(game)

        assert p1.mana_pool.total() == 0

    def test_one_shot_does_not_repeat(self) -> None:
        """The delayed mana fires once; the following main phase adds nothing."""
        game, _, _ = _counter_setup(wizard=True)
        p1 = game.players[0]

        _advance_to_p1_main(game)
        p1._script.extend(["pass", "pass"])
        game.players[1]._script.extend(["pass", "pass"])
        priority_loop(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2

        # Next time p1's main comes around: nothing fires.
        _advance_to_p1_main(game)
        assert game.stack.is_empty()
        assert p1.mana_pool.total() == 0
