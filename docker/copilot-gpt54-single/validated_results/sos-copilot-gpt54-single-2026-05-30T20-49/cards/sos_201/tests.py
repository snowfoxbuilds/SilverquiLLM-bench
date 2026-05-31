"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from engine.zones import move_to_zone
from test_utils import create_game, set_board_state


def _fire_upkeep(game, active_player_index: int) -> None:
    game.active_player_index = active_player_index
    game.priority_player_index = active_player_index
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())


def _resolve_single_trigger(game, source) -> None:
    assert len(game.stack) == 1
    trigger_obj = game.stack.pop()
    assert trigger_obj.source is source
    trigger_obj.on_resolve(game)


class TestLoreholdTheHistorianProperties:
    """Static characteristics should match the card spec."""

    def test_is_a_legendary_five_five_elder_dragon_with_flying_and_haste(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert isinstance(card, Creature)
        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes
        assert card.base_power == 5
        assert card.base_toughness == 5
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords


class TestLoreholdTheHistorianUpkeepTrigger:
    """The upkeep trigger should loot only on opponents' upkeeps."""

    def test_registers_a_beginning_of_opponents_upkeep_trigger(self) -> None:
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
        card.register_triggers(game)
        assert len(game.trigger_manager.get_triggers_for_source(card)) == 1

        _fire_upkeep(game, 0)

        assert len(game.stack) == 0

    def test_opponents_upkeep_trigger_can_be_declined(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        held_card = Instant(name="Old Lesson", owner=p1, controller=p1)
        drawn_card = Instant(name="Fresh Lesson", owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], hand=[held_card])
        game.get_library(p1).add(drawn_card)
        card.register_triggers(game)

        p1.choose_yes_no = lambda prompt: False

        _fire_upkeep(game, 1)
        _resolve_single_trigger(game, card)

        assert game.get_hand(p1).contains(held_card)
        assert not game.get_hand(p1).contains(drawn_card)
        assert game.get_library(p1).contains(drawn_card)
        assert not game.get_graveyard(p1).contains(held_card)

    def test_opponents_upkeep_trigger_discards_a_card_then_draws_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        discarded_card = Instant(name="Spent Lesson", owner=p1, controller=p1)
        drawn_card = Instant(name="New Lesson", owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], hand=[discarded_card])
        game.get_library(p1).add(drawn_card)
        card.register_triggers(game)

        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: discarded_card

        _fire_upkeep(game, 1)
        _resolve_single_trigger(game, card)

        assert not game.get_hand(p1).contains(discarded_card)
        assert game.get_graveyard(p1).contains(discarded_card)
        assert game.get_hand(p1).contains(drawn_card)
        assert not game.get_library(p1).contains(drawn_card)

    def test_opponents_upkeep_trigger_with_no_card_in_hand_does_not_draw(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn_card = Instant(name="Unreachable Lesson", owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], hand=[])
        game.get_library(p1).add(drawn_card)
        card.register_triggers(game)

        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: None

        _fire_upkeep(game, 1)
        _resolve_single_trigger(game, card)

        assert not game.get_hand(p1).contains(drawn_card)
        assert game.get_library(p1).contains(drawn_card)
        assert len(game.get_graveyard(p1).get_all()) == 0


class TestLoreholdTheHistorianMiracle:
    """Lorehold should grant and enable miracle {2} for your hand's spells."""

    def test_grants_miracle_two_to_your_instants_and_sorceries_in_hand_only(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        your_instant = Instant(name="Your Instant", owner=p1, controller=p1)
        your_sorcery = Sorcery(
            name="Your Sorcery",
            owner=p1,
            controller=p1,
        )
        your_creature = Creature(name="Your Creature", owner=p1, controller=p1)
        opponent_instant = Instant(name="Opponent Instant", owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[card], hand=[your_instant, your_sorcery, your_creature])
        set_board_state(game, 1, hand=[opponent_instant])

        card.on_enters_battlefield(game)

        assert your_instant.get_granted_miracle_cost() == ManaCost.parse("{2}")
        assert your_sorcery.get_granted_miracle_cost() == ManaCost.parse("{2}")
        assert your_creature.get_granted_miracle_cost() is None
        assert opponent_instant.get_granted_miracle_cost() is None

    def test_leaving_battlefield_removes_granted_miracle_from_your_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        your_instant = Instant(name="Your Instant", owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], hand=[your_instant])
        card.on_enters_battlefield(game)

        assert your_instant.get_granted_miracle_cost() == ManaCost.parse("{2}")

        move_to_zone(game, card, Zone.BATTLEFIELD, Zone.GRAVEYARD)

        assert your_instant.get_granted_miracle_cost() is None

    def test_first_card_drawn_this_turn_can_be_cast_for_miracle_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        miracle_spell = Instant(
            name="Miraculous Lesson",
            mana_cost=ManaCost.parse("{7}"),
            owner=p1,
            controller=p1,
        )

        set_board_state(game, 0, battlefield=[card], hand=[])
        card.on_enters_battlefield(game)
        game.get_library(p1).add(miracle_spell)
        p1.choose_yes_no = lambda prompt: True
        p1.mana_pool.add(ManaType.COLORLESS, 2)

        drawn = draw_card(game, p1)

        assert drawn is miracle_spell
        assert not game.get_hand(p1).contains(miracle_spell)
        assert len(game.stack) == 1
        assert miracle_spell.cast_reason == "miracle"
        assert miracle_spell.mana_spent == 2

        game.stack.pop().on_resolve(game)

        assert game.get_graveyard(p1).contains(miracle_spell)

    def test_second_card_drawn_this_turn_cannot_be_cast_for_miracle(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        first_draw = Creature(name="First Draw", owner=p1, controller=p1)
        second_draw = Instant(
            name="Second Draw",
            mana_cost=ManaCost.parse("{7}"),
            owner=p1,
            controller=p1,
        )

        set_board_state(game, 0, battlefield=[card], hand=[])
        card.on_enters_battlefield(game)
        game.get_library(p1).add(second_draw)
        game.get_library(p1).add(first_draw)
        p1.choose_yes_no = lambda prompt: True
        p1.mana_pool.add(ManaType.COLORLESS, 4)

        draw_card(game, p1)
        drawn = draw_card(game, p1)

        assert drawn is second_draw
        assert game.get_hand(p1).contains(second_draw)
        assert len(game.stack) == 0
        assert game.is_first_card_drawn_this_turn(p1, second_draw) is False
        assert second_draw.get_granted_miracle_cost() == ManaCost.parse("{2}")
