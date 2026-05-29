"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import Keyword, ManaCost, ManaType
from test_utils import cast_spell, create_game, set_board_state


class TestEmeritusOfTruceProperties:
    """Static card data should match the creature half of the card spec."""

    def test_is_a_creature(self) -> None:
        assert isinstance(EmeritusOfTruceSwordsToPlowshares(owner=None), Creature)

    def test_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce // Swords to Plowshares"

    def test_creature_side_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_is_a_cat_cleric(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_power_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_has_prepared_keyword_and_starts_unprepared(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        prepared = getattr(Keyword, "PREPARED", None)

        assert prepared is not None
        assert prepared in card.keywords
        assert hasattr(card, "is_prepared")
        assert card.is_prepared is False


class TestEmeritusOfTruceEntersBattlefieldTrigger:
    """Its ETB trigger should create an Inkling and update prepared state."""

    @staticmethod
    def _vanilla_creature(name: str) -> Creature:
        return Creature(name=name, base_power=2, base_toughness=2)

    @staticmethod
    def _inklings_on_battlefield(game, player) -> list[Creature]:
        return [
            obj
            for obj in game.get_battlefield(player).get_all()
            if isinstance(obj, Creature) and "Inkling" in getattr(obj, "subtypes", set())
        ]

    def test_registers_an_enters_battlefield_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent

    def test_casting_card_creates_a_white_black_flying_inkling_for_the_chosen_player(self, monkeypatch) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.WHITE: 3},
        )
        monkeypatch.setattr(p1, "choose_target", lambda options, requirement: p2)

        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")

        inklings = self._inklings_on_battlefield(game, p2)
        assert len(inklings) == 1

        token = inklings[0]
        assert token.is_token is True
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert Keyword.FLYING in token.keywords
        assert set(getattr(token, "colors", [])) == {"W", "B"}
        assert token.controller is p2

    def test_targeting_opponent_at_equal_creature_counts_becomes_prepared_after_the_token_is_created(self, monkeypatch) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        ally = self._vanilla_creature("Helpful Bear")
        foe_one = self._vanilla_creature("Enemy Bear")
        foe_two = self._vanilla_creature("Enemy Cleric")

        set_board_state(game, 0, battlefield=[card, ally])
        set_board_state(game, 1, battlefield=[foe_one, foe_two])
        card.register_triggers(game)
        monkeypatch.setattr(p1, "choose_target", lambda options, requirement: p2)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert len(self._inklings_on_battlefield(game, p2)) == 1
        assert hasattr(card, "is_prepared")
        assert card.is_prepared is True

    def test_targeting_yourself_at_equal_creature_counts_does_not_prepare_the_card(self, monkeypatch) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        ally = self._vanilla_creature("Helpful Bear")
        foe_one = self._vanilla_creature("Enemy Bear")
        foe_two = self._vanilla_creature("Enemy Cleric")

        set_board_state(game, 0, battlefield=[card, ally])
        set_board_state(game, 1, battlefield=[foe_one, foe_two])
        card.register_triggers(game)
        monkeypatch.setattr(p1, "choose_target", lambda options, requirement: p1)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert len(self._inklings_on_battlefield(game, p1)) == 1
        assert hasattr(card, "is_prepared")
        assert card.is_prepared is False
