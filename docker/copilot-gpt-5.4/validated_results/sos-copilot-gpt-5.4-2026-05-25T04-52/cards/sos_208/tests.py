"""Tests for SOS 208 — Paradox Surveyor."""

from __future__ import annotations

from typing import Any

from benchmarks.sos.workspace.cards.sos.sos_208.card_impl import ParadoxSurveyor
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Land, Sorcery
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class VariableLecture(Sorcery):
    """Simple X-cost spell used to validate the printed selection rule."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Variable Lecture")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{U}"))
        super().__init__(**kwargs)


class TestParadoxSurveyorProperties:
    """Static card data should match the SOS 208 spec."""

    def test_is_elf_druid_creature_with_reach(self) -> None:
        card = ParadoxSurveyor(owner=None)

        assert isinstance(card, Creature)
        assert "Elf" in card.subtypes
        assert "Druid" in card.subtypes
        assert Keyword.REACH in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = ParadoxSurveyor(owner=None)

        assert card.name == "Paradox Surveyor"
        assert card.mana_cost == ManaCost.parse("{G}{G/U}{U}")
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestParadoxSurveyorEntersTrigger:
    """Paradox Surveyor should turn its ETB look into one chosen card."""

    def test_registers_an_enters_battlefield_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ParadoxSurveyor(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent

    def test_self_entry_can_put_a_revealed_land_into_your_hand_and_put_the_rest_on_the_bottom_in_random_order(self) -> None:
        game = create_game()
        p1 = game.players[0]
        deeper = CardImpl(name="Deeper Lesson", owner=p1, controller=p1)
        land_card = Land(name="Chosen Campus", owner=p1, controller=p1)
        filler_a = CardImpl(name="Top Spell A", owner=p1, controller=p1)
        filler_b = CardImpl(name="Top Spell B", owner=p1, controller=p1)
        filler_c = CardImpl(name="Top Spell C", owner=p1, controller=p1)
        filler_d = CardImpl(name="Top Spell D", owner=p1, controller=p1)
        card = ParadoxSurveyor(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        game.get_library(p1).add(deeper)
        game.get_library(p1).add(land_card)
        game.get_library(p1).add(filler_a)
        game.get_library(p1).add(filler_b)
        game.get_library(p1).add(filler_c)
        game.get_library(p1).add(filler_d)
        game.queue_bottom_order(filler_c, filler_a, filler_d, filler_b)
        p1._script.append(land_card)
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        assert len(game.stack) == 1

        resolve_top(game)

        assert game.get_hand(p1).contains(land_card)
        assert not game.get_library(p1).contains(land_card)
        assert len(game.look_history) == 1
        assert game.look_history[-1].cards == [land_card, filler_a, filler_b, filler_c, filler_d]
        assert game.look_history[-1].source is card
        assert game.look_history[-1].reason == "Paradox Surveyor"
        assert len(game.reveal_history) == 1
        assert game.reveal_history[-1].cards == [land_card]
        assert game.reveal_history[-1].source is card
        assert game.reveal_history[-1].reason == "Paradox Surveyor"
        assert len(game.bottom_order_history) == 1
        assert game.bottom_order_history[-1].cards == [filler_a, filler_b, filler_c, filler_d]
        assert game.bottom_order_history[-1].ordered_cards == [filler_c, filler_a, filler_d, filler_b]
        assert game.bottom_order_history[-1].source is card
        assert game.bottom_order_history[-1].reason == "Paradox Surveyor"
        assert game.bottom_order_history[-1].used_queued_order is True
        assert game.get_library(p1).get_all() == [filler_c, filler_a, filler_d, filler_b, deeper]

    def test_self_entry_can_put_a_revealed_x_cost_card_into_your_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        deeper = CardImpl(name="Deeper Lesson", owner=p1, controller=p1)
        x_spell = VariableLecture(owner=p1, controller=p1)
        land_card = Land(name="Unused Campus", owner=p1, controller=p1)
        filler_a = CardImpl(name="Top Spell A", owner=p1, controller=p1)
        filler_b = CardImpl(name="Top Spell B", owner=p1, controller=p1)
        filler_c = CardImpl(name="Top Spell C", owner=p1, controller=p1)
        card = ParadoxSurveyor(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        game.get_library(p1).add(deeper)
        game.get_library(p1).add(x_spell)
        game.get_library(p1).add(land_card)
        game.get_library(p1).add(filler_a)
        game.get_library(p1).add(filler_b)
        game.get_library(p1).add(filler_c)
        game.queue_bottom_order(land_card, filler_c, filler_a, filler_b)
        p1._script.append(x_spell)
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        resolve_top(game)

        assert game.get_hand(p1).contains(x_spell)
        assert not game.get_library(p1).contains(x_spell)
        assert game.get_library(p1).contains(land_card)
        assert len(game.reveal_history) == 1
        assert game.reveal_history[-1].cards == [x_spell]
        assert game.bottom_order_history[-1].ordered_cards == [land_card, filler_c, filler_a, filler_b]

    def test_self_entry_may_decline_to_take_an_eligible_card_and_puts_all_five_on_the_bottom(self) -> None:
        game = create_game()
        p1 = game.players[0]
        deeper = CardImpl(name="Deeper Lesson", owner=p1, controller=p1)
        land_card = Land(name="Chosen Campus", owner=p1, controller=p1)
        x_spell = VariableLecture(owner=p1, controller=p1)
        filler_a = CardImpl(name="Top Spell A", owner=p1, controller=p1)
        filler_b = CardImpl(name="Top Spell B", owner=p1, controller=p1)
        filler_c = CardImpl(name="Top Spell C", owner=p1, controller=p1)
        card = ParadoxSurveyor(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        game.get_library(p1).add(deeper)
        game.get_library(p1).add(land_card)
        game.get_library(p1).add(x_spell)
        game.get_library(p1).add(filler_a)
        game.get_library(p1).add(filler_b)
        game.get_library(p1).add(filler_c)
        game.queue_bottom_order(filler_b, land_card, x_spell, filler_c, filler_a)
        p1._script.append(None)
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        resolve_top(game)

        assert game.get_hand(p1).get_all() == []
        assert len(game.look_history) == 1
        assert game.look_history[-1].cards == [land_card, x_spell, filler_a, filler_b, filler_c]
        assert len(game.reveal_history) == 0
        assert len(game.bottom_order_history) == 1
        assert game.bottom_order_history[-1].ordered_cards == [
            filler_b,
            land_card,
            x_spell,
            filler_c,
            filler_a,
        ]
        assert game.get_library(p1).get_all() == [
            filler_b,
            land_card,
            x_spell,
            filler_c,
            filler_a,
            deeper,
        ]
