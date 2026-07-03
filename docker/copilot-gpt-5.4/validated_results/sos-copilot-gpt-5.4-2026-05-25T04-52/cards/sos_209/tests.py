"""Tests for SOS 209 — Pest Mascot."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_209.card_impl import PestMascot
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import GainsLifeTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestPestMascotProperties:
    """Static card data should match the SOS 209 spec."""

    def test_is_pest_ape_creature_with_trample(self) -> None:
        card = PestMascot(owner=None)

        assert isinstance(card, Creature)
        assert "Pest" in card.subtypes
        assert "Ape" in card.subtypes
        assert Keyword.TRAMPLE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = PestMascot(owner=None)

        assert card.name == "Pest Mascot"
        assert card.mana_cost == ManaCost.parse("{1}{B}{G}")
        assert card.base_power == 2
        assert card.base_toughness == 3


class TestPestMascotLifeGainTrigger:
    """Pest Mascot should grow itself whenever you gain life."""

    def test_registers_a_gains_life_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PestMascot(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is GainsLifeTriggeredEvent

    def test_your_life_gain_puts_exactly_one_plus_one_plus_one_counter_on_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PestMascot(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=3))

        assert len(game.stack) == 1

        resolve_top(game)

        assert card.plus_one_counters == 1
        assert card.power == 3
        assert card.toughness == 4

    def test_opponents_life_gain_does_not_trigger_it(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = PestMascot(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p2, amount=1))

        assert game.stack.is_empty()
        assert card.plus_one_counters == 0
