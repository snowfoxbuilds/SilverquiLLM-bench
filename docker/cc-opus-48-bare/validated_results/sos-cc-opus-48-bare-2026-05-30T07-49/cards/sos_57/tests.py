"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature
from engine.casting import cast_spell as engine_cast
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


def _set_priority_window(game, active_index: int) -> None:
    """Put the game in a main phase with *active_index* as active player."""
    game.active_player_index = active_index
    game.priority_player_index = active_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


class TestManaSculptProperties:
    def test_name(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_cannot_cast_with_empty_stack(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=game.players[0], controller=game.players[0])
        assert card.can_cast(game) is False


class TestManaSculptCounter:
    def test_counters_target_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        sculpt = ManaSculpt(owner=p1, controller=p1)
        bear = Creature(
            name="Bear",
            mana_cost=ManaCost.parse("{1}{G}"),
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, hand=[sculpt], mana={ManaType.BLUE: 3})
        set_board_state(
            game, 1, hand=[bear], mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1}
        )

        _set_priority_window(game, 1)
        engine_cast(game, p2, bear)
        assert len(game.stack) == 1

        bear_obj = game.stack.peek()
        p1._script.appendleft(bear_obj)
        engine_cast(game, p1, sculpt)

        # Resolve Mana Sculpt (top of stack).
        game.stack.pop().on_resolve(game)

        assert len(game.stack) == 0
        assert bear in game.get_graveyard(p2).get_all()
        assert not game.get_battlefield(p2).get_all()


class TestManaSculptWizardMana:
    def test_wizard_grants_colorless_next_main_phase(self) -> None:
        game = create_game()
        p1, p2 = game.players
        sculpt = ManaSculpt(owner=p1, controller=p1)
        wizard = Creature(
            name="Apprentice", subtypes={"Wizard"}, base_power=1, base_toughness=1
        )
        big = Creature(
            name="Big",
            mana_cost=ManaCost.parse("{2}{G}{G}"),
            base_power=4,
            base_toughness=4,
        )
        set_board_state(
            game, 0, battlefield=[wizard], hand=[sculpt], mana={ManaType.BLUE: 3}
        )
        set_board_state(
            game, 1, hand=[big], mana={ManaType.GREEN: 2, ManaType.COLORLESS: 2}
        )

        _set_priority_window(game, 1)
        engine_cast(game, p2, big)
        assert big.mana_spent == 4

        big_obj = game.stack.peek()
        p1._script.appendleft(big_obj)
        engine_cast(game, p1, sculpt)
        game.stack.pop().on_resolve(game)

        # Spell is countered; no mana added yet.
        assert big in game.get_graveyard(p2).get_all()
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

        # At the beginning of p1's next main phase, {C}{C}{C}{C} is added.
        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(phase=Phase.PRECOMBAT_MAIN, player=p1),
        )
        assert len(game.stack) == 1
        game.stack.pop().on_resolve(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 4

    def test_no_wizard_no_delayed_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        sculpt = ManaSculpt(owner=p1, controller=p1)
        big = Creature(
            name="Big",
            mana_cost=ManaCost.parse("{2}{G}{G}"),
            base_power=4,
            base_toughness=4,
        )
        set_board_state(game, 0, hand=[sculpt], mana={ManaType.BLUE: 3})
        set_board_state(
            game, 1, hand=[big], mana={ManaType.GREEN: 2, ManaType.COLORLESS: 2}
        )

        _set_priority_window(game, 1)
        engine_cast(game, p2, big)
        big_obj = game.stack.peek()
        p1._script.appendleft(big_obj)
        engine_cast(game, p1, sculpt)
        game.stack.pop().on_resolve(game)

        # No Wizard → no delayed trigger registered.
        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(phase=Phase.PRECOMBAT_MAIN, player=p1),
        )
        assert len(game.stack) == 0
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
