"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from types import MethodType

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Keyword, ManaCost
from test_utils import create_game, set_board_state


def _bind_choose_target(player, chosen_target, *, expected_options=None) -> None:
    def choose_target(self, options, description):
        if expected_options is not None:
            assert set(options) == set(expected_options)
        return chosen_target

    player.choose_target = MethodType(choose_target, player)


def _make_bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _inklings(game, player) -> list[Creature]:
    return [
        obj
        for obj in game.get_battlefield(player).get_all()
        if isinstance(obj, Creature) and "Inkling" in getattr(obj, "subtypes", set())
    ]


class TestEmeritusOfTruceProperties:
    """Static front-face characteristics from the card spec."""

    def test_is_a_cat_cleric_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert {"Cat", "Cleric"} <= card.subtypes

    def test_name_mana_cost_and_power_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestEmeritusOfTruceEntersTrigger:
    """ETB trigger contract: target player gets an Inkling, then preparation is checked."""

    def test_registers_one_enters_battlefield_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent

    def test_other_creature_entering_does_not_trigger_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        other = _make_bear("Other Creature")

        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=other, controller=p1),
        )

        assert game.stack.is_empty()

    def test_trigger_chooses_target_on_stack_and_that_player_gets_the_inkling(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        _bind_choose_target(p1, p2, expected_options=game.players)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )

        trigger = game.stack.pop()
        assert trigger.targets == [p2]

        _bind_choose_target(p1, p1, expected_options=game.players)
        trigger.on_resolve(game)

        p2_inklings = _inklings(game, p2)
        assert len(p2_inklings) == 1
        token = p2_inklings[0]
        assert token.is_token is True
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert "Inkling" in token.subtypes
        assert Keyword.FLYING in token.keywords
        assert _inklings(game, p1) == []

    def test_targeting_an_opponent_can_prepare_it_after_the_token_changes_creature_counts(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        opposing_creature = _make_bear("Opponent Bear")

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[opposing_creature])
        card.register_triggers(game)

        assert card.is_prepared is False
        _bind_choose_target(p1, p2, expected_options=game.players)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert card.is_prepared is True

    def test_giving_yourself_the_token_can_stop_preparation_if_counts_become_tied(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        first_opposing_creature = _make_bear("Opponent Bear 1")
        second_opposing_creature = _make_bear("Opponent Bear 2")

        set_board_state(game, 0, battlefield=[card])
        set_board_state(
            game,
            1,
            battlefield=[first_opposing_creature, second_opposing_creature],
        )
        card.register_triggers(game)

        assert card.is_prepared is False
        _bind_choose_target(p1, p1, expected_options=game.players)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert card.is_prepared is False
