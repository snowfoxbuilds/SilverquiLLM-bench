"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature, Instant
from engine.events import EntersBattlefieldTriggeredEvent
from engine.stack import PreparedAction, get_legal_actions
from engine.types import Color, Keyword, ManaCost
from test_utils import create_game, set_board_state


class TestEmeritusOfTruceProperties:
    """Static card data should match the creature side of the SOS 13 spec."""

    def test_is_cat_cleric_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)
        assert {"Cat", "Cleric"} <= card.subtypes

    def test_name_mana_cost_and_power_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_starts_unprepared(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert hasattr(card, "is_prepared")
        assert card.is_prepared is False

    def test_exposes_spell_face_name_type_line_and_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.spell_face.name == "Swords to Plowshares"
        assert card.spell_face.mana_cost == ManaCost.parse("{W}")
        assert card.spell_face.type_line == "Instant"
        assert card.spell_side == card.spell_face
        assert card.spell_name == "Swords to Plowshares"
        assert card.spell_mana_cost == ManaCost.parse("{W}")
        assert card.spell_type_line == "Instant"


class TestEmeritusOfTruceEnterTrigger:
    """The ETB ability should create the token, then prepare only if outnumbered."""

    @staticmethod
    def _get_etb_trigger(game, card):
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        trigger = triggers[0]
        assert trigger.event_type is EntersBattlefieldTriggeredEvent
        return trigger

    @staticmethod
    def _inklings(game, player):
        return [
            obj
            for obj in game.get_battlefield(player).get_all()
            if isinstance(obj, Creature) and "Inkling" in getattr(obj, "subtypes", set())
        ]

    def test_trigger_condition_matches_only_this_creature_entering(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        other = Creature(name="Other", base_power=2, base_toughness=2)

        trigger = self._get_etb_trigger(game, card)

        assert trigger.condition(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        ) is True
        assert trigger.condition(
            game,
            EntersBattlefieldTriggeredEvent(permanent=other, controller=p1),
        ) is False

    def test_trigger_makes_target_player_create_one_one_flying_inkling(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        trigger = self._get_etb_trigger(game, card)
        card.chosen_targets = [p2]
        trigger.effect(game)

        inklings = self._inklings(game, p2)
        assert len(inklings) == 1
        token = inklings[0]
        assert token.is_token is True
        assert token.controller is p2
        assert token.owner is p2
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert Keyword.FLYING in token.keywords

    def test_trigger_makes_white_and_black_inkling(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        trigger = self._get_etb_trigger(game, card)
        card.chosen_targets = [p2]
        trigger.effect(game)

        token = self._inklings(game, p2)[0]
        assert token.colors == {Color.WHITE, Color.BLACK}

    def test_trigger_can_target_you_for_the_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        trigger = self._get_etb_trigger(game, card)
        card.chosen_targets = [p1]
        trigger.effect(game)

        inklings = self._inklings(game, p1)
        assert len(inklings) == 1
        assert card in game.get_battlefield(p1).get_all()

    def test_trigger_prepares_this_creature_when_opponent_controls_more_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        opposing_bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[opposing_bear])

        trigger = self._get_etb_trigger(game, card)
        card.chosen_targets = [p2]
        trigger.effect(game)

        assert getattr(card, "is_prepared", False) is True

    def test_trigger_does_not_prepare_when_creature_counts_are_equal(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        bear_one = Creature(name="Bear One", base_power=2, base_toughness=2)
        bear_two = Creature(name="Bear Two", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[bear_one, bear_two])

        trigger = self._get_etb_trigger(game, card)
        card.chosen_targets = [p1]
        trigger.effect(game)

        assert len(self._inklings(game, p1)) == 1
        assert getattr(card, "is_prepared", False) is False


class TestEmeritusOfTrucePreparedAction:
    """Prepared status should expose a public spell-copy cast action."""

    @staticmethod
    def _prepare_card(game):
        p1, p2 = game.players
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        target_creature = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=4,
            base_toughness=4,
        )
        extra_creature = Creature(
            name="Extra Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[target_creature, extra_creature])

        card.register_triggers(game)
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        card.chosen_targets = [p2]
        trigger.effect(game)

        assert card.is_prepared is True
        return card, target_creature

    def test_prepared_permanent_exposes_public_spell_copy_action(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card, _ = self._prepare_card(game)

        actions = get_legal_actions(game, p1)

        assert len(actions) == 1
        action = actions[0]
        assert isinstance(action, PreparedAction)
        assert action.source is card
        assert action.controller is p1
        assert isinstance(action.spell, Instant)
        assert action.spell.name == "Swords to Plowshares"
        assert action.spell.mana_cost == ManaCost.parse("{W}")

    def test_casting_prepared_action_unprepares_and_casts_spell_copy(self) -> None:
        game = create_game(player2_life=9)
        p1, p2 = game.players
        card, target_creature = self._prepare_card(game)

        action = get_legal_actions(game, p1)[0]
        stack_object = action.perform(game, targets=[target_creature])

        assert card.is_prepared is False
        assert game.stack.peek() is stack_object
        assert stack_object.source is not action.spell
        assert isinstance(stack_object.source, Instant)
        assert stack_object.source.name == "Swords to Plowshares"
        assert stack_object.targets == [target_creature]

        resolved = game.stack.pop()
        resolved.on_resolve(game)

        assert game.get_battlefield(p2).contains(target_creature) is False
        assert game.get_exile(p2).contains(target_creature) is True
        assert p2.life == 13
        assert all(
            getattr(obj, "name", None) != "Swords to Plowshares"
            for obj in game.get_graveyard(p1).get_all()
        )
