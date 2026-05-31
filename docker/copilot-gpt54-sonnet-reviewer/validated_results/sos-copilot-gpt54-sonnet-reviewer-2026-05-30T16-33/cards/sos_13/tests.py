"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature, Instant
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Keyword, ManaCost
from test_utils import create_game, set_board_state


def _resolve_self_etb(game, card: EmeritusOfTruceSwordsToPlowshares, target_player) -> None:
    """Register the card's ETB trigger, choose *target_player*, and resolve it."""
    controller = card.controller
    if controller is not None and hasattr(controller, "_script"):
        controller._script.appendleft(target_player)
    card.chosen_targets = [target_player]
    card.register_triggers(game)
    game.trigger_manager.fire_event(
        game,
        EntersBattlefieldTriggeredEvent(permanent=card, controller=card.controller),
    )
    trigger = game.stack.pop()
    trigger.on_resolve(game)


def _inklings(game, player) -> list[Creature]:
    """Return Inkling creatures controlled by *player*."""
    return [
        obj
        for obj in game.get_battlefield(player).get_all()
        if isinstance(obj, Creature) and "Inkling" in getattr(obj, "subtypes", set())
    ]


class TestEmeritusOfTruceProperties:
    """Static card data should match the SOS 13 spec's front face."""

    def test_is_a_three_three_cat_cleric_creature_with_front_face_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)

        assert isinstance(card, Creature)
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert CardType.CREATURE in card.card_types
        assert {"Cat", "Cleric"} <= card.subtypes
        assert card.base_power == 3
        assert card.base_toughness == 3
        assert card.rules_text == (
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared. "
            "(While it's prepared, you may cast a copy of its spell. Doing so "
            "unprepares it.)"
        )


class TestEmeritusOfTruceEnterTheBattlefieldTrigger:
    """The ETB trigger should target a player, create an Inkling, and maybe prepare."""

    def test_registers_one_enters_the_battlefield_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent

    def test_targeted_player_gets_a_one_one_flying_white_and_black_inkling(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        _resolve_self_etb(game, card, p2)

        inklings = _inklings(game, p2)
        assert len(inklings) == 1
        token = inklings[0]
        token_colors = {getattr(color, "value", color) for color in getattr(token, "colors", [])}

        assert CardType.CREATURE in token.card_types
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert "Inkling" in token.subtypes
        assert Keyword.FLYING in token.keywords
        assert token_colors == {"W", "B"}

    def test_does_not_become_prepared_when_opponent_is_not_ahead_after_token_creation(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        opposing_bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[opposing_bear])

        _resolve_self_etb(game, card, p1)

        assert getattr(card, "is_prepared", False) is False
        assert len(game.get_exile(p1).get_all()) == 0

    def test_becomes_prepared_and_exiles_a_spell_face_copy_when_opponent_has_more_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        bears = [
            Creature(name=f"Bear {idx}", base_power=2, base_toughness=2)
            for idx in range(2)
        ]
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=bears)

        _resolve_self_etb(game, card, p2)

        exiled = game.get_exile(p1).get_all()
        assert getattr(card, "is_prepared", False) is True
        assert len(exiled) == 1

        prepared_copy = exiled[0]
        assert isinstance(prepared_copy, Instant)
        assert prepared_copy.name == "Swords to Plowshares"
        assert prepared_copy.mana_cost == ManaCost.parse("{W}")
        assert CardType.INSTANT in prepared_copy.card_types
        assert CardType.CREATURE not in prepared_copy.card_types
