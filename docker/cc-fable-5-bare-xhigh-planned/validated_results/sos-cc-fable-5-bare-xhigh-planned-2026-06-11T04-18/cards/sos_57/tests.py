"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.casting import cast_spell as engine_cast_spell
from engine.card import Creature
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Step
from test_utils import advance_to_phase, create_game, set_board_state


def _wizard() -> Creature:
    return Creature(name="Wizard", subtypes={"Wizard"}, base_power=1, base_toughness=1)


def _advance_to_next_precombat_main(game):
    """Roll the turn over and stop at the (new) active player's precombat main."""
    advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)


def _counter_a_bear(game, *, p1_extra_battlefield=None):
    """p2 (active) casts a {2} bear; p1 counters it with Mana Sculpt."""
    p1, p2 = game.players
    bear = Creature(name="Bear", mana_cost=ManaCost.parse("{2}"), base_power=2, base_toughness=2)
    set_board_state(game, 1, hand=[bear], mana={ManaType.COLORLESS: 2})
    battlefield = list(p1_extra_battlefield or [])
    set_board_state(game, 0, battlefield=battlefield, hand=[ManaSculpt()],
                    mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
    game.active_player_index = 1
    game.priority_player_index = 1
    game._normal_next_index = 0  # p1 takes the next turn
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    engine_cast_spell(game, p2, next(c for c in game.get_hand(p2).get_all() if c.name == "Bear"))
    bear_so = game.stack.peek()
    sculpt = next(c for c in game.get_hand(p1).get_all() if c.name == "Mana Sculpt")
    p1._script.extend([bear_so])
    engine_cast_spell(game, p1, sculpt)
    # Resolve the stack: Mana Sculpt counters the bear.
    p1._script.extend(["pass"])
    p2._script.extend(["pass"])
    priority_loop(game)
    return bear


class TestCounter:
    def test_counters_target_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bear = _counter_a_bear(game, p1_extra_battlefield=[_wizard()])
        assert game.stack.is_empty()
        assert game.get_graveyard(p2).contains(bear)
        assert not game.get_battlefield(p2).contains(bear)

    def test_cannot_cast_with_empty_stack(self) -> None:
        game = create_game()
        set_board_state(game, 0, hand=[ManaSculpt()],
                        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        try:
            from test_utils import cast_spell

            cast_spell(game, 0, "Mana Sculpt")
            raised = False
        except Exception:
            raised = True
        assert raised


class TestDelayedMana:
    def test_wizard_grants_delayed_colorless(self) -> None:
        """Countering a 2-mana spell with a Wizard out: +2 {C} at your next main."""
        game = create_game()
        p1, p2 = game.players
        _counter_a_bear(game, p1_extra_battlefield=[_wizard()])
        # Advance from p2's main phase to p1's next precombat main.
        _advance_to_next_precombat_main(game)
        assert game.active_player is p1
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2

    def test_no_wizard_no_delayed_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _counter_a_bear(game)  # no Wizard on p1's battlefield
        _advance_to_next_precombat_main(game)
        assert game.active_player is p1
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_one_shot_does_not_refire(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _counter_a_bear(game, p1_extra_battlefield=[_wizard()])
        _advance_to_next_precombat_main(game)
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2
        # A later main phase of p1's must not add mana again.
        _advance_to_next_precombat_main(game)  # p2's turn
        _advance_to_next_precombat_main(game)  # p1's turn again
        assert game.active_player is p1
        priority_loop(game)  # nothing on stack -> auto-pass
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_amount_is_mana_actually_spent_not_mana_value(self) -> None:
        """A cost-reduced spell records the reduced amount."""
        from cards.sos.sos_1.card_impl import TheDawningArchaic
        from engine.card import Instant

        game = create_game()
        p1, p2 = game.players
        # p2 casts The Dawning Archaic ({10}) with 4 instants in graveyard -> pays 6.
        graveyard = [Instant(name=f"I{i}", mana_cost=ManaCost.parse("{1}")) for i in range(4)]
        set_board_state(game, 1, hand=[TheDawningArchaic()], graveyard=graveyard,
                        mana={ManaType.COLORLESS: 6})
        set_board_state(game, 0, battlefield=[_wizard()], hand=[ManaSculpt()],
                        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        game.active_player_index = 1
        game.priority_player_index = 1
        game._normal_next_index = 0  # p1 takes the next turn
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        engine_cast_spell(game, p2, next(c for c in game.get_hand(p2).get_all()))
        so = game.stack.peek()
        p1._script.extend([so])
        engine_cast_spell(game, p1, next(c for c in game.get_hand(p1).get_all()))
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)
        _advance_to_next_precombat_main(game)
        assert game.active_player is p1
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 6
