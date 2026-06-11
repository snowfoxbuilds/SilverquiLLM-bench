"""Tests for sos_201 — Lorehold, the Historian."""

from __future__ import annotations

from engine.card import Creature, Instant, Sorcery
from engine.game_state import Phase
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from test_utils import create_game, set_board_state, _resolve_top_of_stack


class TestLoreholdProperties:
    def test_name(self) -> None:
        assert LoreholdTheHistorian().name == "Lorehold, the Historian"

    def test_flying_haste(self) -> None:
        c = LoreholdTheHistorian()
        assert Keyword.FLYING in c.keywords
        assert Keyword.HASTE in c.keywords

    def test_stats(self) -> None:
        c = LoreholdTheHistorian()
        assert c.base_power == 5
        assert c.base_toughness == 5

    def test_is_creature(self) -> None:
        assert CardType.CREATURE in LoreholdTheHistorian().card_types


class TestMiracle:
    def _setup(self):
        game = create_game()
        p0 = game.players[0]
        lorehold = LoreholdTheHistorian()
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)
        return game, p0, lorehold

    def test_miracle_fires_on_first_instant_drawn(self) -> None:
        """Drawing an instant as the first card of the turn fires miracle trigger."""
        game, p0, lorehold = self._setup()

        instant = Instant(name="Zap", mana_cost=ManaCost(generic=0))
        instant.owner = p0
        instant.controller = p0
        p0.zones[Zone.LIBRARY]._objects.append(instant)

        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        p0.cards_drawn_this_turn = 0

        from engine.game import draw_card
        draw_card(game, p0)  # cards_drawn_this_turn → 1, fires event

        # Trigger is on the stack
        assert not game.stack.is_empty()

        # Accept miracle, cast for {2}
        p0._script.append(True)  # yes, cast for miracle cost
        _resolve_top_of_stack(game)

        # Card should be on stack (cast via miracle)
        # (it resolves since no targets needed)
        assert not game.get_hand(p0).contains(instant)

    def test_miracle_does_not_fire_on_second_draw(self) -> None:
        """Miracle only fires on the FIRST card drawn this turn."""
        game, p0, lorehold = self._setup()

        instant = Instant(name="Zap", mana_cost=ManaCost(generic=0))
        instant.owner = p0
        instant.controller = p0
        p0.zones[Zone.LIBRARY]._objects.append(instant)

        # Simulate already having drawn once
        p0.cards_drawn_this_turn = 1

        from engine.game import draw_card
        draw_card(game, p0)  # cards_drawn_this_turn → 2, NOT the first

        # No trigger should fire
        assert game.stack.is_empty()

    def test_miracle_does_not_fire_for_non_instant_sorcery(self) -> None:
        """Miracle doesn't trigger for creature cards."""
        game, p0, lorehold = self._setup()

        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.owner = p0
        creature.controller = p0
        p0.zones[Zone.LIBRARY]._objects.append(creature)
        p0.cards_drawn_this_turn = 0

        from engine.game import draw_card
        draw_card(game, p0)

        # No trigger
        assert game.stack.is_empty()

    def test_miracle_declined_leaves_card_in_hand(self) -> None:
        """Declining miracle leaves the card in hand without cost."""
        game, p0, lorehold = self._setup()

        sorcery = Sorcery(name="Boom", mana_cost=ManaCost(generic=3))
        sorcery.owner = p0
        sorcery.controller = p0
        p0.zones[Zone.LIBRARY]._objects.append(sorcery)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        p0.cards_drawn_this_turn = 0

        from engine.game import draw_card
        draw_card(game, p0)

        # Trigger fires — decline
        p0._script.append(False)
        _resolve_top_of_stack(game)

        # Card still in hand, no mana spent
        assert game.get_hand(p0).contains(sorcery)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 2  # unchanged


class TestOpponentUpkeepLoot:
    def _setup(self):
        game = create_game()
        p0 = game.players[0]
        lorehold = LoreholdTheHistorian()
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.register_triggers(game)
        return game, p0, lorehold

    def test_loot_fires_on_opponent_upkeep(self) -> None:
        """At the beginning of each opponent's upkeep, may discard to draw."""
        game, p0, lorehold = self._setup()

        # Give p0 a card to discard and a card in library to draw
        discard_target = Instant(name="Fodder", mana_cost=ManaCost(generic=0))
        draw_target = Instant(name="Prize", mana_cost=ManaCost(generic=0))
        set_board_state(game, 0, hand=[discard_target])
        p0.zones[Zone.LIBRARY]._objects.clear()
        draw_target.owner = p0
        draw_target.controller = p0
        p0.zones[Zone.LIBRARY]._objects.append(draw_target)

        # Fire upkeep event for opponent (p1)
        game.active_player_index = 1  # p1's turn
        from engine.events import BeginningOfUpkeepTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        # Trigger on stack — accept: discard Fodder, draw Prize
        p0._script.append(True)        # yes, discard
        p0._script.append(discard_target)  # choose Fodder to discard

        _resolve_top_of_stack(game)

        # Fodder in graveyard, Prize in hand
        assert p0.zones[Zone.GRAVEYARD].contains(discard_target)
        assert game.get_hand(p0).contains(draw_target)

    def test_loot_does_not_fire_on_own_upkeep(self) -> None:
        """Loot trigger should NOT fire on Lorehold controller's own upkeep."""
        game, p0, lorehold = self._setup()

        game.active_player_index = 0  # p0's turn
        from engine.events import BeginningOfUpkeepTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        # No trigger should fire for p0's upkeep
        assert game.stack.is_empty()

    def test_loot_declined_no_draw(self) -> None:
        """Declining loot means no discard and no draw."""
        game, p0, lorehold = self._setup()

        hand_card = Instant(name="Keep", mana_cost=ManaCost(generic=0))
        set_board_state(game, 0, hand=[hand_card])
        game.active_player_index = 1

        from engine.events import BeginningOfUpkeepTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        p0._script.append(False)  # decline
        _resolve_top_of_stack(game)

        assert game.get_hand(p0).contains(hand_card)
