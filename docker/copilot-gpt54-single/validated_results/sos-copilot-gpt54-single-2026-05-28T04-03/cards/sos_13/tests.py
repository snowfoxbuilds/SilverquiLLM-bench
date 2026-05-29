"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Color, Keyword, ManaCost
from test_utils import create_game, set_board_state


def _vanilla_creature(name: str) -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _inklings(game, player) -> list[Creature]:
    return [
        obj
        for obj in game.get_battlefield(player).get_all()
        if isinstance(obj, Creature) and "Inkling" in getattr(obj, "subtypes", set())
    ]


class TestEmeritusOfTruceProperties:
    """Static front-face characteristics should match the SOS 13 spec."""

    def test_is_a_three_three_cat_cleric_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert {"Cat", "Cleric"} <= card.subtypes
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_name_uses_the_full_split_card_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce // Swords to Plowshares"

    def test_front_face_mana_cost_is_one_white_white(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_starts_unprepared(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.prepared is False


class TestEmeritusOfTruceEnterTheBattlefieldTrigger:
    """The ETB trigger should target a player, make an Inkling, then check prepared."""

    def test_registers_a_self_enters_trigger_with_target_locking(self) -> None:
        game = create_game()
        player = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=player, controller=player)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent
        assert triggers[0].stack_object_factory is not None

    def test_trigger_locks_in_the_chosen_player_and_gives_that_player_the_inkling(self) -> None:
        game = create_game()
        caster = game.players[0]
        chosen_player = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=caster, controller=caster)
        set_board_state(game, 0, battlefield=[card])

        caster.choose_target = lambda options, requirement: chosen_player
        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=caster),
        )

        trigger_obj = game.stack.pop()
        assert trigger_obj.targets == [chosen_player]

        caster.choose_target = lambda options, requirement: caster
        trigger_obj.on_resolve(game)

        assert len(_inklings(game, caster)) == 0
        inklings = _inklings(game, chosen_player)
        assert len(inklings) == 1

        token = inklings[0]
        assert token.is_token is True
        assert CardType.CREATURE in token.card_types
        assert "Inkling" in token.subtypes
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert Keyword.FLYING in token.keywords
        assert token.colors == {Color.WHITE, Color.BLACK}

    def test_becomes_prepared_when_an_opponent_still_controls_more_creatures_after_the_token(self) -> None:
        game = create_game()
        caster = game.players[0]
        opponent = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=caster, controller=caster)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(
            game,
            1,
            battlefield=[
                _vanilla_creature("Bear A"),
                _vanilla_creature("Bear B"),
                _vanilla_creature("Bear C"),
            ],
        )

        caster.choose_target = lambda options, requirement: caster
        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=caster),
        )

        game.stack.pop().on_resolve(game)

        assert len(_inklings(game, caster)) == 1
        assert len(game.get_battlefield(opponent).get_all()) == 3
        assert card.prepared is True

    def test_does_not_become_prepared_when_the_created_token_makes_creature_counts_equal(self) -> None:
        game = create_game()
        caster = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=caster, controller=caster)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(
            game,
            1,
            battlefield=[
                _vanilla_creature("Bear A"),
                _vanilla_creature("Bear B"),
            ],
        )

        caster.choose_target = lambda options, requirement: caster
        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=caster),
        )

        game.stack.pop().on_resolve(game)

        assert len(_inklings(game, caster)) == 1
        assert card.prepared is False
