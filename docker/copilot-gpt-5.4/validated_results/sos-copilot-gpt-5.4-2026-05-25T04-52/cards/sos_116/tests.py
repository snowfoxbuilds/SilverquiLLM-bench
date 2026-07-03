"""Tests for SOS 116 — Garrison Excavator."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_116.card_impl import GarrisonExcavator
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature
from benchmarks.sos.workspace.engine.events import GraveyardLeavesTriggeredEvent
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestGarrisonExcavatorProperties:
    """Static card data should match the SOS 116 spec."""

    def test_is_orc_sorcerer_creature_with_menace(self) -> None:
        card = GarrisonExcavator(owner=None)

        assert isinstance(card, Creature)
        assert "Orc" in card.subtypes
        assert "Sorcerer" in card.subtypes
        assert Keyword.MENACE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = GarrisonExcavator(owner=None)

        assert card.name == "Garrison Excavator"
        assert card.mana_cost == ManaCost.parse("{3}{R}")
        assert card.base_power == 3
        assert card.base_toughness == 4


class TestGarrisonExcavatorGraveyardLeaves:
    """Garrison Excavator should create one Spirit token per graveyard-leave event."""

    def test_registers_a_graveyard_leaves_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GarrisonExcavator(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is GraveyardLeavesTriggeredEvent

    def test_card_leaving_your_graveyard_puts_a_trigger_on_the_stack_and_creates_a_red_and_white_2_2_spirit(self) -> None:
        game = create_game()
        p1 = game.players[0]
        excavator = GarrisonExcavator(owner=p1, controller=p1)
        lesson = CardImpl(name="Recovered Lesson", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[excavator], graveyard=[lesson])
        excavator.register_triggers(game)

        move_to_zone(game, lesson, Zone.GRAVEYARD, Zone.HAND)

        assert len(game.stack) == 1
        assert game.stack.peek().source is excavator

        resolve_top(game)

        tokens = [
            permanent
            for permanent in game.get_battlefield(p1).get_all()
            if getattr(permanent, "is_token", False)
        ]
        assert len(tokens) == 1
        token = tokens[0]
        assert isinstance(token, Creature)
        assert token.power == 2
        assert token.toughness == 2
        assert "Spirit" in token.subtypes
        assert get_colors(token) == {Color.RED, Color.WHITE}

    def test_single_graveyard_leaves_event_with_multiple_cards_creates_only_one_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        excavator = GarrisonExcavator(owner=p1, controller=p1)
        first = CardImpl(name="First Lesson", owner=p1, controller=p1)
        second = CardImpl(name="Second Lesson", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[excavator])
        excavator.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            GraveyardLeavesTriggeredEvent(
                player=p1,
                cards=[first, second],
                destination=Zone.EXILE,
            ),
        )

        assert len(game.stack) == 1
        resolve_top(game)

        tokens = [
            permanent
            for permanent in game.get_battlefield(p1).get_all()
            if getattr(permanent, "is_token", False)
        ]
        assert len(tokens) == 1
