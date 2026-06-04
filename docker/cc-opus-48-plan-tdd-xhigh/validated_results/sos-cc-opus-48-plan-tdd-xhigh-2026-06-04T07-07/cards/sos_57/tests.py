"""Tests for SOS 57 — Mana Sculpt (counter + delayed colorless mana)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.casting import cast_spell as _ecast
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import _resolve_top_of_stack, create_game, set_board_state


class _BigSpell(Instant):
    """Test instant {2}{R} with a no-op effect (something to counter)."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Big Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        pass


def _wizard() -> Creature:
    return Creature(name="Wizard Apprentice", subtypes={"Wizard"},
                    base_power=1, base_toughness=1)


def _cast_target(game, player, card):
    """Cast a spell, leaving it on the (real) stack unresolved."""
    _ecast(game, player, card)
    return game.stack.peek()


def _cast_response(game, player, card, target):
    """Cast an instant in response, scripting its single target choice."""
    player._script.appendleft(target)
    _ecast(game, player, card)


class TestManaSculptProperties:
    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_is_instant(self) -> None:
        assert CardType.INSTANT in ManaSculpt(owner=None).card_types


class TestManaSculptCounter:
    def test_counters_target_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ms = ManaSculpt(owner=None)
        big = _BigSpell(owner=None)
        set_board_state(game, 0, battlefield=[_wizard()], hand=[ms],
                        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        set_board_state(game, 1, hand=[big],
                        mana={ManaType.RED: 1, ManaType.COLORLESS: 2})
        game.active_player_index = 1
        game.priority_player_index = 1
        target_obj = _cast_target(game, p2, big)
        assert big.mana_spent == 3
        _cast_response(game, p1, ms, target_obj)
        _resolve_top_of_stack(game)
        # Big Spell is countered -> in p2's graveyard, off the stack.
        assert big in game.get_graveyard(p2).get_all()
        assert game.stack.is_empty()


class TestManaSculptDelayedMana:
    """The delayed colorless mana is a one-shot trigger gated on a Wizard.

    The engine fires ``BeginningOfMainPhaseTriggeredEvent`` in ``run_turn``;
    here we drive that event through the real trigger manager to exercise the
    registered trigger's condition, effect, and self-unregister.
    """

    def _counter_with_wizard(self, game, p1, p2, has_wizard: bool):
        ms = ManaSculpt(owner=None)
        big = _BigSpell(owner=None)
        bf = [_wizard()] if has_wizard else []
        set_board_state(game, 0, battlefield=bf, hand=[ms],
                        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        set_board_state(game, 1, hand=[big],
                        mana={ManaType.RED: 1, ManaType.COLORLESS: 2})
        game.active_player_index = 1
        game.priority_player_index = 1
        target_obj = _cast_target(game, p2, big)
        _cast_response(game, p1, ms, target_obj)
        _resolve_top_of_stack(game)

    def test_wizard_adds_colorless_on_controllers_main_phase(self) -> None:
        game = create_game()
        p1, p2 = game.players
        self._counter_with_wizard(game, p1, p2, has_wizard=True)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_precombat=True))
        _resolve_top_of_stack(game)
        # spent to cast Big Spell was 3 -> 3 colorless.
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_is_one_shot(self) -> None:
        game = create_game()
        p1, p2 = game.players
        self._counter_with_wizard(game, p1, p2, has_wizard=True)
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_precombat=True))
        _resolve_top_of_stack(game)
        p1.mana_pool.empty()
        # Second main phase: trigger already unregistered, no mana added.
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_precombat=False))
        _resolve_top_of_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_only_fires_on_controllers_main_phase(self) -> None:
        game = create_game()
        p1, p2 = game.players
        self._counter_with_wizard(game, p1, p2, has_wizard=True)
        # Opponent's main phase must not trigger the mana.
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p2, is_precombat=True))
        _resolve_top_of_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_no_wizard_no_delayed_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        self._counter_with_wizard(game, p1, p2, has_wizard=False)
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_precombat=True))
        _resolve_top_of_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
