"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Color, Keyword, ManaCost
from test_utils import create_game


class TestEmeritusOfTruceProperties:
    """Static front-face characteristics should match the SOS 13 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(EmeritusOfTruceSwordsToPlowshares(owner=None), Creature)

    def test_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce // Swords to Plowshares"

    def test_mana_cost_uses_creature_face_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_is_cat_cleric(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert CardType.CREATURE in card.card_types
        assert {"Cat", "Cleric"} <= card.subtypes

    def test_power_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestEmeritusOfTruceEnterTrigger:
    """ETB ability should register correctly and create the specified token."""

    def test_registers_one_enters_battlefield_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)

        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())

        assert after - before == 1
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        assert trigger.event_type is EntersBattlefieldTriggeredEvent
        assert trigger.controller is p1

    def test_trigger_condition_matches_only_this_creatures_entry(self) -> None:
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
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]

        assert trigger.condition is not None
        assert trigger.condition(
            game,
            EntersBattlefieldTriggeredEvent(
                permanent=card,
                controller=p1,
                creature=card,
                card=card,
            ),
        ) is True
        assert trigger.condition(
            game,
            EntersBattlefieldTriggeredEvent(
                permanent=other,
                controller=p1,
                creature=other,
                card=other,
            ),
        ) is False


class TestEmeritusOfTruceTokenCreation:
    """The ETB effect should create the specified Inkling token for the target player."""

    def test_targeted_opponent_gets_one_one_flying_inkling(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]

        card.chosen_targets = [p2]
        trigger.effect(game)

        assert len(game.get_battlefield(p1).get_all()) == 1
        created = game.get_battlefield(p2).get_all()
        assert len(created) == 1
        token = created[0]
        assert isinstance(token, Creature)
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert "Inkling" in token.subtypes
        assert Keyword.FLYING in token.keywords

    def test_controller_can_also_be_the_target_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]

        card.chosen_targets = [p1]
        trigger.effect(game)

        battlefield = game.get_battlefield(p1).get_all()
        assert len(battlefield) == 2
        token = next(obj for obj in battlefield if obj is not card)
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert "Inkling" in token.subtypes


class TestEmeritusOfTruceTriggeredResolution:
    """The ETB trigger should target players on the stack and update prepared state."""

    @staticmethod
    def _other_creature(owner: object) -> Creature:
        creature = Creature(
            name="Support Bear",
            owner=owner,
            controller=owner,
            base_power=2,
            base_toughness=2,
        )
        creature.card_types = {CardType.CREATURE}
        return creature

    @staticmethod
    def _fire_enter_trigger(game: object, card: object, controller: object) -> object:
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(
                permanent=card,
                controller=controller,
                creature=card,
                card=card,
            ),
        )
        stack_obj = game.stack.peek()
        assert stack_obj is not None
        return stack_obj

    def test_etb_trigger_targets_player_on_stack_and_prepares_after_opponent_gets_token(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        game.get_battlefield(p2).add(self._other_creature(p2))
        card.register_triggers(game)

        def choose_target(options: list[object], requirement: object) -> object:
            assert len(options) == 2
            assert p1 in options
            assert p2 in options
            assert requirement.description == "target player"
            return p2

        p1.choose_target = choose_target

        stack_obj = self._fire_enter_trigger(game, card, p1)

        assert stack_obj.targets == [p2]
        assert card.is_prepared is False

        game.stack.pop().on_resolve(game)

        battlefield = game.get_battlefield(p2).get_all()
        assert len(battlefield) == 2
        token = next(obj for obj in battlefield if getattr(obj, 'name', '') == 'Inkling')
        assert token.colors == {Color.WHITE, Color.BLACK}
        assert card.is_prepared is True

    def test_etb_trigger_can_target_controller_and_leaves_card_unprepared_when_counts_do_not_favor_opponent(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        game.get_battlefield(p2).add(self._other_creature(p2))
        card.register_triggers(game)

        def choose_target(options: list[object], requirement: object) -> object:
            assert len(options) == 2
            assert p1 in options
            assert p2 in options
            assert requirement.description == "target player"
            return p1

        p1.choose_target = choose_target

        stack_obj = self._fire_enter_trigger(game, card, p1)

        assert stack_obj.targets == [p1]

        game.stack.pop().on_resolve(game)

        battlefield = game.get_battlefield(p1).get_all()
        assert len(battlefield) == 2
        token = next(obj for obj in battlefield if obj is not card)
        assert token.colors == {Color.WHITE, Color.BLACK}
        assert card.is_prepared is False
