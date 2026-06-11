"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature
from engine.casting import cast_spell as engine_cast_spell
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase
from test_utils import create_game, advance_to_phase, set_board_state


def _advance_to_next_precombat_main(game) -> None:
    """Advance to the NEXT precombat main (advance_to_phase is a no-op when
    the game is already in a precombat main)."""
    game.advance_phase()
    if (game.phase, game.step) != (Phase.PRECOMBAT_MAIN, None):
        _advance_to_next_precombat_main(game)


def _setup_counter_scenario(game, *, wizard: bool):
    """p2 (active) casts a {2} bear left on the stack; p1 responds with
    Mana Sculpt through the real cast pipeline."""
    p1, p2 = game.players

    battlefield = []
    if wizard:
        battlefield.append(
            Creature(name="Sage", base_power=1, base_toughness=2, subtypes={"Wizard"})
        )
    set_board_state(game, 0, battlefield=battlefield,
                    mana={ManaType.COLORLESS: 1, ManaType.BLUE: 2})

    game.active_player_index = 1
    game.priority_player_index = 1
    game._normal_next_index = 0  # p1 takes the next turn
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None

    bear = Creature(name="Stack Bear", base_power=2, base_toughness=2,
                    mana_cost=ManaCost.parse("{2}"))
    game.get_hand(p2).add(bear)
    bear.owner = bear.controller = p2
    p2.mana_pool.add(ManaType.COLORLESS, 2)
    engine_cast_spell(game, p2, bear)  # stays on the stack

    sculpt = ManaSculpt(owner=p1)
    game.get_hand(p1).add(sculpt)
    sculpt.owner = sculpt.controller = p1
    target_so = game.stack.peek()
    p1._script.extend([target_so])  # target choice for Mana Sculpt
    engine_cast_spell(game, p1, sculpt)

    # Resolve the stack: Mana Sculpt counters; nothing else resolves.
    p1._script.extend(["pass", "pass"])
    p2._script.extend(["pass", "pass"])
    priority_loop(game)
    return p1, p2, bear, sculpt


class TestManaSculptProperties:
    def test_static_data(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.name == "Mana Sculpt"
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_cannot_cast_with_empty_stack(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=game.players[0])
        assert card.can_cast(game) is False


class TestManaSculptCounter:
    def test_counters_target_spell(self) -> None:
        game = create_game()
        p1, p2, bear, sculpt = _setup_counter_scenario(game, wizard=True)
        assert game.stack.is_empty()
        assert game.get_graveyard(p2).contains(bear)
        assert not game.get_battlefield(p2).contains(bear)
        assert game.get_graveyard(p1).contains(sculpt)

    def test_delayed_mana_with_wizard(self) -> None:
        game = create_game()
        p1, p2, bear, sculpt = _setup_counter_scenario(game, wizard=True)
        # Advance to p1's next precombat main: trigger fires and resolves.
        _advance_to_next_precombat_main(game)  # p2 turn ends, p1 main
        assert game.active_player is p1
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)
        # The bear was cast for {2} → add {C}{C}.
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2

    def test_no_wizard_no_mana(self) -> None:
        game = create_game()
        p1, p2, bear, sculpt = _setup_counter_scenario(game, wizard=False)
        _advance_to_next_precombat_main(game)
        assert game.active_player is p1
        if not game.stack.is_empty():
            p1._script.extend(["pass"])
            p2._script.extend(["pass"])
            priority_loop(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_delayed_mana_is_one_shot(self) -> None:
        game = create_game()
        p1, p2, bear, sculpt = _setup_counter_scenario(game, wizard=True)
        _advance_to_next_precombat_main(game)
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2
        # Advance through p2's next main to p1's following main — the
        # trigger must not fire again.
        _advance_to_next_precombat_main(game)  # p2 main
        assert game.active_player is p2
        assert game.stack.is_empty()
        _advance_to_next_precombat_main(game)  # p1 main again
        assert game.active_player is p1
        assert game.stack.is_empty()
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
