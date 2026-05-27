"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.game import draw_card
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.types import CardType, Color, Keyword, ManaCost, ManaType, Supertype
from test_utils import create_game, set_board_state


class TestLoreholdTheHistorianProperties:
    """Static characteristics from the card spec."""

    def test_is_a_legendary_elder_dragon_creature_with_specified_stats(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert isinstance(card, Creature)
        assert card.name == "Lorehold, the Historian"
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying_and_haste(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords

    def test_is_red_and_white(self) -> None:
        assert LoreholdTheHistorian(owner=None).colors == {Color.RED, Color.WHITE}


class TestLoreholdTheHistorianUpkeepTrigger:
    """Triggered discard-then-draw ability during opponents' upkeeps."""

    @staticmethod
    def _fire_upkeep(game) -> None:
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

    def test_registers_one_beginning_of_upkeep_trigger(self) -> None:
        game = create_game()
        card = LoreholdTheHistorian(owner=None)

        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is BeginningOfUpkeepTriggeredEvent

    def test_does_not_trigger_on_your_own_upkeep(self) -> None:
        game = create_game()
        card = LoreholdTheHistorian(owner=None)

        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        card.register_triggers(game)

        self._fire_upkeep(game)

        assert game.stack.is_empty()

    def test_opponent_upkeep_allows_you_to_decline_discarding(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=None)
        kept = Creature(name="Kept Card", base_power=2, base_toughness=2)
        drawn = Creature(name="Drawn Card", base_power=1, base_toughness=1)

        set_board_state(game, 0, battlefield=[card], hand=[kept])
        game.get_library(p1).add(drawn)
        game.active_player_index = 1
        p1.choose_yes_no = lambda _prompt: False

        card.register_triggers(game)
        self._fire_upkeep(game)

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert game.get_hand(p1).contains(kept)
        assert not game.get_hand(p1).contains(drawn)
        assert game.get_library(p1).contains(drawn)
        assert game.get_graveyard(p1).get_all() == []

    def test_opponent_upkeep_discards_chosen_card_then_draws_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=None)
        discard_me = Creature(name="Discard Me", base_power=2, base_toughness=2)
        keep_me = Creature(name="Keep Me", base_power=2, base_toughness=2)
        drawn = Creature(name="Drawn Card", base_power=1, base_toughness=1)

        set_board_state(game, 0, battlefield=[card], hand=[discard_me, keep_me])
        game.get_library(p1).add(drawn)
        game.active_player_index = 1
        p1.choose_yes_no = lambda _prompt: True
        p1.choose_card = lambda cards, _description: discard_me

        card.register_triggers(game)
        self._fire_upkeep(game)

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert game.get_graveyard(p1).contains(discard_me)
        assert not game.get_hand(p1).contains(discard_me)
        assert game.get_hand(p1).contains(keep_me)
        assert game.get_hand(p1).contains(drawn)
        assert not game.get_library(p1).contains(drawn)

    def test_opponent_upkeep_with_empty_hand_does_not_draw_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=None)
        drawn = Creature(name="Drawn Card", base_power=1, base_toughness=1)

        set_board_state(game, 0, battlefield=[card], hand=[])
        game.get_library(p1).add(drawn)
        game.active_player_index = 1
        p1.choose_yes_no = lambda _prompt: True

        card.register_triggers(game)
        self._fire_upkeep(game)

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert game.get_hand(p1).get_all() == []
        assert game.get_graveyard(p1).get_all() == []
        assert game.get_library(p1).contains(drawn)
        assert not hasattr(p1, "cards_drawn_this_turn") or p1.cards_drawn_this_turn == 0


class TestLoreholdTheHistorianMiracle:
    """Granted miracle {2} for instant and sorcery cards in hand."""

    def test_grants_miracle_two_to_your_instant_and_sorcery_cards_in_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=None)
        instant = Instant(name="Big Instant", mana_cost=ManaCost.parse("{4}{R}"))
        sorcery = Sorcery(name="Big Sorcery", mana_cost=ManaCost.parse("{5}{W}"))

        set_board_state(game, 0, battlefield=[lorehold], hand=[instant, sorcery])

        assert instant.has_miracle(game, p1) is True
        assert sorcery.has_miracle(game, p1) is True
        assert instant.get_miracle_cost(game, p1) == ManaCost.parse("{2}")
        assert sorcery.get_miracle_cost(game, p1) == ManaCost.parse("{2}")

    def test_does_not_grant_miracle_to_nonspells_or_opponents_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=None)
        creature = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        opposing_instant = Instant(name="Opponent Spell", mana_cost=ManaCost.parse("{3}{U}"))

        set_board_state(game, 0, battlefield=[lorehold], hand=[creature])
        set_board_state(game, 1, hand=[opposing_instant])

        assert creature.has_miracle(game, p1) is False
        assert creature.get_miracle_cost(game, p1) is None
        assert opposing_instant.has_miracle(game, p2) is False
        assert opposing_instant.get_miracle_cost(game, p2) is None

    def test_first_card_drawn_this_turn_opens_a_miracle_window_at_two_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=None)
        drawn_spell = Instant(name="Drawn Spell", mana_cost=ManaCost.parse("{4}{R}"))

        set_board_state(game, 0, battlefield=[lorehold], hand=[])
        game.get_library(p1).add(drawn_spell)

        drawn = draw_card(game, p1)
        window = game.get_miracle_window(player=p1, card=drawn_spell)

        assert drawn is drawn_spell
        assert window is not None
        assert window.card is drawn_spell
        assert window.player is p1
        assert window.cost == ManaCost.parse("{2}")
        assert window.turn_number == game.turn_number

    def test_second_card_drawn_this_turn_does_not_open_a_miracle_window(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=None)
        first_draw = Creature(name="Drawn Creature", base_power=1, base_toughness=1)
        second_draw = Instant(name="Second Draw", mana_cost=ManaCost.parse("{4}{R}"))

        set_board_state(game, 0, battlefield=[lorehold], hand=[])
        game.get_library(p1).add(second_draw)
        game.get_library(p1).add(first_draw)

        assert draw_card(game, p1) is first_draw
        assert draw_card(game, p1) is second_draw
        assert game.has_miracle_window(player=p1, card=second_draw) is False

    def test_can_cast_first_drawn_sorcery_via_miracle_for_two_outside_normal_timing(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=None)
        drawn_sorcery = Sorcery(name="Huge Lesson", mana_cost=ManaCost.parse("{5}{R}"))

        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            hand=[],
            mana={ManaType.COLORLESS: 2},
        )
        game.get_library(p1).add(drawn_sorcery)
        game.active_player_index = 1

        assert draw_card(game, p1) is drawn_sorcery
        assert game.has_miracle_window(player=p1, card=drawn_sorcery) is True

        game.cast_spell_via_miracle(p1, drawn_sorcery)

        stack_obj = game.stack.peek()
        assert stack_obj is not None
        assert stack_obj.source is drawn_sorcery
        assert game.get_hand(p1).contains(drawn_sorcery) is False
        assert p1.mana_pool.total() == 0

        resolved = game.stack.pop()
        resolved.on_resolve(game)

        assert game.get_graveyard(p1).contains(drawn_sorcery)
        assert game.has_miracle_window(player=p1, card=drawn_sorcery) is False
