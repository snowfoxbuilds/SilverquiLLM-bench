"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.casting import CastingError
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Color, Keyword, ManaCost, ManaType
from test_utils import create_game, set_board_state


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


def _creatures(game, player) -> list[Creature]:
    return [
        obj
        for obj in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    ]


def _inklings(game, player) -> list[Creature]:
    return [
        obj
        for obj in _creatures(game, player)
        if "Inkling" in getattr(obj, "subtypes", set())
    ]


def _fire_self_etb(game, source) -> None:
    controller = source.controller
    game.trigger_manager.fire_event(
        game,
        EntersBattlefieldTriggeredEvent(
            permanent=source,
            controller=controller,
            card=source,
            creature=source,
        ),
    )


class TestEmeritusOfTruceProperties:
    def test_is_creature(self) -> None:
        assert isinstance(EmeritusOfTruceSwordsToPlowshares(owner=None), Creature)

    def test_name_and_creature_side_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_is_cat_cleric_three_three(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert {"Cat", "Cleric"} <= card.subtypes
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_starts_unprepared(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert getattr(card, "is_prepared", False) is False


class TestEmeritusOfTruceTriggerRegistration:
    def test_register_triggers_adds_self_etb_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent


class TestEmeritusOfTruceEntersAbility:
    def test_you_may_target_yourself_to_create_a_one_one_flying_inkling(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        p1._script.append(p1)

        card.register_triggers(game)
        _fire_self_etb(game, card)
        _resolve_all(game)

        inklings = _inklings(game, p1)
        assert len(inklings) == 1
        inkling = inklings[0]
        assert inkling.base_power == 1
        assert inkling.base_toughness == 1
        assert Keyword.FLYING in inkling.keywords
        assert len(_inklings(game, p2)) == 0

    def test_created_inkling_is_white_and_black(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        p1._script.append(p1)

        card.register_triggers(game)
        _fire_self_etb(game, card)
        _resolve_all(game)

        inkling = _inklings(game, p1)[0]
        assert inkling.colors == {Color.WHITE, Color.BLACK}

    def test_trigger_locks_target_player_when_put_on_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        p1._script.append(p2)

        card.register_triggers(game)
        _fire_self_etb(game, card)

        p1._script.clear()
        p1._script.append(p1)
        _resolve_all(game)

        assert len(_inklings(game, p2)) == 1
        assert len(_inklings(game, p1)) == 0

    def test_prepares_when_opponent_controls_more_creatures_after_token_creation(self) -> None:
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
        p1._script.append(p2)

        card.register_triggers(game)
        _fire_self_etb(game, card)
        _resolve_all(game)

        assert getattr(card, "is_prepared", False) is True
        exiled_copies = game.get_exile(p1).get_all()
        assert len(exiled_copies) == 1
        prepared_copy = exiled_copies[0]
        assert prepared_copy.name == "Swords to Plowshares"
        assert CardType.INSTANT in getattr(prepared_copy, "card_types", set())
        assert prepared_copy.mana_cost == ManaCost.parse("{W}")

    def test_does_not_prepare_when_creature_counts_end_up_tied(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        p1._script.append(p2)

        card.register_triggers(game)
        _fire_self_etb(game, card)
        _resolve_all(game)

        assert len(_inklings(game, p2)) == 1
        assert getattr(card, "is_prepared", False) is False
        assert game.get_exile(p1).get_all() == []


class TestEmeritusOfTrucePreparedSpellCopy:
    def test_casting_prepared_copy_spends_white_mana_and_unprepares(self) -> None:
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
        set_board_state(game, 0, battlefield=[card], mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[opposing_bear])
        p1._script.append(p2)

        card.register_triggers(game)
        _fire_self_etb(game, card)
        _resolve_all(game)
        prepared_copy = card.get_prepared_copy(game)

        assert prepared_copy is not None

        card.cast_prepared_copy(game)

        assert card.is_prepared is False
        assert card.prepared_copy is None
        assert not game.get_exile(p1).contains(prepared_copy)
        assert game.stack.peek().source is prepared_copy
        assert p1.mana_pool.get(ManaType.WHITE) == 0
        assert prepared_copy.colors_spent == [Color.WHITE]

        game.stack.pop().on_resolve(game)
        assert game.get_graveyard(p1).contains(prepared_copy)

    def test_cannot_cast_prepared_copy_without_paying_its_mana_cost(self) -> None:
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
        p1._script.append(p2)

        card.register_triggers(game)
        _fire_self_etb(game, card)
        _resolve_all(game)
        prepared_copy = card.get_prepared_copy(game)

        assert prepared_copy is not None

        try:
            card.cast_prepared_copy(game)
            raise AssertionError("Expected casting without white mana to fail")
        except CastingError as exc:
            assert "insufficient mana" in str(exc)

        assert card.is_prepared is True
        assert card.prepared_copy is prepared_copy
        assert game.get_exile(p1).contains(prepared_copy)
        assert game.stack.is_empty()
