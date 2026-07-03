"""Tests for SOS 143 — Comforting Counsel."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_143.card_impl import ComfortingCounsel
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Enchantment
from benchmarks.sos.workspace.engine.events import GainsLifeTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestComfortingCounselProperties:
    """Static card data should match the SOS 143 spec."""

    def test_is_enchantment(self) -> None:
        assert isinstance(ComfortingCounsel(owner=None), Enchantment)

    def test_name_and_mana_cost(self) -> None:
        card = ComfortingCounsel(owner=None)

        assert card.name == "Comforting Counsel"
        assert card.mana_cost == ManaCost.parse("{1}{G}")


class TestComfortingCounselLifeGainTrigger:
    """Comforting Counsel should grow when its controller gains life."""

    def test_registers_a_gains_life_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ComfortingCounsel(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert any(trigger.event_type is GainsLifeTriggeredEvent for trigger in triggers)

    def test_gain_life_puts_a_growth_counter_on_the_enchantment(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ComfortingCounsel(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, GainsLifeTriggeredEvent(player=p1, amount=2))

        assert len(game.stack) == 1

        resolve_top(game)

        assert card.counters.get("growth", 0) == 1


class TestComfortingCounselContinuousEffect:
    """Comforting Counsel should buff only your creatures once it has five counters."""

    def test_with_fewer_than_five_growth_counters_it_does_not_buff_your_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ComfortingCounsel(owner=p1, controller=p1)
        ally = Creature(
            name="Helpful Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card, ally])
        add_counter(game, card, "growth", 4)

        card.apply_continuous_effect(game)
        game.effect_manager.apply_all(game)

        assert ally.power == 2
        assert ally.toughness == 2

    def test_with_five_growth_counters_it_gives_only_your_creatures_plus_three_plus_three(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ComfortingCounsel(owner=p1, controller=p1)
        ally = Creature(
            name="Helpful Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opponent_creature = Creature(
            name="Opposing Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card, ally])
        set_board_state(game, 1, battlefield=[opponent_creature])
        add_counter(game, card, "growth", 5)

        card.apply_continuous_effect(game)
        game.effect_manager.apply_all(game)

        assert ally.power == 5
        assert ally.toughness == 5
        assert opponent_creature.power == 2
        assert opponent_creature.toughness == 2
