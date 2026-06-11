"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.casting import cast_spell as engine_cast_spell
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase
from test_utils import TestSetupError, cast_spell, create_game, set_board_state


def _counter_setup(*, with_wizard: bool):
    """p2 casts a 2-mana Bear; p1 counters it with Mana Sculpt."""
    game = create_game(scripts=([], []))
    p1, p2 = game.players

    sculpt = ManaSculpt()
    p1_board = []
    if with_wizard:
        p1_board.append(
            Creature(name="Wiz", subtypes={"Wizard"}, base_power=1, base_toughness=1)
        )
    set_board_state(game, 0, battlefield=p1_board, hand=[sculpt],
                    mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})

    bear = Creature(name="Bear", mana_cost=ManaCost.parse("{1}{G}"),
                    base_power=2, base_toughness=2)
    set_board_state(game, 1, hand=[bear],
                    mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1})

    # p2 casts Bear at sorcery speed; it stays on the stack.
    game.active_player_index = 1
    game.priority_player_index = 1
    game._normal_next_index = 0  # keep normal rotation consistent
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    engine_cast_spell(game, p2, bear)
    bear_so = game.stack.peek()

    # p1 responds with Mana Sculpt targeting the Bear spell.
    p1._script.append(bear_so)
    engine_cast_spell(game, p1, sculpt)

    # Both players pass; Mana Sculpt resolves and counters the Bear.
    p2._script.append("pass")
    p1._script.append("pass")
    priority_loop(game)
    return game, p1, p2, sculpt, bear


class TestProperties:
    def test_static_data(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.name == "Mana Sculpt"
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")
        assert isinstance(card, Instant)


class TestCounter:
    def test_counters_target_spell(self) -> None:
        game, p1, p2, sculpt, bear = _counter_setup(with_wizard=True)
        assert game.get_graveyard(p2).contains(bear)
        assert not game.get_battlefield(p2).contains(bear)
        assert game.get_graveyard(p1).contains(sculpt)
        assert game.stack.is_empty()

    def test_cannot_cast_with_empty_stack(self) -> None:
        game = create_game()
        set_board_state(game, 0, hand=[ManaSculpt()],
                        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        try:
            cast_spell(game, 0, "Mana Sculpt")
            raise AssertionError("cast should have failed with empty stack")
        except TestSetupError as exc:
            assert "can_cast" in str(exc)


class TestDelayedMana:
    def _advance_to_p1_main(self, game) -> None:
        from test_utils import advance_to_phase

        # We're in p2's precombat main; go forward to p1's precombat main.
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

    def test_wizard_grants_colorless_at_next_main(self) -> None:
        game, p1, p2, sculpt, bear = _counter_setup(with_wizard=True)
        self._advance_to_p1_main(game)
        assert game.active_player is p1
        assert len(game.stack) == 1          # delayed trigger waiting

        p1._script.append("pass")
        p2._script.append("pass")
        priority_loop(game)

        # Bear cost {1}{G} → 2 mana spent → add {C}{C}.
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2
        # One-shot: nothing left registered for the sculpt.
        assert game.trigger_manager.get_triggers_for_source(sculpt) == []

    def test_no_wizard_no_mana(self) -> None:
        game, p1, p2, sculpt, bear = _counter_setup(with_wizard=False)
        self._advance_to_p1_main(game)
        assert len(game.stack) == 1

        p1._script.append("pass")
        p2._script.append("pass")
        priority_loop(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
        # Spent even though no Wizard was controlled.
        assert game.trigger_manager.get_triggers_for_source(sculpt) == []
