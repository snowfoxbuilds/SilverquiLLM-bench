"""Tests for SOS 181 — Colossus of the Blood Age."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_181.card_impl import ColossusOfTheBloodAge
from benchmarks.sos.workspace.engine.card import CardImpl, Creature
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.events import CreatureDiesTriggeredEvent, EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.game import destroy
from benchmarks.sos.workspace.engine.types import CardType, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestColossusOfTheBloodAgeProperties:
    """Static card data should match the SOS 181 spec."""

    def test_is_artifact_construct_creature(self) -> None:
        card = ColossusOfTheBloodAge(owner=None)

        assert isinstance(card, Creature)
        assert CardType.ARTIFACT in card.card_types
        assert "Construct" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = ColossusOfTheBloodAge(owner=None)

        assert card.name == "Colossus of the Blood Age"
        assert card.mana_cost == ManaCost.parse("{4}{R}{W}")
        assert card.base_power == 6
        assert card.base_toughness == 6


class TestColossusOfTheBloodAgeEntersTrigger:
    """Colossus of the Blood Age should blast opponents and gain life on entry."""

    def test_registers_enters_battlefield_and_dies_triggers(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ColossusOfTheBloodAge(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 2
        assert any(trigger.event_type is EntersBattlefieldTriggeredEvent for trigger in triggers)
        assert any(trigger.event_type is CreatureDiesTriggeredEvent for trigger in triggers)

    def test_when_it_enters_it_deals_three_to_each_opponent_and_you_gain_three_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ColossusOfTheBloodAge(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        assert len(game.stack) == 1
        resolve_top(game)

        assert p1.life == 23
        assert p2.life == 17

    def test_another_creature_entering_does_not_trigger_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ColossusOfTheBloodAge(owner=p1, controller=p1)
        other = Creature(
            name="Other Construct",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card, other])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=other, creature=other, controller=p1),
        )

        assert game.stack.is_empty()


class TestColossusOfTheBloodAgeDiesTrigger:
    """Colossus of the Blood Age should rummage when it dies."""

    def test_when_it_dies_with_no_cards_in_hand_you_still_draw_one_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ColossusOfTheBloodAge(owner=p1, controller=p1)
        drawn = CardImpl(name="Fresh Notes", owner=p1, controller=p1)
        game.get_library(p1).add(drawn)
        set_board_state(game, 0, battlefield=[card], hand=[])
        card.register_triggers(game)

        destroy(game, card)

        assert len(game.stack) == 1
        resolve_top(game)

        assert game.get_graveyard(p1).contains(card)
        assert game.get_hand(p1).contains(drawn)
        assert not game.get_library(p1).contains(drawn)

    def test_when_it_dies_you_may_discard_selected_cards_then_draw_that_many_plus_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ColossusOfTheBloodAge(owner=p1, controller=p1)
        discard_one = CardImpl(name="Spent Thesis", owner=p1, controller=p1)
        discard_two = CardImpl(name="Draft Rebuttal", owner=p1, controller=p1)
        keep = CardImpl(name="Keep for Later", owner=p1, controller=p1)
        draw_one = CardImpl(name="First Draw", owner=p1, controller=p1)
        draw_two = CardImpl(name="Second Draw", owner=p1, controller=p1)
        draw_three = CardImpl(name="Third Draw", owner=p1, controller=p1)
        game.get_library(p1).add(draw_one)
        game.get_library(p1).add(draw_two)
        game.get_library(p1).add(draw_three)
        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[discard_one, discard_two, keep],
        )
        p1._script.extend([True, discard_one, True, discard_two, False])
        card.register_triggers(game)

        destroy(game, card)

        assert len(game.stack) == 1
        resolve_top(game)

        assert game.get_graveyard(p1).contains(card)
        assert game.get_graveyard(p1).contains(discard_one)
        assert game.get_graveyard(p1).contains(discard_two)
        assert not game.get_hand(p1).contains(discard_one)
        assert not game.get_hand(p1).contains(discard_two)
        assert game.get_hand(p1).contains(keep)
        assert game.get_hand(p1).contains(draw_one)
        assert game.get_hand(p1).contains(draw_two)
        assert game.get_hand(p1).contains(draw_three)
