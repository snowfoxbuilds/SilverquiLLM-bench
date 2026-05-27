"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Color, Keyword, ManaCost
from test_utils import create_game, set_board_state


class TestEmeritusOfTruceProperties:
    """Static characteristics from the creature face of the spec."""

    def test_is_a_cat_cleric_creature_with_printed_stats(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)

        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert {"Cat", "Cleric"} <= card.subtypes
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestEmeritusOfTruceEnterTrigger:
    """ETB trigger contract for token creation and preparation."""

    @staticmethod
    def _creature(name: str) -> Creature:
        creature = Creature(name=name, base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        return creature

    @staticmethod
    def _fire_self_etb(game, card: EmeritusOfTruceSwordsToPlowshares) -> None:
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(
                permanent=card,
                controller=card.controller,
            ),
        )

    @staticmethod
    def _inklings(game, player) -> list[Creature]:
        return [
            obj
            for obj in game.get_battlefield(player).get_all()
            if isinstance(obj, Creature)
            and getattr(obj, "is_token", False)
            and "Inkling" in getattr(obj, "subtypes", set())
        ]

    def test_registers_one_enters_battlefield_trigger(self) -> None:
        game = create_game()
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)

        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent

    def test_another_creature_entering_does_not_trigger_it(self) -> None:
        game = create_game()
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        other = self._creature("Other Cat")

        set_board_state(game, 0, battlefield=[card, other])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(
                permanent=other,
                controller=game.players[0],
            ),
        )

        assert game.stack.is_empty()

    def test_trigger_chooses_a_player_target_when_it_enters(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)

        set_board_state(game, 0, battlefield=[card])
        p1.choose_target = lambda _options, _requirement: p2

        card.register_triggers(game)
        self._fire_self_etb(game, card)

        trigger_obj = game.stack.peek()
        assert trigger_obj is not None
        assert trigger_obj.targets == [p2]
        assert len(trigger_obj.target_requirements) == 1

    def test_targeted_opponent_gets_flying_inkling_and_card_becomes_prepared(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        opp_a = self._creature("Opp A")
        opp_b = self._creature("Opp B")

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[opp_a, opp_b])
        p1.choose_target = lambda _options, _requirement: p2

        card.register_triggers(game)
        self._fire_self_etb(game, card)

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        tokens = self._inklings(game, p2)
        assert len(tokens) == 1
        assert self._inklings(game, p1) == []
        token = tokens[0]
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert CardType.CREATURE in token.card_types
        assert Keyword.FLYING in token.keywords
        assert card.is_prepared is True

    def test_targeted_player_gets_a_white_and_black_inkling(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)

        set_board_state(game, 0, battlefield=[card])
        p1.choose_target = lambda _options, _requirement: p2

        card.register_triggers(game)
        self._fire_self_etb(game, card)

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        tokens = self._inklings(game, p2)
        assert len(tokens) == 1
        assert tokens[0].colors == {Color.WHITE, Color.BLACK}

    def test_targeting_yourself_creates_the_token_before_checking_prepared(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        opp_a = self._creature("Opp A")
        opp_b = self._creature("Opp B")

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[opp_a, opp_b])
        p1.choose_target = lambda _options, _requirement: p1

        card.register_triggers(game)
        self._fire_self_etb(game, card)

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        tokens = self._inklings(game, p1)
        assert len(tokens) == 1
        assert self._inklings(game, p2) == []
        assert card.is_prepared is False
