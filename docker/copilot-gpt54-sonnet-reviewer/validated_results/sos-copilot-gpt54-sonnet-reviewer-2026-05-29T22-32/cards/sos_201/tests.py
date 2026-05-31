"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from types import MethodType

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.casting import (
    cast_spell_via_miracle,
    get_alternative_cast_options,
    get_miracle_opportunities,
)
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state


def _bind_choose_yes_no(player, answers: list[bool]) -> None:
    remaining = iter(answers)

    def choose_yes_no(self, prompt: str) -> bool:
        return next(remaining)

    player.choose_yes_no = MethodType(choose_yes_no, player)


def _bind_choose_card(player, chosen_card, *, expected_options=None) -> None:
    def choose_card(self, cards, description: str):
        if expected_options is not None:
            assert set(cards) == set(expected_options)
        return chosen_card

    player.choose_card = MethodType(choose_card, player)


def _set_library(player, cards: list[object]) -> None:
    library = player.zones[Zone.LIBRARY]
    for existing in library.get_all():
        library.remove(existing)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


class TestLoreholdTheHistorianProperties:
    """Static characteristics from the card spec."""

    def test_is_a_legendary_creature_elder_dragon(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes

    def test_name_and_mana_cost(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_power_toughness_flying_and_haste(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert card.base_power == 5
        assert card.base_toughness == 5
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords


class TestLoreholdTheHistorianUpkeepTrigger:
    """Opponent-upkeep discard-then-draw trigger contract."""

    def test_registers_one_beginning_of_upkeep_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is BeginningOfUpkeepTriggeredEvent

    def test_triggers_on_an_opponents_upkeep(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        game.active_player_index = 1

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        trigger = game.stack.peek()
        assert trigger is not None
        assert trigger.source is card
        assert trigger.controller is p1

    def test_only_opponents_upkeeps_trigger_it(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        game.active_player_index = 0

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert game.stack.is_empty()

        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        trigger = game.stack.peek()
        assert trigger is not None
        assert trigger.source is card

    def test_you_may_decline_to_discard_and_then_do_not_draw(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        kept_card = Creature(name="Card Kept in Hand", base_power=2, base_toughness=2)
        drawn_card = Creature(name="Would-Be Drawn Card", base_power=1, base_toughness=1)

        set_board_state(game, 0, battlefield=[card], hand=[kept_card])
        _set_library(p1, [drawn_card])
        card.register_triggers(game)
        game.active_player_index = 1
        _bind_choose_yes_no(p1, [False])

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.get_hand(p1).contains(kept_card)
        assert not game.get_hand(p1).contains(drawn_card)
        assert not game.get_graveyard(p1).contains(kept_card)
        assert p1.zones[Zone.LIBRARY].contains(drawn_card)

    def test_if_you_discard_a_card_you_draw_one_card(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        discard_me = Creature(name="Discard Me", base_power=2, base_toughness=2)
        keep_me = Creature(name="Keep Me", base_power=3, base_toughness=3)
        drawn_card = Creature(name="Drawn Card", base_power=1, base_toughness=1)

        set_board_state(game, 0, battlefield=[card], hand=[discard_me, keep_me])
        _set_library(p1, [drawn_card])
        card.register_triggers(game)
        game.active_player_index = 1
        _bind_choose_yes_no(p1, [True])
        _bind_choose_card(
            p1,
            discard_me,
            expected_options=[discard_me, keep_me],
        )

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.get_graveyard(p1).contains(discard_me)
        assert not game.get_hand(p1).contains(discard_me)
        assert game.get_hand(p1).contains(keep_me)
        assert game.get_hand(p1).contains(drawn_card)
        assert not p1.zones[Zone.LIBRARY].contains(drawn_card)

    def test_with_no_cards_in_hand_the_trigger_is_a_noop(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_card = Creature(name="Library Card", base_power=1, base_toughness=1)

        set_board_state(game, 0, battlefield=[card], hand=[])
        _set_library(p1, [drawn_card])
        card.register_triggers(game)
        game.active_player_index = 1

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert len(game.get_hand(p1).get_all()) == 0
        assert len(game.get_graveyard(p1).get_all()) == 0
        assert p1.zones[Zone.LIBRARY].contains(drawn_card)


class TestLoreholdTheHistorianMiracleGrant:
    """Static miracle-granting contract for cards in hand."""

    def test_grants_miracle_option_to_instant_card_in_your_hand(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        instant = Instant(name="History's Bolt", mana_cost=ManaCost.parse("{4}{R}"))

        set_board_state(game, 0, battlefield=[card], hand=[instant])

        options = get_alternative_cast_options(game, p1, instant)

        assert len(options) == 1
        assert options[0].name == "miracle"
        assert options[0].cost == ManaCost.parse("{2}")
        assert options[0].source is card
        assert options[0].requires_first_draw_this_turn is True
        assert options[0].ignore_timing is True

    def test_grants_miracle_option_to_sorcery_card_in_your_hand(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        sorcery = Sorcery(name="Campus Chronicle", mana_cost=ManaCost.parse("{6}{R}"))

        set_board_state(game, 0, battlefield=[card], hand=[sorcery])

        options = get_alternative_cast_options(game, p1, sorcery)

        assert len(options) == 1
        assert options[0].name == "miracle"
        assert options[0].cost == ManaCost.parse("{2}")
        assert options[0].source is card

    def test_does_not_grant_miracle_to_creature_cards_in_hand(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        creature = Creature(name="Lorehold Student", base_power=2, base_toughness=2)

        set_board_state(game, 0, battlefield=[card], hand=[creature])

        assert get_alternative_cast_options(game, p1, creature) == []

    def test_does_not_grant_miracle_to_opponents_hand_cards(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        instant = Instant(name="Opponent's Note", mana_cost=ManaCost.parse("{3}{R}"))

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, hand=[instant])

        assert get_alternative_cast_options(game, p2, instant) == []

    def test_does_not_grant_miracle_if_lorehold_is_not_on_the_battlefield(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        instant = Instant(name="Uninspired Spark", mana_cost=ManaCost.parse("{4}{R}"))

        set_board_state(game, 0, hand=[card, instant])

        assert get_alternative_cast_options(game, p1, instant) == []


class TestLoreholdTheHistorianMiracleWindow:
    """First-draw miracle opportunity and casting behavior."""

    def test_first_draw_of_turn_creates_public_miracle_opportunity_for_drawn_instant(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_instant = Instant(name="Recovered Lecture", mana_cost=ManaCost.parse("{5}{R}"))

        set_board_state(game, 0, battlefield=[card], hand=[])
        _set_library(p1, [drawn_instant])

        draw_card(game, p1)

        opportunities = get_miracle_opportunities(game, p1, drawn_instant)
        assert len(opportunities) == 1
        assert opportunities[0].card is drawn_instant
        assert opportunities[0].player is p1
        assert opportunities[0].cost == ManaCost.parse("{2}")
        assert opportunities[0].source is card

    def test_second_draw_of_turn_does_not_create_a_miracle_opportunity(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        first_draw = Creature(name="Field Archivist", base_power=1, base_toughness=3)
        second_draw = Instant(name="Belated Discovery", mana_cost=ManaCost.parse("{4}{R}"))

        set_board_state(game, 0, battlefield=[card], hand=[])
        _set_library(p1, [second_draw, first_draw])

        draw_card(game, p1)
        draw_card(game, p1)

        assert get_miracle_opportunities(game, p1, second_draw) == []

    def test_first_draw_of_turn_creature_card_creates_no_miracle_opportunity(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_creature = Creature(name="No Miracle Here", base_power=3, base_toughness=3)

        set_board_state(game, 0, battlefield=[card], hand=[])
        _set_library(p1, [drawn_creature])

        draw_card(game, p1)

        assert get_miracle_opportunities(game, p1) == []

    def test_can_cast_a_drawn_sorcery_via_miracle_during_upkeep_for_two_mana(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_sorcery = Sorcery(name="Sudden Thesis", mana_cost=ManaCost.parse("{6}{R}"))

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[],
            mana={ManaType.COLORLESS: 2},
        )
        _set_library(p1, [drawn_sorcery])
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP

        draw_card(game, p1)

        opportunity = get_miracle_opportunities(game, p1, drawn_sorcery)[0]
        cast_spell_via_miracle(game, opportunity)

        stack_obj = game.stack.peek()
        assert stack_obj is not None
        assert stack_obj.source is drawn_sorcery
        assert not game.get_hand(p1).contains(drawn_sorcery)
        assert p1.zones[Zone.STACK].contains(drawn_sorcery)
        assert p1.mana_pool.total() == 0
        assert drawn_sorcery.mana_spent_amount == 2
        assert get_miracle_opportunities(game, p1, drawn_sorcery) == []
