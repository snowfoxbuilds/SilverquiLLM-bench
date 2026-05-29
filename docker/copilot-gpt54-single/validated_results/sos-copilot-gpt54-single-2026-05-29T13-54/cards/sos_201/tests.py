"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import Keyword, ManaCost, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state


class TestLoreholdTheHistorianProperties:
    """Static card data should match the SOS 201 spec."""

    def test_is_a_legendary_elder_dragon_creature(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes

    def test_name_mana_cost_and_power_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying_and_haste(self) -> None:
        keywords = LoreholdTheHistorian(owner=None).keywords
        assert Keyword.FLYING in keywords
        assert Keyword.HASTE in keywords


class TestLoreholdTheHistorianUpkeepTrigger:
    """Opponent-upkeep loot trigger should discard first, then draw if you did."""

    @staticmethod
    def _get_upkeep_trigger(game, card):
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        trigger = triggers[0]
        assert trigger.event_type is BeginningOfUpkeepTriggeredEvent
        return trigger

    @staticmethod
    def _put_on_top_of_library(player, card) -> None:
        card.owner = player
        card.controller = player
        player.zones[Zone.LIBRARY].add(card)

    def test_registers_a_beginning_of_upkeep_trigger_for_opponents(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        trigger = self._get_upkeep_trigger(game, card)

        assert trigger.source is card
        assert trigger.controller is p1

    def test_trigger_condition_matches_only_an_opponents_upkeep(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        trigger = self._get_upkeep_trigger(game, card)

        game.active_player = p2
        assert trigger.condition(game, BeginningOfUpkeepTriggeredEvent()) is True

        game.active_player = p1
        assert trigger.condition(game, BeginningOfUpkeepTriggeredEvent()) is False

    def test_opponents_upkeep_event_puts_the_trigger_on_the_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        self._get_upkeep_trigger(game, card)

        game.active_player = p2
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert len(game.stack.objects()) == 1
        stack_obj = game.stack.peek()
        assert stack_obj is not None
        assert stack_obj.source is card
        assert stack_obj.controller is p1

    def test_you_may_decline_to_discard_and_then_do_not_draw(self, monkeypatch) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        spare_card = Instant(name="Keep Me", mana_cost=ManaCost.parse("{U}"))
        drawn_card = Sorcery(name="Future Lesson", mana_cost=ManaCost.parse("{1}{R}"))
        set_board_state(game, 0, battlefield=[card], hand=[spare_card])
        self._put_on_top_of_library(p1, drawn_card)
        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: False)

        self._get_upkeep_trigger(game, card)
        game.active_player = p2
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert game.get_hand(p1).contains(spare_card) is True
        assert game.get_hand(p1).contains(drawn_card) is False
        assert game.get_graveyard(p1).contains(spare_card) is False
        assert p1.zones[Zone.LIBRARY].contains(drawn_card) is True

    def test_if_you_discard_a_card_you_draw_a_replacement_card(self, monkeypatch) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        discarded_card = Instant(name="Old Notes", mana_cost=ManaCost.parse("{R}"))
        drawn_card = Sorcery(name="Fresh Notes", mana_cost=ManaCost.parse("{2}{W}"))
        set_board_state(game, 0, battlefield=[card], hand=[discarded_card])
        self._put_on_top_of_library(p1, drawn_card)
        monkeypatch.setattr(p1, "choose_yes_no", lambda prompt: True)
        monkeypatch.setattr(p1, "choose_card", lambda cards, description: discarded_card)

        self._get_upkeep_trigger(game, card)
        game.active_player = p2
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert game.get_hand(p1).contains(discarded_card) is False
        assert game.get_graveyard(p1).contains(discarded_card) is True
        assert game.get_hand(p1).contains(drawn_card) is True
        assert p1.zones[Zone.LIBRARY].contains(drawn_card) is False

    def test_with_no_cards_in_hand_the_trigger_is_a_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_card = Instant(name="Unchanged Future", mana_cost=ManaCost.parse("{W}"))
        set_board_state(game, 0, battlefield=[card], hand=[])
        self._put_on_top_of_library(p1, drawn_card)

        self._get_upkeep_trigger(game, card)
        game.active_player = p2
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert game.get_hand(p1).contains(drawn_card) is False
        assert p1.zones[Zone.LIBRARY].contains(drawn_card) is True
        assert game.get_graveyard(p1).get_all() == []


class TestLoreholdTheHistorianMiracleWindow:
    """First-card draw windows should grant public miracle permissions."""

    @staticmethod
    def _put_on_top_of_library(player, card) -> None:
        card.owner = player
        card.controller = player
        player.zones[Zone.LIBRARY].add(card)

    def test_first_instant_drawn_gains_public_miracle_permission(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_card = Instant(name="Sudden Thesis", mana_cost=ManaCost.parse("{1}{R}"))
        set_board_state(game, 0, battlefield=[card])
        self._put_on_top_of_library(p1, drawn_card)

        assert draw_card(game, p1) is drawn_card

        permissions = drawn_card.get_alternate_cast_permissions()
        assert len(permissions) == 1
        permission = permissions[0]
        assert permission.label == "miracle"
        assert permission.mana_cost == ManaCost.parse("{2}")
        assert permission.from_zone is Zone.HAND
        assert permission.granted_by is card
        assert permission.ignore_timing is True
        assert permission.expires == "draw_window"

    def test_first_sorcery_drawn_gains_public_miracle_permission(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_card = Sorcery(name="Lecture Finale", mana_cost=ManaCost.parse("{2}{W}"))
        set_board_state(game, 0, battlefield=[card])
        self._put_on_top_of_library(p1, drawn_card)

        assert draw_card(game, p1) is drawn_card

        permissions = drawn_card.get_alternate_cast_permissions()
        assert len(permissions) == 1
        assert permissions[0].label == "miracle"
        assert permissions[0].mana_cost == ManaCost.parse("{2}")

    def test_second_card_drawn_this_turn_does_not_gain_miracle_permission(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        first_draw = Instant(name="First Lesson", mana_cost=ManaCost.parse("{R}"))
        second_draw = Instant(name="Follow-Up Lesson", mana_cost=ManaCost.parse("{1}{R}"))
        set_board_state(game, 0, battlefield=[card])
        self._put_on_top_of_library(p1, second_draw)
        self._put_on_top_of_library(p1, first_draw)

        assert draw_card(game, p1) is first_draw
        assert draw_card(game, p1) is second_draw

        assert len(first_draw.get_alternate_cast_permissions()) == 1
        assert second_draw.get_alternate_cast_permissions() == []

    def test_first_drawn_creature_does_not_gain_miracle_permission(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_card = Creature(name="Ordinary Student", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card])
        self._put_on_top_of_library(p1, drawn_card)

        assert draw_card(game, p1) is drawn_card
        assert drawn_card.get_alternate_cast_permissions() == []

    def test_opponents_first_draw_does_not_gain_miracle_permission(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_card = Instant(name="Enemy Epiphany", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, battlefield=[card])
        self._put_on_top_of_library(p2, drawn_card)

        assert draw_card(game, p2) is drawn_card
        assert drawn_card.get_alternate_cast_permissions() == []

    def test_draw_window_permission_clears_when_the_next_turn_begins(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_card = Instant(name="Fleeting Insight", mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, battlefield=[card])
        self._put_on_top_of_library(p1, drawn_card)
        draw_card(game, p1)
        assert len(drawn_card.get_alternate_cast_permissions()) == 1

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()

        assert drawn_card.get_alternate_cast_permissions() == []
