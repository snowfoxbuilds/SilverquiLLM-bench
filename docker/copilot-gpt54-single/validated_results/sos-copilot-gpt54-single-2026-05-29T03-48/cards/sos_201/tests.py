"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.casting import resolve_top
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import Keyword, ManaCost, ManaType, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state


def _set_upkeep(game, active_player_index: int) -> None:
    game.active_player_index = active_player_index
    game.priority_player_index = active_player_index
    game.phase = Phase.BEGINNING
    game.step = Step.UPKEEP


def _put_on_top_of_library(player, card) -> None:
    card.owner = player
    card.controller = player
    player.zones[Zone.LIBRARY].add(card)


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        resolve_top(game)


class TestLoreholdTheHistorianProperties:
    """Static card data should match the SOS 201 spec."""

    def test_is_legendary_elder_dragon_creature(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_name(self) -> None:
        assert LoreholdTheHistorian(owner=None).name == "Lorehold, the Historian"

    def test_mana_cost(self) -> None:
        assert LoreholdTheHistorian(owner=None).mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_power_and_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying_and_haste(self) -> None:
        keywords = LoreholdTheHistorian(owner=None).keywords
        assert Keyword.FLYING in keywords
        assert Keyword.HASTE in keywords


class TestLoreholdTheHistorianOpponentUpkeepTrigger:
    """The upkeep ability should only matter on opponents' upkeeps."""

    def test_registers_a_beginning_of_upkeep_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert any(t.event_type is BeginningOfUpkeepTriggeredEvent for t in triggers)

    def test_does_not_trigger_on_its_controllers_upkeep(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        _set_upkeep(game, 0)

        card.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert game.stack.is_empty()

    def test_opponents_upkeep_may_be_declined(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        discard_fodder = Instant(name="Spare Note", mana_cost=ManaCost.parse("{U}"))
        drawn_card = Instant(name="Future Note", mana_cost=ManaCost.parse("{U}"))

        set_board_state(game, 0, battlefield=[card], hand=[discard_fodder])
        _put_on_top_of_library(p1, drawn_card)
        _set_upkeep(game, 1)

        def _unexpected_choose_card(_cards, _description: str):
            raise AssertionError("should not choose a discard when the ability is declined")

        p1.choose_yes_no = lambda _prompt: False  # type: ignore[method-assign]
        p1.choose_card = _unexpected_choose_card  # type: ignore[method-assign]

        card.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_all(game)

        assert game.get_hand(p1).contains(discard_fodder)
        assert not game.get_hand(p1).contains(drawn_card)
        assert p1.zones[Zone.LIBRARY].contains(drawn_card)
        assert not game.get_graveyard(p1).contains(discard_fodder)

    def test_opponents_upkeep_discards_chosen_card_then_draws(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        discard_fodder = Sorcery(name="Old Lesson", mana_cost=ManaCost.parse("{3}{R}"))
        drawn_card = Instant(name="Fresh Lesson", mana_cost=ManaCost.parse("{U}"))

        set_board_state(game, 0, battlefield=[card], hand=[discard_fodder])
        _put_on_top_of_library(p1, drawn_card)
        _set_upkeep(game, 1)

        p1.choose_yes_no = lambda _prompt: True  # type: ignore[method-assign]
        p1.choose_card = lambda cards, _description: discard_fodder  # type: ignore[method-assign]

        card.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_all(game)

        assert game.get_graveyard(p1).contains(discard_fodder)
        assert not game.get_hand(p1).contains(discard_fodder)
        assert game.get_hand(p1).contains(drawn_card)
        assert not p1.zones[Zone.LIBRARY].contains(drawn_card)

    def test_opponents_upkeep_with_empty_hand_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        top_card = Instant(name="Untouched Card", mana_cost=ManaCost.parse("{U}"))

        set_board_state(game, 0, battlefield=[card], hand=[])
        _put_on_top_of_library(p1, top_card)
        _set_upkeep(game, 1)

        def _unexpected_yes_no(_prompt: str) -> bool:
            raise AssertionError("should not offer discard when hand is empty")

        def _unexpected_choose_card(_cards, _description: str):
            raise AssertionError("should not ask for a discard choice when hand is empty")

        p1.choose_yes_no = _unexpected_yes_no  # type: ignore[method-assign]
        p1.choose_card = _unexpected_choose_card  # type: ignore[method-assign]

        card.register_triggers(game)
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_all(game)

        assert len(game.get_hand(p1).get_all()) == 0
        assert p1.zones[Zone.LIBRARY].contains(top_card)


class TestLoreholdTheHistorianMiracle:
    """Lorehold should grant miracle {2} to instant and sorcery cards you draw."""

    def test_first_drawn_sorcery_may_be_cast_for_two_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_spell = Sorcery(name="Expensive Lesson", mana_cost=ManaCost.parse("{6}{R}"))

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[],
            mana={ManaType.COLORLESS: 2},
        )
        _put_on_top_of_library(p1, drawn_spell)
        _set_upkeep(game, 1)

        p1.choose_yes_no = lambda _prompt: True  # type: ignore[method-assign]

        card.register_triggers(game)
        draw_card(game, p1)
        _resolve_all(game)

        assert p1.mana_pool.total() == 0
        assert game.get_graveyard(p1).contains(drawn_spell)
        assert not game.get_hand(p1).contains(drawn_spell)

    def test_miracle_cast_may_be_declined(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_spell = Sorcery(name="Held Lesson", mana_cost=ManaCost.parse("{5}{R}"))

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[],
            mana={ManaType.COLORLESS: 2},
        )
        _put_on_top_of_library(p1, drawn_spell)
        _set_upkeep(game, 1)

        p1.choose_yes_no = lambda _prompt: False  # type: ignore[method-assign]

        card.register_triggers(game)
        draw_card(game, p1)
        _resolve_all(game)

        assert p1.mana_pool.total() == 2
        assert game.get_hand(p1).contains(drawn_spell)
        assert not game.get_graveyard(p1).contains(drawn_spell)

    def test_second_card_drawn_this_turn_is_not_offered_for_miracle(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        first_draw = Creature(name="Campus Visitor", base_power=2, base_toughness=2)
        second_draw = Sorcery(name="Late Lesson", mana_cost=ManaCost.parse("{4}{R}"))

        set_board_state(game, 0, battlefield=[card], hand=[], mana={ManaType.COLORLESS: 2})
        _put_on_top_of_library(p1, second_draw)
        _put_on_top_of_library(p1, first_draw)
        _set_upkeep(game, 1)

        def _unexpected_yes_no(_prompt: str) -> bool:
            raise AssertionError("should not offer miracle for the second card drawn this turn")

        p1.choose_yes_no = _unexpected_yes_no  # type: ignore[method-assign]

        card.register_triggers(game)
        draw_card(game, p1)
        assert game.stack.is_empty()

        draw_card(game, p1)
        assert game.stack.is_empty()
        assert game.get_hand(p1).contains(second_draw)
        assert p1.mana_pool.total() == 2

    def test_first_drawn_creature_has_no_miracle_offer(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_creature = Creature(name="Ground Student", base_power=2, base_toughness=2)

        set_board_state(game, 0, battlefield=[card], hand=[], mana={ManaType.COLORLESS: 2})
        _put_on_top_of_library(p1, drawn_creature)
        _set_upkeep(game, 1)

        def _unexpected_yes_no(_prompt: str) -> bool:
            raise AssertionError("should not offer miracle for a creature card")

        p1.choose_yes_no = _unexpected_yes_no  # type: ignore[method-assign]

        card.register_triggers(game)
        draw_card(game, p1)

        assert game.stack.is_empty()
        assert game.get_hand(p1).contains(drawn_creature)
        assert p1.mana_pool.total() == 2
