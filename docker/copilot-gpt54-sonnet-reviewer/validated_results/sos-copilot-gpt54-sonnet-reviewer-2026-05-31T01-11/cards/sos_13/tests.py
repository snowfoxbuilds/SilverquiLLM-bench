"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Color, Keyword, ManaCost
from test_utils import create_game, set_board_state


class TestEmeritusOfTruceProperties:
    """Static front-face data and prepared state should match the spec."""

    def test_is_creature_named_and_costed(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_has_cat_cleric_typing_and_three_three_stats(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert CardType.CREATURE in card.card_types
        assert {"Cat", "Cleric"} <= card.subtypes
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_starts_unprepared(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert hasattr(card, "is_prepared")
        assert card.is_prepared is False


class TestEmeritusOfTruceEnterTrigger:
    """The ETB trigger should target a player, make an Inkling, and prepare conditionally."""

    @staticmethod
    def _fire_self_etb(game, card, target_player) -> None:
        controller = card.controller
        assert controller is not None
        controller._script.appendleft(target_player)
        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=controller),
        )

    @staticmethod
    def _inklings(game, player):
        return [
            permanent
            for permanent in game.get_battlefield(player).get_all()
            if isinstance(permanent, Creature) and "Inkling" in getattr(permanent, "subtypes", set())
        ]

    def test_enter_trigger_locks_chosen_target_player_on_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        self._fire_self_etb(game, card, p2)

        assert not game.stack.is_empty()
        trigger_obj = game.stack.pop()
        assert trigger_obj.source is card
        assert trigger_obj.controller is p1
        assert trigger_obj.targets == [p2]

    def test_target_player_creates_one_one_white_black_inkling_with_flying(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        self._fire_self_etb(game, card, p2)
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        inklings = self._inklings(game, p2)
        assert len(inklings) == 1
        token = inklings[0]
        assert token.is_token is True
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert getattr(token, "colors", None) == {Color.WHITE, Color.BLACK}
        assert Keyword.FLYING in token.keywords

    def test_becomes_prepared_when_opponent_controls_more_creatures_after_resolution(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(
            game,
            1,
            battlefield=[
                Creature(name="Bear 1", base_power=2, base_toughness=2),
                Creature(name="Bear 2", base_power=2, base_toughness=2),
                Creature(name="Bear 3", base_power=2, base_toughness=2),
            ],
        )

        self._fire_self_etb(game, card, p1)
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert card.is_prepared is True

    def test_does_not_become_prepared_when_no_opponent_controls_more_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(
            game,
            1,
            battlefield=[Creature(name="Bear", base_power=2, base_toughness=2)],
        )

        self._fire_self_etb(game, card, p1)
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert card.is_prepared is False

    def test_creature_count_check_happens_after_target_player_gets_the_token(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(
            game,
            1,
            battlefield=[Creature(name="Bear", base_power=2, base_toughness=2)],
        )

        self._fire_self_etb(game, card, p2)
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert card.is_prepared is True
