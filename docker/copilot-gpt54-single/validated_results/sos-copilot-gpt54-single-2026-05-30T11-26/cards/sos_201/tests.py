"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.card import Creature, Instant, Sorcery
from engine.types import (
    Color,
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Step,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


class _MiracleTestInstant(Instant):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Flash of Scholarship")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}"))
        super().__init__(**kwargs)
        self.was_resolved = False

    def on_resolve(self, game) -> None:
        self.was_resolved = True
        if self.controller is not None:
            self.controller.life += 3


class _MiracleTestSorcery(Sorcery):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Lesson in Fire")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{W}"))
        super().__init__(**kwargs)
        self.was_resolved = False

    def on_resolve(self, game) -> None:
        self.was_resolved = True
        if self.controller is not None:
            self.controller.life += 4


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)


def _put_library_bottom_to_top(game, player, cards) -> None:
    library = game.get_library(player)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


def _test_creature(name: str = "Test Creature") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


class TestLoreholdTheHistorianProperties:
    def test_is_a_legendary_elder_dragon_creature(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert isinstance(card, Creature)
        assert card.name == "Lorehold, the Historian"
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes

    def test_has_red_white_cost_flying_haste_and_five_five_stats(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert card.colors == {Color.RED, Color.WHITE}
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords
        assert card.base_power == 5
        assert card.base_toughness == 5


class TestLoreholdTheHistorianOpponentUpkeepTrigger:
    def test_on_each_opponents_upkeep_you_may_discard_a_card_to_draw_a_card(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        discarded = _test_creature("Old Notes")
        drawn = _test_creature("Fresh Notes")

        set_board_state(game, 0, battlefield=[lorehold], hand=[discarded])
        _put_library_bottom_to_top(game, p1, [drawn])
        lorehold.register_triggers(game)

        p1.choose_yes_no = lambda _prompt: True
        p1.choose_card = lambda _cards, _description: discarded
        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_all(game)

        assert game.get_graveyard(p1).contains(discarded)
        assert not game.get_hand(p1).contains(discarded)
        assert game.get_hand(p1).contains(drawn)

    def test_does_not_trigger_on_your_own_upkeep(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[lorehold], hand=[_test_creature("Card in Hand")])
        lorehold.register_triggers(game)

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert game.stack.is_empty()

    def test_declining_to_discard_leaves_hand_and_library_unchanged(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        kept = _test_creature("Kept Card")
        top_card = _test_creature("Top Card")

        set_board_state(game, 0, battlefield=[lorehold], hand=[kept])
        _put_library_bottom_to_top(game, p1, [top_card])
        lorehold.register_triggers(game)

        p1.choose_yes_no = lambda _prompt: False
        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_all(game)

        assert game.get_hand(p1).contains(kept)
        assert game.get_library(p1).contains(top_card)
        assert not game.get_hand(p1).contains(top_card)

    def test_with_no_cards_in_hand_the_upkeep_trigger_is_a_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        top_card = _test_creature("Top Card")

        set_board_state(game, 0, battlefield=[lorehold], hand=[])
        _put_library_bottom_to_top(game, p1, [top_card])
        lorehold.register_triggers(game)

        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_all(game)

        assert game.get_hand(p1).get_all() == []
        assert game.get_library(p1).contains(top_card)


class TestLoreholdTheHistorianMiracle:
    def test_first_drawn_instant_can_be_cast_for_miracle_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_instant = _MiracleTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            hand=[],
            mana={ManaType.COLORLESS: 2},
        )
        _put_library_bottom_to_top(game, p1, [drawn_instant])
        lorehold.register_triggers(game)
        p1.cards_drawn_this_turn = 0
        p1.choose_yes_no = lambda _prompt: True

        draw_card(game, p1)

        assert game.get_hand(p1).contains(drawn_instant)
        assert not game.stack.is_empty()

        game.stack.pop().on_resolve(game)

        miracle_spell = game.stack.peek()
        assert miracle_spell is not None
        assert miracle_spell.source is drawn_instant
        assert miracle_spell.total_mana_spent == 2
        assert not game.get_hand(p1).contains(drawn_instant)
        assert p1.mana_pool.total() == 0

        game.stack.pop().on_resolve(game)

        assert drawn_instant.was_resolved is True
        assert p1.life == 23
        assert game.get_graveyard(p1).contains(drawn_instant)

    def test_first_drawn_sorcery_can_be_cast_for_miracle_two_outside_normal_timing(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_sorcery = _MiracleTestSorcery(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            hand=[],
            mana={ManaType.COLORLESS: 2},
        )
        _put_library_bottom_to_top(game, p1, [drawn_sorcery])
        lorehold.register_triggers(game)
        p1.cards_drawn_this_turn = 0
        p1.choose_yes_no = lambda _prompt: True
        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP

        draw_card(game, p1)
        game.stack.pop().on_resolve(game)

        miracle_spell = game.stack.peek()
        assert miracle_spell is not None
        assert miracle_spell.source is drawn_sorcery
        assert miracle_spell.total_mana_spent == 2
        assert not game.get_hand(p1).contains(drawn_sorcery)

        game.stack.pop().on_resolve(game)

        assert drawn_sorcery.was_resolved is True
        assert p1.life == 24
        assert game.get_graveyard(p1).contains(drawn_sorcery)
        assert p2.life == 20

    def test_second_card_drawn_this_turn_does_not_get_miracle(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_instant = _MiracleTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            hand=[],
            mana={ManaType.COLORLESS: 2},
        )
        _put_library_bottom_to_top(game, p1, [drawn_instant])
        lorehold.register_triggers(game)
        p1.cards_drawn_this_turn = 1

        draw_card(game, p1)

        assert game.stack.is_empty()
        assert game.get_hand(p1).contains(drawn_instant)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2

    def test_first_drawn_nonspell_card_does_not_get_miracle(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_creature = _test_creature("History Bear")

        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            hand=[],
            mana={ManaType.COLORLESS: 2},
        )
        _put_library_bottom_to_top(game, p1, [drawn_creature])
        lorehold.register_triggers(game)
        p1.cards_drawn_this_turn = 0

        draw_card(game, p1)

        assert game.stack.is_empty()
        assert game.get_hand(p1).contains(drawn_creature)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2

    def test_you_may_decline_to_cast_the_miracle_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_instant = _MiracleTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            hand=[],
            mana={ManaType.COLORLESS: 2},
        )
        _put_library_bottom_to_top(game, p1, [drawn_instant])
        lorehold.register_triggers(game)
        p1.cards_drawn_this_turn = 0
        p1.choose_yes_no = lambda _prompt: False

        draw_card(game, p1)
        game.stack.pop().on_resolve(game)

        assert game.stack.is_empty()
        assert game.get_hand(p1).contains(drawn_instant)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2
        assert not game.get_graveyard(p1).contains(drawn_instant)
