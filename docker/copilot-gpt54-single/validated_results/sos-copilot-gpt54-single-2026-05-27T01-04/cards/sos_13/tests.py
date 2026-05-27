"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Color, Keyword, ManaCost
from test_utils import create_game, set_board_state


def _creature_count(game, player) -> int:
    return sum(
        1
        for obj in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


def _inklings(game, player) -> list[Creature]:
    return [
        obj
        for obj in game.get_battlefield(player).get_all()
        if isinstance(obj, Creature) and "Inkling" in getattr(obj, "subtypes", set())
    ]


class TestEmeritusOfTruceProperties:
    """Static card data should match the SOS 13 creature-side spec."""

    def test_is_a_cat_cleric_creature_named_emeritus_of_truce(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert CardType.CREATURE in card.card_types
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_has_white_three_mana_cost_three_three_stats_and_oracle_text(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.base_power == 3
        assert card.base_toughness == 3
        assert card.rules_text == (
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared. "
            "(While it's prepared, you may cast a copy of its spell. Doing so "
            "unprepares it.)"
        )


class TestEmeritusOfTruceEnterTrigger:
    """Its enter trigger should create an Inkling, then check for preparation."""

    def test_registers_one_self_enter_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)

        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent
        assert triggers[0].controller is p1

    def test_etb_target_player_creates_a_white_black_flying_inkling_for_that_player(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        p1._script.append(p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )

        assert len(game.stack) == 1
        game.stack.pop().on_resolve(game)

        created = _inklings(game, p1)
        assert len(created) == 1
        token = created[0]
        assert token.is_token is True
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert Keyword.FLYING in token.keywords
        assert set(getattr(token, "colors", set())) == {Color.WHITE, Color.BLACK}
        assert _inklings(game, p2) == []

    def test_etb_can_target_an_opponent_player_for_token_creation(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        p1._script.append(p2)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )
        game.stack.pop().on_resolve(game)

        assert _inklings(game, p1) == []
        assert len(_inklings(game, p2)) == 1

    def test_prepares_when_targeted_player_ends_with_more_creatures_than_you(self) -> None:
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

        p1._script.append(p2)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[opposing_bear])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )
        game.stack.pop().on_resolve(game)

        assert _creature_count(game, p2) == 2
        assert _creature_count(game, p1) == 1
        assert getattr(card, "is_prepared", False) is True

    def test_does_not_prepare_when_no_opponent_controls_more_creatures_after_the_token(self) -> None:
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

        p1._script.append(p1)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[opposing_bear])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )
        game.stack.pop().on_resolve(game)

        assert _creature_count(game, p1) == 2
        assert _creature_count(game, p2) == 1
        assert getattr(card, "is_prepared", False) is False

    def test_illegal_non_player_choice_is_ignored(self) -> None:
        invalid_target = Creature(name="Not a Player", base_power=1, base_toughness=1)
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        p1._script.append(invalid_target)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )

        assert len(game.stack) == 1
        game.stack.pop().on_resolve(game)

        assert _inklings(game, p1) == []
        assert _inklings(game, p2) == []
        assert getattr(card, "is_prepared", False) is False
