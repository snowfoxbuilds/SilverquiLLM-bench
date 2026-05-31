"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature, Instant
from engine.casting import CastingError
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


def _resolve_top_of_stack(game) -> None:
    obj = game.stack.pop()
    obj.on_resolve(game)


def _battlefield_creatures(game, player) -> list[Creature]:
    return [
        obj
        for obj in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    ]


def _prepared_status(card) -> bool:
    return bool(getattr(card, "is_prepared", getattr(card, "prepared", False)))


def _normalized_colors(obj) -> set[str]:
    colors = getattr(obj, "colors", set()) or set()
    return {getattr(color, "value", color) for color in colors}


def _prepared_spell_copies(player) -> list:
    return [
        obj
        for obj in player.zones[Zone.EXILE].get_all()
        if getattr(obj, "name", None) == "Swords to Plowshares"
    ]


class TestEmeritusOfTruceProperties:
    """Static card data should match the creature face of the spec."""

    def test_is_creature(self) -> None:
        assert isinstance(EmeritusOfTruceSwordsToPlowshares(owner=None), Creature)

    def test_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce // Swords to Plowshares"

    def test_front_face_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_front_face_types_and_subtypes(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert CardType.CREATURE in card.card_types
        assert CardType.INSTANT not in card.card_types
        assert {"Cat", "Cleric"} <= card.subtypes

    def test_power_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestEmeritusOfTruceEnterTrigger:
    """The ETB trigger should create the token, then check for preparation."""

    def test_registers_one_self_etb_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent
        assert triggers[0].controller is p1

    def test_does_not_trigger_for_other_permanent_entering(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        other = Creature(
            name="Other Creature",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )

        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=other, controller=p1),
        )

        assert game.stack.is_empty()

    def test_no_target_is_a_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        opposing_bear = Creature(
            name="Opposing Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[opposing_bear])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )
        assert len(game.stack) == 1

        _resolve_top_of_stack(game)

        assert len(_battlefield_creatures(game, p1)) == 1
        assert len(_battlefield_creatures(game, p2)) == 1
        assert _prepared_status(card) is False
        assert _prepared_spell_copies(p1) == []

    def test_target_player_creates_white_black_flying_inkling_token(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        card.chosen_targets = [p2]

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )
        _resolve_top_of_stack(game)

        creatures = _battlefield_creatures(game, p2)
        assert len(creatures) == 1
        token = creatures[0]
        assert token.controller is p2
        assert token.owner is p2
        assert token.is_token is True
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert CardType.CREATURE in token.card_types
        assert "Inkling" in token.subtypes
        assert Keyword.FLYING in token.keywords
        assert _normalized_colors(token) == {"W", "B"}

    def test_targeting_opponent_checks_counts_after_token_and_prepares(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        opposing_bear = Creature(
            name="Opposing Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[opposing_bear])
        card.register_triggers(game)
        card.chosen_targets = [p2]

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )
        _resolve_top_of_stack(game)

        assert len(_battlefield_creatures(game, p1)) == 1
        assert len(_battlefield_creatures(game, p2)) == 2
        assert _prepared_status(card) is True

        prepared_copies = _prepared_spell_copies(p1)
        assert len(prepared_copies) == 1
        prepared_copy = prepared_copies[0]
        assert isinstance(prepared_copy, Instant)
        assert prepared_copy.mana_cost == ManaCost.parse("{W}")
        assert prepared_copy.name == "Swords to Plowshares"
        assert CardType.INSTANT in prepared_copy.card_types

    def test_targeting_yourself_can_avoid_becoming_prepared(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        opposing_bear = Creature(
            name="Opposing Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[opposing_bear])
        card.register_triggers(game)
        card.chosen_targets = [p1]

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )
        _resolve_top_of_stack(game)

        assert len(_battlefield_creatures(game, p1)) == 2
        assert len(_battlefield_creatures(game, p2)) == 1
        assert _prepared_status(card) is False
        assert _prepared_spell_copies(p1) == []


class TestEmeritusPreparedCopyCasting:
    """Prepared copies can be cast from exile and unprepare the source."""

    def test_cast_prepared_copy_from_exile_uses_target_and_unprepares(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        opposing_bear = Creature(
            name="Opposing Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            battlefield=[card],
            mana={ManaType.WHITE: 1},
        )
        set_board_state(game, 1, battlefield=[opposing_bear])
        card.register_triggers(game)
        card.chosen_targets = [p2]

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )
        _resolve_top_of_stack(game)

        prepared_copy = card.get_prepared_spell_copy()
        assert prepared_copy is not None

        p1._script.appendleft(opposing_bear)
        card.cast_prepared_copy(game)

        assert _prepared_status(card) is False
        assert card.get_prepared_spell_copy() is None
        assert _prepared_spell_copies(p1) == []
        assert p1.mana_pool.get(ManaType.WHITE) == 0
        assert len(game.stack) == 1
        stack_obj = game.stack.peek()
        assert stack_obj is not None
        assert stack_obj.source is prepared_copy
        assert stack_obj.targets == [opposing_bear]

    def test_casting_prepared_copy_removes_the_permission_to_cast_again(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        opposing_bear = Creature(
            name="Opposing Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            battlefield=[card],
            mana={ManaType.WHITE: 1},
        )
        set_board_state(game, 1, battlefield=[opposing_bear])
        card.register_triggers(game)
        card.chosen_targets = [p2]

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )
        _resolve_top_of_stack(game)

        assert card.can_cast_prepared_copy(game) is True

        p1._script.appendleft(opposing_bear)
        card.cast_prepared_copy(game)

        assert card.can_cast_prepared_copy(game) is False
        with pytest.raises(CastingError):
            card.cast_prepared_copy(game)
        assert len(game.stack) == 1
