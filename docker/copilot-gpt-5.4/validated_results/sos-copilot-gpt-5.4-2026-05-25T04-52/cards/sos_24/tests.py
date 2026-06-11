"""Tests for SOS 24 — Owlin Historian."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_24.card_impl import OwlinHistorian
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestOwlinHistorianProperties:
    """Static card data should match the SOS 24 spec."""

    def test_is_bird_cleric_creature_with_flying(self) -> None:
        card = OwlinHistorian(owner=None)
        assert isinstance(card, Creature)
        assert "Bird" in card.subtypes
        assert "Cleric" in card.subtypes
        assert Keyword.FLYING in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = OwlinHistorian(owner=None)
        assert card.name == "Owlin Historian"
        assert card.mana_cost == ManaCost.parse("{2}{W}")
        assert card.base_power == 2
        assert card.base_toughness == 3


class TestOwlinHistorianSurveil:
    """Owlin Historian should surveil 1 when it resolves."""

    def test_controller_may_put_the_top_card_of_their_library_into_their_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bottom_card = CardImpl(name="Earlier Lesson", owner=p1, controller=p1)
        top_card = CardImpl(name="Latest Lesson", owner=p1, controller=p1)
        game.get_library(p1).add(bottom_card)
        game.get_library(p1).add(top_card)
        p1._script.append(True)
        card = OwlinHistorian(owner=p1, controller=p1)

        card.on_resolve(game)

        assert game.get_graveyard(p1).contains(top_card)
        assert game.get_library(p1).contains(top_card) is False
        assert game.get_library(p1).top(1) == [bottom_card]

    def test_controller_may_leave_the_top_card_of_their_library_in_place(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bottom_card = CardImpl(name="Earlier Lesson", owner=p1, controller=p1)
        top_card = CardImpl(name="Latest Lesson", owner=p1, controller=p1)
        game.get_library(p1).add(bottom_card)
        game.get_library(p1).add(top_card)
        p1._script.append(False)
        card = OwlinHistorian(owner=p1, controller=p1)

        card.on_resolve(game)

        assert game.get_graveyard(p1).get_all() == []
        assert game.get_library(p1).get_all() == [bottom_card, top_card]

    def test_empty_library_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]

        OwlinHistorian(owner=p1, controller=p1).on_resolve(game)

        assert game.get_library(p1).get_all() == []
        assert game.get_graveyard(p1).get_all() == []


class TestOwlinHistorianGraveyardLeaves:
    """Owlin Historian should reward cards leaving its controller's graveyard."""

    def test_card_leaving_your_graveyard_puts_a_trigger_on_the_stack_and_grants_plus_one_plus_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        historian = OwlinHistorian(owner=p1, controller=p1)
        lesson = CardImpl(name="Recovered Lesson", owner=p1, controller=p1)
        game.get_battlefield(p1).add(historian)
        game.get_graveyard(p1).add(lesson)
        historian.register_triggers(game)

        move_to_zone(game, lesson, Zone.GRAVEYARD, Zone.HAND)

        assert len(game.stack) == 1
        assert game.stack.peek().source is historian

        resolve_top(game)

        assert historian.power == 3
        assert historian.toughness == 4

    def test_graveyard_leaves_bonus_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        historian = OwlinHistorian(owner=p1, controller=p1)
        lesson = CardImpl(name="Recovered Lesson", owner=p1, controller=p1)
        game.get_battlefield(p1).add(historian)
        game.get_graveyard(p1).add(lesson)
        historian.register_triggers(game)

        move_to_zone(game, lesson, Zone.GRAVEYARD, Zone.HAND)
        resolve_top(game)

        assert historian.power == 3
        assert historian.toughness == 4

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert historian.power == 2
        assert historian.toughness == 3

    def test_cards_leaving_an_opponents_graveyard_do_not_trigger_it(self) -> None:
        game = create_game()
        p1, p2 = game.players
        historian = OwlinHistorian(owner=p1, controller=p1)
        opponent_card = CardImpl(name="Opponent Lesson", owner=p2, controller=p2)
        game.get_battlefield(p1).add(historian)
        game.get_graveyard(p2).add(opponent_card)
        historian.register_triggers(game)

        move_to_zone(game, opponent_card, Zone.GRAVEYARD, Zone.HAND)

        assert len(game.stack) == 0
        assert historian.power == 2
        assert historian.toughness == 3
