"""Tests for Lorehold, the Historian (sos_201)."""

from __future__ import annotations

import pytest

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


class TestLoreholdProperties:
    def test_name(self):
        card = LoreholdTheHistorian()
        assert card.name == "Lorehold, the Historian"

    def test_mana_cost_cmc(self):
        card = LoreholdTheHistorian()
        assert card.mana_cost.cmc == 5  # {3}{R}{W}

    def test_mana_cost_colors(self):
        card = LoreholdTheHistorian()
        assert card.mana_cost.pips.get(ManaType.RED, 0) == 1
        assert card.mana_cost.pips.get(ManaType.WHITE, 0) == 1
        assert card.mana_cost.generic == 3

    def test_base_power(self):
        card = LoreholdTheHistorian()
        assert card.base_power == 5

    def test_base_toughness(self):
        card = LoreholdTheHistorian()
        assert card.base_toughness == 5

    def test_is_creature(self):
        card = LoreholdTheHistorian()
        assert CardType.CREATURE in card.card_types

    def test_is_legendary(self):
        card = LoreholdTheHistorian()
        assert Supertype.LEGENDARY in card.supertypes

    def test_elder_subtype(self):
        card = LoreholdTheHistorian()
        assert "Elder" in card.subtypes

    def test_dragon_subtype(self):
        card = LoreholdTheHistorian()
        assert "Dragon" in card.subtypes

    def test_flying_keyword(self):
        card = LoreholdTheHistorian()
        assert Keyword.FLYING in card.keywords

    def test_haste_keyword(self):
        card = LoreholdTheHistorian()
        assert Keyword.HASTE in card.keywords


class TestLoreholdUpkeepTrigger:
    def _setup_lorehold_on_battlefield(self, game):
        """Place Lorehold on p1's battlefield and register triggers."""
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)
        return lorehold

    def test_upkeep_trigger_registered(self):
        """register_triggers should add an upkeep trigger."""
        from engine.events import BeginningOfUpkeepTriggeredEvent

        game = create_game()
        self._setup_lorehold_on_battlefield(game)

        triggers = game.trigger_manager.get_triggers()
        upkeep_triggers = [t for t in triggers if t.event_type is BeginningOfUpkeepTriggeredEvent]
        assert len(upkeep_triggers) >= 1

    def test_upkeep_trigger_fires_on_opponent_upkeep(self):
        """Trigger should push onto the stack when opponent is active player."""
        from engine.events import BeginningOfUpkeepTriggeredEvent

        game = create_game()
        self._setup_lorehold_on_battlefield(game)

        # Set p2 as active player (opponent's upkeep)
        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert not game.stack.is_empty()

    def test_upkeep_trigger_does_not_fire_on_own_upkeep(self):
        """Trigger should NOT fire when controller (p1) is the active player."""
        from engine.events import BeginningOfUpkeepTriggeredEvent

        game = create_game()
        self._setup_lorehold_on_battlefield(game)

        # p1 is active player (own upkeep)
        game.active_player_index = 0
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert game.stack.is_empty()

    def test_discard_to_draw_preserves_hand_size(self):
        """Discarding a card should draw a replacement (net hand size unchanged)."""
        from engine.events import BeginningOfUpkeepTriggeredEvent
        from engine.player import DeterministicPlayer

        game = create_game()
        p1 = game.players[0]
        lorehold = self._setup_lorehold_on_battlefield(game)

        # Give p1 a card in hand to discard and a card in library to draw
        hand_card = Instant(
            name="DiscardMe", mana_cost=ManaCost.parse("{1}"), owner=p1, controller=p1
        )
        draw_card = Sorcery(
            name="DrawMe", mana_cost=ManaCost.parse("{1}"), owner=p1, controller=p1
        )
        set_board_state(game, 0, hand=[hand_card])
        game.get_library(p1).add(draw_card)

        # Script p1 to choose hand_card to discard
        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(hand_card)

        # Opponent's upkeep
        game.active_player_index = 1
        initial_hand = len(game.get_hand(p1).get_all())

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        final_hand = len(game.get_hand(p1).get_all())
        assert final_hand == initial_hand  # discarded one, drew one

    def test_discard_card_goes_to_graveyard(self):
        """The discarded card should end up in the graveyard."""
        from engine.events import BeginningOfUpkeepTriggeredEvent
        from engine.player import DeterministicPlayer

        game = create_game()
        p1 = game.players[0]
        self._setup_lorehold_on_battlefield(game)

        hand_card = Instant(
            name="DiscardMe2", mana_cost=ManaCost.parse("{1}"), owner=p1, controller=p1
        )
        draw_card_obj = Sorcery(
            name="DrawMe2", mana_cost=ManaCost.parse("{1}"), owner=p1, controller=p1
        )
        set_board_state(game, 0, hand=[hand_card])
        game.get_library(p1).add(draw_card_obj)

        if isinstance(p1, DeterministicPlayer):
            p1._script.appendleft(hand_card)

        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        graveyard = game.get_graveyard(p1)
        assert graveyard.contains(hand_card)


