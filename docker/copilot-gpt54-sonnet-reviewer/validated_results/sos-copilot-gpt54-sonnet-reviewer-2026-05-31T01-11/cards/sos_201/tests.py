"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Step,
    Supertype,
    Zone,
)
from engine.zones import move_to_zone
from test_utils import create_game, set_board_state


def _set_step(game, phase: Phase, step: Step | None, active_player_index: int) -> None:
    game.active_player_index = active_player_index
    game.priority_player_index = active_player_index
    game.phase = phase
    game.step = step


def _put_on_top_of_library(player, card) -> None:
    card.owner = player
    card.controller = player
    player.zones[Zone.LIBRARY].add(card)


class TestLoreholdTheHistorianProperties:
    """Static card data should match the SOS 201 spec."""

    def test_is_legendary_creature_elder_dragon(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes

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


class TestLoreholdTheHistorianMiracle:
    """The battlefield ability should grant miracle {2} to your drawn instants/sorceries."""

    def test_first_instant_draw_pushes_locked_miracle_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_card = Instant(name="Recovered Lesson", mana_cost=ManaCost.parse("{4}{U}"))

        set_board_state(game, 0, battlefield=[card])
        _put_on_top_of_library(p1, drawn_card)
        _set_step(game, Phase.BEGINNING, Step.DRAW, 0)
        card.register_triggers(game)

        draw_card(game, p1)

        assert game.get_hand(p1).contains(drawn_card)
        assert not game.stack.is_empty()
        trigger_obj = game.stack.pop()
        assert trigger_obj.source is card
        assert trigger_obj.controller is p1
        assert trigger_obj.targets == [drawn_card]

    def test_first_sorcery_draw_can_be_cast_for_two_during_draw_step(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_card = Sorcery(name="Recovered Thesis", mana_cost=ManaCost.parse("{5}{R}"))

        set_board_state(
            game,
            0,
            battlefield=[card],
            mana={ManaType.COLORLESS: 2},
        )
        _put_on_top_of_library(p1, drawn_card)
        _set_step(game, Phase.BEGINNING, Step.DRAW, 0)
        p1.choose_yes_no = lambda _prompt: True
        card.register_triggers(game)

        draw_card(game, p1)
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert p1.mana_pool.total() == 0
        assert p1.zones[Zone.STACK].contains(drawn_card)
        assert not game.get_hand(p1).contains(drawn_card)
        spell_obj = game.stack.peek()
        assert spell_obj is not None
        assert spell_obj.source is drawn_card

    def test_first_creature_draw_does_not_trigger_miracle(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_card = Creature(name="Campus Guard", base_power=2, base_toughness=2)

        set_board_state(game, 0, battlefield=[card])
        _put_on_top_of_library(p1, drawn_card)
        _set_step(game, Phase.BEGINNING, Step.DRAW, 0)
        card.register_triggers(game)

        draw_card(game, p1)

        assert game.get_hand(p1).contains(drawn_card)
        assert game.stack.is_empty()

    def test_second_card_drawn_this_turn_does_not_trigger_miracle(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_card = Instant(name="Late Lecture", mana_cost=ManaCost.parse("{3}{U}"))

        set_board_state(game, 0, battlefield=[card])
        _put_on_top_of_library(p1, drawn_card)
        _set_step(game, Phase.BEGINNING, Step.DRAW, 0)
        p1.cards_drawn_this_turn = 1
        card.register_triggers(game)

        draw_card(game, p1)

        assert game.get_hand(p1).contains(drawn_card)
        assert game.stack.is_empty()

    def test_declining_miracle_leaves_drawn_spell_in_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_card = Instant(name="Uncast Thesis", mana_cost=ManaCost.parse("{4}{U}"))

        set_board_state(
            game,
            0,
            battlefield=[card],
            mana={ManaType.COLORLESS: 2},
        )
        _put_on_top_of_library(p1, drawn_card)
        _set_step(game, Phase.BEGINNING, Step.DRAW, 0)
        p1.choose_yes_no = lambda _prompt: False
        card.register_triggers(game)

        draw_card(game, p1)
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 2
        assert game.get_hand(p1).contains(drawn_card)
        assert not p1.zones[Zone.STACK].contains(drawn_card)
        assert game.stack.is_empty()

    def test_miracle_trigger_does_not_retarget_if_drawn_card_left_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_card = Instant(name="Stolen Insight", mana_cost=ManaCost.parse("{4}{U}"))

        set_board_state(game, 0, battlefield=[card], mana={ManaType.COLORLESS: 2})
        _put_on_top_of_library(p1, drawn_card)
        _set_step(game, Phase.BEGINNING, Step.DRAW, 0)
        p1.choose_yes_no = lambda _prompt: True
        card.register_triggers(game)

        draw_card(game, p1)
        trigger_obj = game.stack.pop()
        move_to_zone(game, drawn_card, Zone.HAND, Zone.GRAVEYARD)
        trigger_obj.on_resolve(game)

        assert game.get_graveyard(p1).contains(drawn_card)
        assert not p1.zones[Zone.STACK].contains(drawn_card)
        assert game.stack.is_empty()


class TestLoreholdTheHistorianOpponentUpkeepTrigger:
    """The upkeep trigger should loot only on opponents' upkeeps."""

    def test_opponents_upkeep_pushes_trigger(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        _set_step(game, Phase.BEGINNING, Step.UPKEEP, 1)
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert not game.stack.is_empty()
        trigger_obj = game.stack.pop()
        assert trigger_obj.source is card
        assert trigger_obj.controller is p1
        assert game.active_player is p2

    def test_your_own_upkeep_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        _set_step(game, Phase.BEGINNING, Step.UPKEEP, 0)
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert game.stack.is_empty()

    def test_resolving_trigger_can_discard_a_card_to_draw_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        to_discard = Instant(name="Spent Notes", mana_cost=ManaCost.parse("{1}{R}"))
        drawn_card = Sorcery(name="Fresh Research", mana_cost=ManaCost.parse("{2}{W}"))

        set_board_state(game, 0, battlefield=[card], hand=[to_discard])
        _put_on_top_of_library(p1, drawn_card)
        _set_step(game, Phase.BEGINNING, Step.UPKEEP, 1)
        p1.choose_yes_no = lambda _prompt: True
        p1.choose_card = lambda cards, _description: to_discard
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert game.get_graveyard(p1).contains(to_discard)
        assert game.get_hand(p1).contains(drawn_card)
        assert not game.get_hand(p1).contains(to_discard)

    def test_declining_trigger_does_not_discard_or_draw(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        kept_card = Instant(name="Held Notes", mana_cost=ManaCost.parse("{1}{R}"))
        library_card = Sorcery(name="Unread Archive", mana_cost=ManaCost.parse("{2}{W}"))

        set_board_state(game, 0, battlefield=[card], hand=[kept_card])
        _put_on_top_of_library(p1, library_card)
        _set_step(game, Phase.BEGINNING, Step.UPKEEP, 1)
        p1.choose_yes_no = lambda _prompt: False
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert game.get_hand(p1).contains(kept_card)
        assert not game.get_graveyard(p1).contains(kept_card)
        assert p1.zones[Zone.LIBRARY].contains(library_card)

    def test_trigger_with_empty_hand_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        library_card = Instant(name="Still Waiting", mana_cost=ManaCost.parse("{3}{U}"))

        set_board_state(game, 0, battlefield=[card], hand=[])
        _put_on_top_of_library(p1, library_card)
        _set_step(game, Phase.BEGINNING, Step.UPKEEP, 1)
        p1.choose_yes_no = lambda _prompt: True
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert len(game.get_hand(p1).get_all()) == 0
        assert p1.zones[Zone.LIBRARY].contains(library_card)
