"""Tests for SOS 189 — Fractal Mascot."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_189.card_impl import FractalMascot
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


def _stun_count(permanent: Creature) -> int:
    return max(permanent.counters.get("stun", 0), getattr(permanent, "stun_counters", 0))


class TestFractalMascotProperties:
    """Static card data should match the SOS 189 spec."""

    def test_is_fractal_elk_creature_with_trample(self) -> None:
        card = FractalMascot(owner=None)

        assert isinstance(card, Creature)
        assert "Fractal" in card.subtypes
        assert "Elk" in card.subtypes
        assert Keyword.TRAMPLE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = FractalMascot(owner=None)

        assert card.name == "Fractal Mascot"
        assert card.mana_cost == ManaCost.parse("{4}{G}{U}")
        assert card.base_power == 6
        assert card.base_toughness == 6


class TestFractalMascotTrigger:
    """Fractal Mascot should lock a target and tap it with a stun counter."""

    def test_registers_an_enters_battlefield_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = FractalMascot(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent

    def test_enters_trigger_targets_an_opponents_creature_then_taps_it_and_adds_a_stun_counter(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = FractalMascot(owner=p1, controller=p1)
        target = Creature(
            name="Opposing Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[target])
        card.register_triggers(game)
        p1._script.append(target)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        assert len(game.stack) == 1
        assert game.stack.peek().targets == [target]

        resolve_top(game)

        assert target.is_tapped is True
        assert _stun_count(target) == 1
