"""Tests for Lorehold, the Historian (sos_201)."""

from __future__ import annotations

import pytest
from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


class TestLoreholdProperties:
    """Static card properties."""

    def test_name(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"

    def test_is_creature(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_power_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_mana_cost(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_has_flying(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.FLYING & card.keywords

    def test_has_haste(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Keyword.HASTE & card.keywords

    def test_is_legendary(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes


class TestLoreholdOpponentUpkeep:
    """At beginning of each opponent's upkeep, may discard → draw."""

    def _get_upkeep_trigger(self, game, card):
        from engine.events import BeginningOfUpkeepTriggeredEvent
        for t in game.trigger_manager.get_triggers_for_source(card):
            if t.event_type is BeginningOfUpkeepTriggeredEvent:
                return t
        return None

    def test_upkeep_trigger_registered(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)
        trigger = self._get_upkeep_trigger(game, card)
        assert trigger is not None

    def test_upkeep_condition_fires_during_opponent_upkeep(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        # Simulate opponent's upkeep (p2 is active)
        game.active_player_index = 1
        from engine.events import BeginningOfUpkeepTriggeredEvent
        trigger = self._get_upkeep_trigger(game, card)
        assert trigger is not None
        assert trigger.condition(game, None) is True

    def test_upkeep_condition_does_not_fire_own_upkeep(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        # p1 is active
        game.active_player_index = 0
        trigger = self._get_upkeep_trigger(game, card)
        assert trigger.condition(game, None) is False

    def test_discard_then_draw(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.active_player_index = 1  # Opponent's upkeep

        hand_card = Instant(name="DiscardMe", owner=p1, controller=p1)
        lib_card = Instant(name="DrawMe", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[hand_card])
        p1.zones[Zone.LIBRARY].add(lib_card, position="top")

        # Script: yes to discard, choose hand_card
        p1._script.append(True)       # yes, discard
        p1._script.append(hand_card)  # discard this

        trigger = self._get_upkeep_trigger(game, card)
        trigger.effect(game)

        assert hand_card in p1.zones[Zone.GRAVEYARD].get_all()
        assert lib_card in p1.zones[Zone.HAND].get_all()

    def test_decline_to_discard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        game.active_player_index = 1

        hand_card = Instant(name="KeepMe", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[hand_card])

        p1._script.append(False)  # no, don't discard

        trigger = self._get_upkeep_trigger(game, card)
        trigger.effect(game)

        assert hand_card in p1.zones[Zone.HAND].get_all()


class TestLoreholdMiracle:
    """Instants/sorceries in hand have miracle {2}."""

    def test_miracle_trigger_registered(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)

        from engine.events import DrawsCardTriggeredEvent
        triggers = [
            t for t in game.trigger_manager.get_triggers_for_source(card)
            if t.event_type is DrawsCardTriggeredEvent
        ]
        assert len(triggers) == 1

    def test_miracle_cast_on_first_draw(self) -> None:
        """When first card drawn is instant/sorcery, may cast for {2}."""
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        # Reset first-draw flag
        game._first_draw_done = False

        spell = Instant(name="Miracle Spell", owner=p1, controller=p1,
                         mana_cost=ManaCost.parse("{3}"))
        p1.zones[Zone.LIBRARY].add(spell, position="top")

        # Mana for miracle cost {2}
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})

        # Draw the card (tags it as first draw)
        from engine.game import draw_card
        drawn = draw_card(game, p1)
        assert drawn is spell
        assert getattr(spell, "_drawn_as_first_this_turn", False) is True

        # Find and fire the draw trigger
        from engine.events import DrawsCardTriggeredEvent
        draw_triggers = [
            t for t in game.trigger_manager.get_triggers_for_source(card)
            if t.event_type is DrawsCardTriggeredEvent
        ]
        assert draw_triggers

        # Script: yes to miracle cast
        p1._script.append(True)

        draw_triggers[0].effect(game)

        # Spell should be cast (on stack or resolved)
        hand = p1.zones[Zone.HAND].get_all()
        assert spell not in hand or game.stack.peek() is not None
