"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

import pytest

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.casting import CastingError, cast_spell as engine_cast_spell
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import Keyword, ManaCost, ManaType, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state


class TestLoreholdTheHistorianProperties:
    """Static card data should match the card spec."""

    def test_is_a_creature(self) -> None:
        assert isinstance(LoreholdTheHistorian(owner=None), Creature)

    def test_name(self) -> None:
        assert LoreholdTheHistorian(owner=None).name == "Lorehold, the Historian"

    def test_mana_cost(self) -> None:
        assert LoreholdTheHistorian(owner=None).mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_is_a_legendary_elder_dragon(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes

    def test_power_and_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying_and_haste(self) -> None:
        keywords = LoreholdTheHistorian(owner=None).keywords
        assert Keyword.FLYING in keywords
        assert Keyword.HASTE in keywords


class TestLoreholdTheHistorianUpkeepTrigger:
    """At each opponent's upkeep, you may discard a card. If you do, draw a card."""

    @staticmethod
    def _put_on_battlefield_and_register(game, card) -> None:
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

    def test_registers_one_beginning_of_upkeep_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        self._put_on_battlefield_and_register(game, card)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is BeginningOfUpkeepTriggeredEvent

    def test_does_not_trigger_on_your_upkeep(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        self._put_on_battlefield_and_register(game, card)
        game.active_player_index = 0
        game.priority_player_index = 0
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert game.stack.is_empty()

    def test_does_not_trigger_if_it_is_not_on_the_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        set_board_state(game, 0, hand=[card])
        card.register_triggers(game)
        game.active_player_index = 1
        game.priority_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert game.stack.is_empty()

    def test_triggers_on_each_opponents_upkeep(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        self._put_on_battlefield_and_register(game, card)
        game.active_player_index = 1
        game.priority_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert len(game.stack) == 1
        assert game.stack.peek().source is card

    def test_may_decline_the_discard_and_draw(self) -> None:
        game = create_game()
        p1 = game.players[0]
        keep = Creature(name="Keep", base_power=2, base_toughness=2)
        draw_me = Creature(name="Draw Me", base_power=1, base_toughness=1)
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        self._put_on_battlefield_and_register(game, card)
        set_board_state(game, 0, hand=[keep])
        p1.zones[Zone.LIBRARY].add(draw_me)
        p1._script.append(False)
        game.active_player_index = 1
        game.priority_player_index = 1

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        game.stack.pop().on_resolve(game)

        assert game.get_hand(p1).contains(keep)
        assert game.get_hand(p1).contains(draw_me) is False
        assert len(game.get_graveyard(p1).get_all()) == 0
        assert p1.zones[Zone.LIBRARY].contains(draw_me)

    def test_empty_hand_means_you_do_not_draw(self) -> None:
        game = create_game()
        p1 = game.players[0]
        draw_me = Creature(name="Draw Me", base_power=1, base_toughness=1)
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        self._put_on_battlefield_and_register(game, card)
        set_board_state(game, 0, hand=[])
        p1.zones[Zone.LIBRARY].add(draw_me)
        p1._script.append(True)
        game.active_player_index = 1
        game.priority_player_index = 1

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        game.stack.pop().on_resolve(game)

        assert len(game.get_hand(p1).get_all()) == 0
        assert len(game.get_graveyard(p1).get_all()) == 0
        assert p1.zones[Zone.LIBRARY].contains(draw_me)

    def test_discarding_a_card_draws_a_replacement_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        discard_me = Creature(name="Discard Me", base_power=2, base_toughness=2)
        keep_me = Creature(name="Keep Me", base_power=2, base_toughness=2)
        draw_me = Creature(name="Draw Me", base_power=1, base_toughness=1)
        card = LoreholdTheHistorian(owner=p1, controller=p1)

        self._put_on_battlefield_and_register(game, card)
        set_board_state(game, 0, hand=[discard_me, keep_me])
        p1.zones[Zone.LIBRARY].add(draw_me)
        p1._script.append(True)
        p1._script.append(discard_me)
        game.active_player_index = 1
        game.priority_player_index = 1

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        game.stack.pop().on_resolve(game)

        assert game.get_graveyard(p1).contains(discard_me)
        assert game.get_hand(p1).contains(discard_me) is False
        assert game.get_hand(p1).contains(keep_me)
        assert game.get_hand(p1).contains(draw_me)
        assert p1.zones[Zone.LIBRARY].contains(draw_me) is False


class TestLoreholdTheHistorianMiracle:
    """Lorehold should grant miracle {2} to the first instant or sorcery you draw each turn."""

    @staticmethod
    def _draw_and_assert_in_hand(game, player, card) -> None:
        drawn = draw_card(game, player)
        assert drawn is card
        assert game.get_hand(player).contains(card)

    def test_first_drawn_instant_can_be_cast_for_two_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        spell = Instant(
            name="Expensive Insight",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{4}{U}"),
        )

        game.active_player_index = 1
        game.priority_player_index = 0
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP
        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            mana={ManaType.COLORLESS: 2},
        )
        p1.cards_drawn_this_turn = 0
        p1.zones[Zone.LIBRARY].add(spell)

        self._draw_and_assert_in_hand(game, p1, spell)
        engine_cast_spell(game, p1, spell)

        assert game.stack.peek().source is spell
        assert spell.actual_mana_spent == 2
        game.stack.pop().on_resolve(game)
        assert game.get_graveyard(p1).contains(spell)

    def test_first_drawn_sorcery_can_be_cast_via_miracle_during_opponents_upkeep(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        spell = Sorcery(
            name="History Lesson",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{4}{R}"),
        )

        game.active_player_index = 1
        game.priority_player_index = 0
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP
        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            mana={ManaType.COLORLESS: 2},
        )
        set_board_state(game, 1, battlefield=[Creature(name="Watcher", owner=p2, controller=p2)])
        p1.cards_drawn_this_turn = 0
        p1.zones[Zone.LIBRARY].add(spell)

        self._draw_and_assert_in_hand(game, p1, spell)
        engine_cast_spell(game, p1, spell)

        assert game.stack.peek().source is spell
        assert spell.actual_mana_spent == 2

    def test_second_card_drawn_this_turn_does_not_get_miracle(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        spell = Sorcery(
            name="Late Lecture",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{4}{R}"),
        )

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            mana={ManaType.COLORLESS: 2},
        )
        p1.cards_drawn_this_turn = 1
        p1.zones[Zone.LIBRARY].add(spell)

        self._draw_and_assert_in_hand(game, p1, spell)

        with pytest.raises(CastingError, match="insufficient mana"):
            engine_cast_spell(game, p1, spell)

    def test_first_drawn_creature_does_not_get_miracle(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        creature = Creature(
            name="Student Archaeologist",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{4}{W}"),
            base_power=3,
            base_toughness=3,
        )

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            mana={ManaType.COLORLESS: 2},
        )
        p1.cards_drawn_this_turn = 0
        p1.zones[Zone.LIBRARY].add(creature)

        self._draw_and_assert_in_hand(game, p1, creature)

        with pytest.raises(CastingError, match="insufficient mana"):
            engine_cast_spell(game, p1, creature)

    def test_lorehold_must_be_on_the_battlefield_to_grant_miracle(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        spell = Instant(
            name="Archive Spark",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{4}{U}"),
        )

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            hand=[lorehold],
            mana={ManaType.COLORLESS: 2},
        )
        p1.cards_drawn_this_turn = 0
        p1.zones[Zone.LIBRARY].add(spell)

        self._draw_and_assert_in_hand(game, p1, spell)

        with pytest.raises(CastingError, match="insufficient mana"):
            engine_cast_spell(game, p1, spell)

    def test_opponents_first_drawn_spell_does_not_get_miracle(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        spell = Instant(
            name="Borrowed Notes",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{4}{U}"),
        )

        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(game, 0, battlefield=[lorehold])
        set_board_state(
            game,
            1,
            mana={ManaType.COLORLESS: 2},
        )
        p2.cards_drawn_this_turn = 0
        p2.zones[Zone.LIBRARY].add(spell)

        self._draw_and_assert_in_hand(game, p2, spell)

        with pytest.raises(CastingError, match="insufficient mana"):
            engine_cast_spell(game, p2, spell)
