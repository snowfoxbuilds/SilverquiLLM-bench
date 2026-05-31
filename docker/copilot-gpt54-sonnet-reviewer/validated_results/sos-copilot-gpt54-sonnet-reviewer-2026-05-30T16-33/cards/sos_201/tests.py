"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import CardType, Keyword, ManaCost, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state


def _set_library(player, cards: list[object]) -> None:
    """Replace *player*'s library with *cards* in bottom-to-top order."""
    library = player.zones[Zone.LIBRARY]
    for obj in library.get_all():
        library.remove(obj)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


class TestLoreholdTheHistorianProperties:
    """Static card data and miracle metadata should match the SOS 201 spec."""

    def test_is_a_legendary_elder_dragon_with_flying_haste_and_five_five(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert CardType.CREATURE in card.card_types
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_name_mana_cost_and_rules_text_match_the_spec(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert card.rules_text == (
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}. "
            "(You may cast a card for its miracle cost when you draw it if "
            "it's the first card you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card."
        )

    def test_exposes_miracle_metadata_with_cost_two(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert "Miracle" in getattr(card, "mechanic_keywords", set())
        miracle_metadata = getattr(card, "keyword_metadata", {}).get("Miracle")
        assert miracle_metadata is not None
        assert miracle_metadata.get("cost") == ManaCost.parse("{2}")


class TestLoreholdTheHistorianMiracleGrant:
    """Lorehold should grant miracle {2} only during the correct draw window."""

    def test_opening_hand_instant_is_not_miracle_castable_without_a_real_draw(self) -> None:
        opening_hand = [Instant(name=f"Opening Lesson {index}") for index in range(7)]
        game = create_game(deck1=opening_hand)
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        opening_instant = game.get_hand(p1).get_all()[0]

        assert game.is_miracle_draw_window(p1, opening_instant) is False
        assert game.get_miracle_cost(p1, opening_instant) is None
        assert game.can_cast_via_miracle(p1, opening_instant) is False

    def test_first_drawn_instant_in_hand_is_castable_via_miracle_for_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_card = Instant(name="Sudden Lecture")
        set_board_state(game, 0, battlefield=[card], hand=[])
        _set_library(p1, [drawn_card])

        draw_card(game, p1)

        assert game.is_miracle_draw_window(p1, drawn_card) is True
        assert game.get_miracle_cost(p1, drawn_card) == ManaCost.parse("{2}")
        assert game.can_cast_via_miracle(p1, drawn_card) is True

    def test_first_drawn_sorcery_in_hand_is_castable_via_miracle_for_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_card = Sorcery(name="Auditorium Revelation")
        set_board_state(game, 0, battlefield=[card], hand=[])
        _set_library(p1, [drawn_card])

        draw_card(game, p1)

        assert game.is_miracle_draw_window(p1, drawn_card) is True
        assert game.get_miracle_cost(p1, drawn_card) == ManaCost.parse("{2}")
        assert game.can_cast_via_miracle(p1, drawn_card) is True

    def test_first_drawn_noninstant_nonsorcery_does_not_gain_miracle_permission(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_card = Creature(name="Campus Custodian", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card], hand=[])
        _set_library(p1, [drawn_card])

        draw_card(game, p1)

        assert game.is_miracle_draw_window(p1, drawn_card) is True
        assert game.get_miracle_cost(p1, drawn_card) is None
        assert game.can_cast_via_miracle(p1, drawn_card) is False

    def test_second_card_drawn_this_turn_is_not_castable_via_miracle(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        first_draw = Creature(name="First Draw", base_power=1, base_toughness=1)
        second_draw = Instant(name="Second Bell")
        set_board_state(game, 0, battlefield=[card], hand=[])
        _set_library(p1, [second_draw, first_draw])

        draw_card(game, p1)
        draw_card(game, p1)

        assert game.is_miracle_draw_window(p1, second_draw) is False
        assert game.get_miracle_cost(p1, second_draw) is None
        assert game.can_cast_via_miracle(p1, second_draw) is False

    def test_miracle_permission_expires_after_the_turn_changes(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_card = Instant(name="Until End of Class")
        set_board_state(game, 0, battlefield=[card], hand=[])
        _set_library(p1, [drawn_card])

        draw_card(game, p1)
        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()

        assert game.is_miracle_draw_window(p1, drawn_card) is False
        assert game.get_miracle_cost(p1, drawn_card) is None
        assert game.can_cast_via_miracle(p1, drawn_card) is False


class TestLoreholdTheHistorianUpkeepTrigger:
    """Opponent-upkeep trigger should offer a discard-then-draw exchange."""

    def test_registers_one_beginning_of_upkeep_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is BeginningOfUpkeepTriggeredEvent

    def test_trigger_does_not_fire_during_your_own_upkeep(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP

        card.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert game.stack.is_empty()

    def test_opponents_upkeep_may_discard_a_card_to_draw_a_card(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        discard_me = Creature(name="Lecture Notes", base_power=1, base_toughness=1)
        drawn_card = Creature(name="Fresh Chapter", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card], hand=[discard_me])
        _set_library(p1, [drawn_card])
        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP
        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: discard_me

        card.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.get_graveyard(p1).contains(discard_me)
        assert not game.get_hand(p1).contains(discard_me)
        assert game.get_hand(p1).contains(drawn_card)
        assert not game.get_library(p1).contains(drawn_card)

    def test_declining_to_discard_leaves_hand_graveyard_and_library_unchanged(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        keep_me = Creature(name="Keep Me", base_power=1, base_toughness=1)
        library_card = Creature(name="Unread Chapter", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card], hand=[keep_me])
        _set_library(p1, [library_card])
        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP
        p1.choose_yes_no = lambda prompt: False

        card.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.get_hand(p1).contains(keep_me)
        assert not game.get_graveyard(p1).contains(keep_me)
        assert game.get_library(p1).contains(library_card)
        assert not game.get_hand(p1).contains(library_card)

    def test_empty_hand_makes_the_opponents_upkeep_trigger_a_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        library_card = Creature(name="Still Waiting", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card], hand=[])
        _set_library(p1, [library_card])
        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP

        card.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert len(game.get_graveyard(p1).get_all()) == 0
        assert game.get_library(p1).contains(library_card)
        assert not game.get_hand(p1).contains(library_card)