class TestLoreholdMiracleGrant:
    def _setup_lorehold_on_battlefield(self, game):
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)
        return lorehold

    def test_miracle_trigger_registered(self):
        """register_triggers should register a DrawsCardTriggeredEvent trigger."""
        from engine.events import DrawsCardTriggeredEvent

        game = create_game()
        self._setup_lorehold_on_battlefield(game)

        triggers = game.trigger_manager.get_triggers()
        draw_triggers = [t for t in triggers if t.event_type is DrawsCardTriggeredEvent]
        assert len(draw_triggers) >= 1

    def test_miracle_eligible_set_on_first_drawn_instant(self):
        """First-drawn instant should get miracle_eligible=True and miracle_cost={2}."""
        from engine.events import DrawsCardTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        self._setup_lorehold_on_battlefield(game)

        instant_card = Instant(
            name="FireBolt", mana_cost=ManaCost.parse("{R}"), owner=p1, controller=p1
        )
        p1.cards_drawn_this_turn = 1  # simulate first draw
        game.trigger_manager.fire_event(
            game, DrawsCardTriggeredEvent(player=p1, card=instant_card)
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert getattr(instant_card, "miracle_eligible", False) is True
        assert getattr(instant_card, "miracle_cost", None) == ManaCost.parse("{2}")

    def test_miracle_eligible_set_on_first_drawn_sorcery(self):
        """First-drawn sorcery should also get miracle."""
        from engine.events import DrawsCardTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        self._setup_lorehold_on_battlefield(game)

        sorcery_card = Sorcery(
            name="TimeWarp", mana_cost=ManaCost.parse("{3}{U}{U}"), owner=p1, controller=p1
        )
        p1.cards_drawn_this_turn = 1
        game.trigger_manager.fire_event(
            game, DrawsCardTriggeredEvent(player=p1, card=sorcery_card)
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert getattr(sorcery_card, "miracle_eligible", False) is True
        assert getattr(sorcery_card, "miracle_cost", None) == ManaCost.parse("{2}")

    def test_miracle_not_granted_on_second_draw(self):
        """Second-drawn card should NOT receive miracle."""
        from engine.events import DrawsCardTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        self._setup_lorehold_on_battlefield(game)

        instant_card = Instant(
            name="Bolt2", mana_cost=ManaCost.parse("{R}"), owner=p1, controller=p1
        )
        p1.cards_drawn_this_turn = 2  # second draw
        game.trigger_manager.fire_event(
            game, DrawsCardTriggeredEvent(player=p1, card=instant_card)
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert getattr(instant_card, "miracle_eligible", False) is False

    def test_miracle_not_granted_to_creature(self):
        """Creatures should NOT receive miracle even as the first draw."""
        from engine.events import DrawsCardTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        self._setup_lorehold_on_battlefield(game)

        creature_card = Creature(
            name="BigBear", base_power=2, base_toughness=2, owner=p1, controller=p1
        )
        p1.cards_drawn_this_turn = 1
        game.trigger_manager.fire_event(
            game, DrawsCardTriggeredEvent(player=p1, card=creature_card)
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert getattr(creature_card, "miracle_eligible", False) is False

    def test_miracle_not_granted_to_opponent_draw(self):
        """Opponent drawing a card should not trigger miracle grant."""
        from engine.events import DrawsCardTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        self._setup_lorehold_on_battlefield(game)

        instant_card = Instant(
            name="EnemyBolt", mana_cost=ManaCost.parse("{R}"), owner=p2, controller=p2
        )
        p2.cards_drawn_this_turn = 1
        game.trigger_manager.fire_event(
            game, DrawsCardTriggeredEvent(player=p2, card=instant_card)
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert getattr(instant_card, "miracle_eligible", False) is False
