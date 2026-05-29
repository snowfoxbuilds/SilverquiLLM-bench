"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell_via_miracle
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.miracle import can_cast_via_miracle, get_miracle_window, reveal_miracle
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state


def _resolve_entire_stack(game) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestLoreholdTheHistorianProperties:
    """Static card data should match the SOS 201 spec."""

    def test_is_legendary_elder_dragon_creature(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_name_and_mana_cost(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_power_and_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying_and_haste(self) -> None:
        keywords = LoreholdTheHistorian(owner=None).keywords

        assert Keyword.FLYING in keywords
        assert Keyword.HASTE in keywords


class TestLoreholdTheHistorianUpkeepTrigger:
    """At each opponent's upkeep, you may discard a card to draw a card."""

    def test_opponents_upkeep_you_may_discard_a_card_to_draw_a_card(self) -> None:
        game = create_game()
        p1, p2 = game.players
        historian = LoreholdTheHistorian(owner=p1, controller=p1)
        discarded_card = Creature(
            name="Old Lecture Notes",
            base_power=2,
            base_toughness=2,
        )
        drawn_card = Instant(
            name="Fresh Inspiration",
            mana_cost=ManaCost.parse("{1}{R}"),
        )

        set_board_state(game, 0, battlefield=[historian], hand=[discarded_card])
        drawn_card.owner = p1
        drawn_card.controller = p1
        game.get_library(p1).add(drawn_card)
        historian.register_triggers(game)

        game.active_player_index = 1
        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: discarded_card

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert len(game.stack) == 1

        _resolve_entire_stack(game)

        assert game.get_graveyard(p1).contains(discarded_card)
        assert not game.get_hand(p1).contains(discarded_card)
        assert game.get_hand(p1).contains(drawn_card)
        assert not game.get_library(p1).contains(drawn_card)

    def test_you_may_decline_to_discard_and_not_draw(self) -> None:
        game = create_game()
        p1, p2 = game.players
        historian = LoreholdTheHistorian(owner=p1, controller=p1)
        kept_card = Creature(
            name="Research Assistant",
            base_power=1,
            base_toughness=1,
        )
        top_library_card = Instant(
            name="Future Lesson",
            mana_cost=ManaCost.parse("{2}{R}"),
        )

        set_board_state(game, 0, battlefield=[historian], hand=[kept_card])
        top_library_card.owner = p1
        top_library_card.controller = p1
        game.get_library(p1).add(top_library_card)
        historian.register_triggers(game)

        game.active_player_index = 1
        p1.choose_yes_no = lambda prompt: False

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_entire_stack(game)

        assert game.get_hand(p1).contains(kept_card)
        assert not game.get_graveyard(p1).contains(kept_card)
        assert game.get_library(p1).contains(top_library_card)
        assert not game.get_hand(p1).contains(top_library_card)

    def test_your_own_upkeep_does_not_trigger_the_ability(self) -> None:
        game = create_game()
        p1 = game.players[0]
        historian = LoreholdTheHistorian(owner=p1, controller=p1)
        hand_card = Creature(
            name="Kept Card",
            base_power=2,
            base_toughness=2,
        )

        set_board_state(game, 0, battlefield=[historian], hand=[hand_card])
        historian.register_triggers(game)

        game.active_player_index = 0
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert game.stack.is_empty()
        assert game.get_hand(p1).contains(hand_card)

    def test_opponents_upkeep_with_empty_hand_does_not_draw_a_card(self) -> None:
        game = create_game()
        p1, p2 = game.players
        historian = LoreholdTheHistorian(owner=p1, controller=p1)
        top_library_card = Instant(
            name="Unread Chapter",
            mana_cost=ManaCost.parse("{1}{W}"),
        )

        set_board_state(game, 0, battlefield=[historian], hand=[])
        top_library_card.owner = p1
        top_library_card.controller = p1
        game.get_library(p1).add(top_library_card)
        historian.register_triggers(game)

        game.active_player_index = 1
        p1.choose_yes_no = lambda prompt: True

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_entire_stack(game)

        assert game.get_library(p1).contains(top_library_card)
        assert not game.get_hand(p1).contains(top_library_card)
        assert game.get_hand(p1).get_all() == []
        assert game.get_graveyard(p1).get_all() == []


class TestLoreholdTheHistorianMiracle:
    """Lorehold grants miracle {2} to instant and sorcery cards in hand."""

    def test_grants_miracle_two_to_instants_and_sorceries_in_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        historian = LoreholdTheHistorian(owner=p1, controller=p1)
        instant_card = Instant(
            name="Sudden Insight",
            mana_cost=ManaCost.parse("{1}{R}"),
        )
        sorcery_card = Sorcery(
            name="Recovered Lesson",
            mana_cost=ManaCost.parse("{4}{W}"),
        )
        creature_card = Creature(
            name="Campus Custodian",
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            battlefield=[historian],
            hand=[instant_card, sorcery_card, creature_card],
        )

        instant_metadata = instant_card.get_miracle_metadata(game)

        assert instant_card.has_miracle(game) is True
        assert instant_metadata is not None
        assert instant_metadata.cost == ManaCost.parse("{2}")
        assert instant_metadata.granted is True
        assert instant_metadata.source is historian
        assert sorcery_card.get_miracle_cost(game) == ManaCost.parse("{2}")
        assert creature_card.get_miracle_metadata(game) is None

    def test_first_card_drawn_can_be_revealed_and_cast_for_miracle_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        historian = LoreholdTheHistorian(owner=p1, controller=p1)
        miracle_card = Sorcery(
            name="Recovered Lesson",
            mana_cost=ManaCost.parse("{5}{R}"),
        )

        set_board_state(
            game,
            0,
            battlefield=[historian],
            hand=[],
            mana={ManaType.COLORLESS: 2},
        )
        miracle_card.owner = p1
        miracle_card.controller = p1
        game.get_library(p1).add(miracle_card)
        game.phase = Phase.BEGINNING
        game.step = Step.DRAW

        drawn_card = draw_card(game, p1)
        miracle_window = get_miracle_window(game, p1, miracle_card)

        assert drawn_card is miracle_card
        assert miracle_window is not None
        assert miracle_window.cost == ManaCost.parse("{2}")
        assert can_cast_via_miracle(game, p1, miracle_card) is False
        assert reveal_miracle(game, p1, miracle_card) is True
        assert can_cast_via_miracle(game, p1, miracle_card) is True

        cast_spell_via_miracle(game, p1, miracle_card)

        assert len(game.stack) == 1
        assert not game.get_hand(p1).contains(miracle_card)
        assert p1.mana_pool.total() == 0

        _resolve_entire_stack(game)

        assert game.get_graveyard(p1).contains(miracle_card)
        assert get_miracle_window(game, p1, miracle_card) is None

    def test_second_card_drawn_this_turn_does_not_get_miracle_window(self) -> None:
        game = create_game()
        p1 = game.players[0]
        historian = LoreholdTheHistorian(owner=p1, controller=p1)
        first_draw = Creature(
            name="Campus Custodian",
            base_power=2,
            base_toughness=2,
        )
        second_draw = Instant(
            name="Sudden Insight",
            mana_cost=ManaCost.parse("{4}{R}"),
        )

        set_board_state(game, 0, battlefield=[historian], hand=[])
        first_draw.owner = p1
        first_draw.controller = p1
        second_draw.owner = p1
        second_draw.controller = p1
        game.get_library(p1).add(second_draw)
        game.get_library(p1).add(first_draw)

        assert draw_card(game, p1) is first_draw
        assert draw_card(game, p1) is second_draw
        assert second_draw.has_miracle(game) is True
        assert get_miracle_window(game, p1, second_draw) is None
        assert reveal_miracle(game, p1, second_draw) is False
        assert can_cast_via_miracle(game, p1, second_draw) is False
