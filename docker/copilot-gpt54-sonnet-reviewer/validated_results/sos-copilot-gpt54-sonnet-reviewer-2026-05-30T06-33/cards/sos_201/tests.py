"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

import pytest

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import CardImpl, Creature, Instant, Sorcery
from engine.casting import CastingError, cast_spell_with_miracle
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state

ORACLE_TEXT = (
    "Flying, haste\n"
    "Each instant and sorcery card in your hand has miracle {2}. "
    "(You may cast a card for its miracle cost when you draw it if it's "
    "the first card you drew this turn.)\n"
    "At the beginning of each opponent's upkeep, you may discard a card. "
    "If you do, draw a card."
)


def _resolve_top_of_stack(game) -> None:
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

    def test_name_mana_cost_rules_text_and_power_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert card.rules_text == ORACLE_TEXT
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying_and_haste(self) -> None:
        keywords = LoreholdTheHistorian(owner=None).keywords

        assert Keyword.FLYING in keywords
        assert Keyword.HASTE in keywords


class TestLoreholdTheHistorianUpkeepTrigger:
    """The upkeep trigger should let you loot on each opponent's upkeep."""

    def test_registers_one_beginning_of_upkeep_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is BeginningOfUpkeepTriggeredEvent
        assert triggers[0].controller is p1

    def test_trigger_does_not_fire_on_your_own_upkeep(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        assert len(game.trigger_manager.get_triggers_for_source(card)) == 1
        game.active_player_index = 0

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert game.stack.is_empty()

    def test_opponents_upkeep_trigger_may_be_declined(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        kept = CardImpl(name="Kept Lesson")
        draw_step = CardImpl(name="Future Draw")
        draw_step.owner = p1
        draw_step.controller = p1
        p1.zones[Zone.LIBRARY].add(draw_step)

        set_board_state(game, 0, battlefield=[card], hand=[kept])
        card.register_triggers(game)
        game.active_player_index = 1
        p1.choose_yes_no = lambda prompt: False

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert len(game.stack) == 1

        _resolve_top_of_stack(game)

        assert p1.zones[Zone.HAND].contains(kept)
        assert not p1.zones[Zone.HAND].contains(draw_step)
        assert p1.zones[Zone.LIBRARY].contains(draw_step)
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == 0

    def test_opponents_upkeep_discard_then_draws_one_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        discard_me = CardImpl(name="Past Lecture")
        drawn = CardImpl(name="New Lecture")
        drawn.owner = p1
        drawn.controller = p1
        p1.zones[Zone.LIBRARY].add(drawn)

        set_board_state(game, 0, battlefield=[card], hand=[discard_me])
        card.register_triggers(game)
        game.active_player_index = 1
        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: discard_me

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert len(game.stack) == 1

        _resolve_top_of_stack(game)

        assert not p1.zones[Zone.HAND].contains(discard_me)
        assert p1.zones[Zone.GRAVEYARD].contains(discard_me)
        assert p1.zones[Zone.HAND].contains(drawn)
        assert not p1.zones[Zone.LIBRARY].contains(drawn)

    def test_opponents_upkeep_with_empty_hand_cannot_turn_into_a_free_draw(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        library_card = CardImpl(name="Unread Thesis")
        library_card.owner = p1
        library_card.controller = p1
        p1.zones[Zone.LIBRARY].add(library_card)

        set_board_state(game, 0, battlefield=[card], hand=[])
        card.register_triggers(game)
        game.active_player_index = 1
        p1.choose_yes_no = lambda prompt: True

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert len(game.stack) == 1

        _resolve_top_of_stack(game)

        assert len(p1.zones[Zone.HAND].get_all()) == 0
        assert p1.zones[Zone.LIBRARY].contains(library_card)
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == 0


class TestLoreholdTheHistorianMiracle:
    """Lorehold should grant and enable miracle for drawn instants and sorceries."""

    def test_first_drawn_instant_in_your_hand_gets_miracle_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn = Instant(name="Sudden Insight", mana_cost=ManaCost.parse("{4}{U}"))

        set_board_state(game, 0, battlefield=[lorehold])
        game.phase = Phase.BEGINNING
        game.step = Step.DRAW
        p1.zones[Zone.LIBRARY].add(drawn)

        assert draw_card(game, p1) is drawn
        assert p1.zones[Zone.HAND].contains(drawn)
        assert drawn.granted_miracle_cost == ManaCost.parse("{2}")
        assert drawn.miracle_available is True

    def test_first_drawn_sorcery_in_your_hand_gets_miracle_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn = Sorcery(name="Ancient Lecture", mana_cost=ManaCost.parse("{5}{R}"))

        set_board_state(game, 0, battlefield=[lorehold])
        game.phase = Phase.BEGINNING
        game.step = Step.DRAW
        p1.zones[Zone.LIBRARY].add(drawn)

        assert draw_card(game, p1) is drawn
        assert p1.zones[Zone.HAND].contains(drawn)
        assert drawn.granted_miracle_cost == ManaCost.parse("{2}")
        assert drawn.miracle_available is True

    def test_second_card_drawn_this_turn_does_not_get_granted_miracle(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        first_draw = CardImpl(name="Regular Lesson")
        second_draw = Instant(name="Late Inspiration", mana_cost=ManaCost.parse("{3}{U}"))

        set_board_state(game, 0, battlefield=[lorehold])
        game.phase = Phase.BEGINNING
        game.step = Step.DRAW
        p1.zones[Zone.LIBRARY].add(second_draw, position="bottom")
        p1.zones[Zone.LIBRARY].add(first_draw)

        assert draw_card(game, p1) is first_draw
        assert draw_card(game, p1) is second_draw
        assert second_draw.granted_miracle_cost is None
        assert second_draw.miracle_available is False

    def test_opponents_drawn_instant_does_not_get_your_granted_miracle(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        opponents_draw = Instant(name="Foreign Research", mana_cost=ManaCost.parse("{3}{U}"))

        set_board_state(game, 0, battlefield=[lorehold])
        game.phase = Phase.BEGINNING
        game.step = Step.DRAW
        p2.zones[Zone.LIBRARY].add(opponents_draw)

        assert draw_card(game, p2) is opponents_draw
        assert opponents_draw.granted_miracle_cost is None
        assert opponents_draw.miracle_available is False

    def test_first_drawn_instant_can_be_cast_for_miracle_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn = Instant(name="Recovered Note", mana_cost=ManaCost.parse("{4}{U}"))

        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            mana={ManaType.COLORLESS: 2},
        )
        game.phase = Phase.BEGINNING
        game.step = Step.DRAW
        p1.zones[Zone.LIBRARY].add(drawn)

        assert draw_card(game, p1) is drawn

        cast_spell_with_miracle(game, p1, drawn)

        assert p1.zones[Zone.STACK].contains(drawn)
        assert drawn.mana_spent_total == 2
        assert not hasattr(drawn, "granted_miracle_cost")
        assert not hasattr(drawn, "miracle_available")

        _resolve_top_of_stack(game)

        assert p1.zones[Zone.GRAVEYARD].contains(drawn)

    def test_first_drawn_sorcery_can_be_cast_for_miracle_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn = Sorcery(name="Recovered Thesis", mana_cost=ManaCost.parse("{5}{R}"))

        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            mana={ManaType.COLORLESS: 2},
        )
        game.phase = Phase.BEGINNING
        game.step = Step.DRAW
        p1.zones[Zone.LIBRARY].add(drawn)

        assert draw_card(game, p1) is drawn

        cast_spell_with_miracle(game, p1, drawn)

        assert p1.zones[Zone.STACK].contains(drawn)
        assert drawn.mana_spent_total == 2

        _resolve_top_of_stack(game)

        assert p1.zones[Zone.GRAVEYARD].contains(drawn)

    def test_miracle_window_expires_after_draw_step(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        drawn = Sorcery(name="Missed Timing", mana_cost=ManaCost.parse("{5}{R}"))

        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            mana={ManaType.COLORLESS: 2},
        )
        game.phase = Phase.BEGINNING
        game.step = Step.DRAW
        p1.zones[Zone.LIBRARY].add(drawn)

        assert draw_card(game, p1) is drawn

        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        with pytest.raises(CastingError, match="miracle window has expired"):
            cast_spell_with_miracle(game, p1, drawn)
