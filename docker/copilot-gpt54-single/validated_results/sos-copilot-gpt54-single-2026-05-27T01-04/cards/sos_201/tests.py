"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state


def _set_library(player, cards_bottom_to_top: list) -> None:
    """Replace *player*'s library with the provided bottom-to-top order."""
    library = player.zones[Zone.LIBRARY]
    for card in library.get_all():
        library.remove(card)
    for card in cards_bottom_to_top:
        card.owner = player
        card.controller = player
        library.add(card)


class TestLoreholdTheHistorianProperties:
    """Static card data should match the SOS 201 spec."""

    def test_is_a_legendary_elder_dragon_creature_named_lorehold_the_historian(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert isinstance(card, Creature)
        assert card.name == "Lorehold, the Historian"
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_has_expected_mana_cost_keywords_stats_and_rules_text(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords
        assert card.base_power == 5
        assert card.base_toughness == 5
        assert card.rules_text == (
            "Flying, haste\n"
            "Each instant and sorcery card in your hand has miracle {2}. "
            "(You may cast a card for its miracle cost when you draw it if "
            "it's the first card you drew this turn.)\n"
            "At the beginning of each opponent's upkeep, you may discard a "
            "card. If you do, draw a card."
        )


class TestLoreholdTheHistorianMiracle:
    """Lorehold should grant and enable miracle {2} for your spells in hand."""

    def test_grants_miracle_two_to_your_instants_and_sorceries_in_hand_only(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        your_instant = Instant(name="Your Instant", mana_cost=ManaCost.parse("{R}"))
        your_sorcery = Sorcery(name="Your Sorcery", mana_cost=ManaCost.parse("{2}{W}"))
        your_creature = Creature(
            name="Your Creature",
            mana_cost=ManaCost.parse("{1}{G}"),
            base_power=2,
            base_toughness=2,
        )
        opposing_instant = Instant(name="Opposing Instant", mana_cost=ManaCost.parse("{U}"))

        set_board_state(game, 0, battlefield=[lorehold], hand=[your_instant, your_sorcery, your_creature])
        set_board_state(game, 1, hand=[opposing_instant])

        assert your_instant.get_miracle_cost(game, p1) == ManaCost.parse("{2}")
        assert your_sorcery.get_miracle_cost(game, p1) == ManaCost.parse("{2}")
        assert your_creature.get_miracle_cost(game, p1) is None
        assert opposing_instant.get_miracle_cost(game, p2) is None

    def test_first_instant_drawn_this_turn_opens_a_miracle_window(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn = Instant(name="Drawn Instant", mana_cost=ManaCost.parse("{1}{R}"))

        set_board_state(game, 0, battlefield=[lorehold])
        _set_library(p1, [drawn])
        game.phase = Phase.BEGINNING
        game.step = Step.DRAW

        result = draw_card(game, p1)

        assert result is drawn
        assert p1.zones[Zone.HAND].contains(drawn)
        assert game.get_miracle_window(p1) is drawn
        assert drawn.get_miracle_cost(game, p1) == ManaCost.parse("{2}")
        assert drawn.is_miracle_available(game, p1) is True

    def test_second_card_drawn_this_turn_does_not_open_a_miracle_window(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        first_drawn = Creature(
            name="First Drawn Creature",
            mana_cost=ManaCost.parse("{1}{G}"),
            base_power=2,
            base_toughness=2,
        )
        second_drawn = Instant(name="Second Drawn Instant", mana_cost=ManaCost.parse("{R}"))

        set_board_state(game, 0, battlefield=[lorehold])
        _set_library(p1, [second_drawn, first_drawn])

        assert draw_card(game, p1) is first_drawn
        assert draw_card(game, p1) is second_drawn
        assert game.get_miracle_window(p1) is None
        assert second_drawn.is_miracle_available(game, p1) is False

    def test_revealed_first_drawn_sorcery_can_be_cast_for_miracle_during_draw_step(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn = Sorcery(name="Drawn Sorcery", mana_cost=ManaCost.parse("{5}{R}"))

        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            mana={ManaType.COLORLESS: 2},
        )
        _set_library(p1, [drawn])
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.BEGINNING
        game.step = Step.DRAW

        assert draw_card(game, p1) is drawn
        assert drawn.reveal_for_miracle(game, p1) is True

        stack_obj = drawn.cast_for_miracle(game, p1)

        assert stack_obj.source is drawn
        assert stack_obj.alternate_cost == ManaCost.parse("{2}")
        assert game.stack.peek() is stack_obj
        assert not p1.zones[Zone.HAND].contains(drawn)
        assert p1.zones[Zone.STACK].contains(drawn)
        assert game.get_miracle_window(p1) is None
        assert drawn.can_cast_for_miracle(game, p1) is False


class TestLoreholdTheHistorianUpkeepTrigger:
    """Its upkeep ability should loot on each opponent's upkeep only."""

    def test_registers_one_beginning_of_upkeep_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)

        assert len(triggers) == 1
        assert triggers[0].event_type is BeginningOfUpkeepTriggeredEvent
        assert triggers[0].controller is p1

    def test_does_not_trigger_during_your_own_upkeep(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        game.priority_player_index = 0
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert game.stack.is_empty()

    def test_opponents_upkeep_trigger_can_be_declined_without_discarding_or_drawing(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        keep = Instant(name="Keep", mana_cost=ManaCost.parse("{R}"))
        would_draw = Sorcery(name="Would Draw", mana_cost=ManaCost.parse("{1}{W}"))

        p1.choose_yes_no = lambda _prompt: False  # type: ignore[method-assign]
        _set_library(p1, [would_draw])
        set_board_state(game, 0, battlefield=[card], hand=[keep])
        game.active_player_index = 1
        game.priority_player_index = 1
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert len(game.stack) == 1
        game.stack.pop().on_resolve(game)

        assert p1.zones[Zone.HAND].contains(keep)
        assert not p1.zones[Zone.GRAVEYARD].contains(keep)
        assert p1.zones[Zone.LIBRARY].contains(would_draw)
        assert not p1.zones[Zone.HAND].contains(would_draw)

    def test_opponents_upkeep_discard_moves_chosen_card_to_graveyard_then_draws_a_replacement(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        discard_me = Instant(name="Discard Me", mana_cost=ManaCost.parse("{R}"))
        keep_me = Sorcery(name="Keep Me", mana_cost=ManaCost.parse("{1}{W}"))
        drawn = Instant(name="Drawn Card", mana_cost=ManaCost.parse("{W}"))

        p1.choose_yes_no = lambda _prompt: True  # type: ignore[method-assign]
        p1.choose_card = lambda cards, _description="": discard_me  # type: ignore[method-assign]
        _set_library(p1, [drawn])
        set_board_state(game, 0, battlefield=[card], hand=[discard_me, keep_me])
        game.active_player_index = 1
        game.priority_player_index = 1
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert len(game.stack) == 1
        game.stack.pop().on_resolve(game)

        assert p1.zones[Zone.GRAVEYARD].contains(discard_me)
        assert not p1.zones[Zone.HAND].contains(discard_me)
        assert p1.zones[Zone.HAND].contains(keep_me)
        assert p1.zones[Zone.HAND].contains(drawn)
        assert len(p1.zones[Zone.HAND]) == 2
        assert len(p1.zones[Zone.LIBRARY]) == 0

    def test_opponents_upkeep_with_empty_hand_cannot_discard_and_does_not_draw(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        would_draw = Instant(name="Would Draw", mana_cost=ManaCost.parse("{W}"))

        _set_library(p1, [would_draw])
        set_board_state(game, 0, battlefield=[card], hand=[])
        game.active_player_index = 1
        game.priority_player_index = 1
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert len(game.stack) == 1
        game.stack.pop().on_resolve(game)

        assert len(p1.zones[Zone.HAND]) == 0
        assert len(p1.zones[Zone.GRAVEYARD]) == 0
        assert p1.zones[Zone.LIBRARY].contains(would_draw)
