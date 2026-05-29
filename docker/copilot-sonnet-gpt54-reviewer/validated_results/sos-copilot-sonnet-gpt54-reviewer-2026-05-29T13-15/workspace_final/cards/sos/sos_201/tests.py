"""Tests for sos_201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import DrawsCardTriggeredEvent, BeginningOfUpkeepTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class TestLoreholdProperties:
    def test_name(self) -> None:
        assert LoreholdTheHistorian(owner=None).name == "Lorehold, the Historian"

    def test_mana_cost(self) -> None:
        assert LoreholdTheHistorian(owner=None).mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_is_creature(self) -> None:
        assert isinstance(LoreholdTheHistorian(owner=None), Creature)

    def test_power_toughness(self) -> None:
        c = LoreholdTheHistorian(owner=None)
        assert c.base_power == 5
        assert c.base_toughness == 5

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in LoreholdTheHistorian(owner=None).keywords

    def test_has_haste(self) -> None:
        assert Keyword.HASTE in LoreholdTheHistorian(owner=None).keywords

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in LoreholdTheHistorian(owner=None).supertypes

    def test_has_dragon_subtype(self) -> None:
        assert "Dragon" in LoreholdTheHistorian(owner=None).subtypes


class TestLoreholdMiracle:
    """Instants and sorceries in hand have miracle {2}."""

    def test_miracle_trigger_registers(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        lorehold.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_miracle_fires_on_draw(self) -> None:
        """When controller draws first card of turn, miracle trigger fires."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        instant = Instant(
            name="Miracle Instant", mana_cost=ManaCost.parse("{3}"),
            owner=p1, controller=p1,
        )
        p1.zones[Zone.LIBRARY].add(instant)

        # Simulate the first card drawn this turn
        p1.cards_drawn_this_turn = 1

        # Fire the draw event for the first card this turn
        game.trigger_manager.fire_event(
            game,
            DrawsCardTriggeredEvent(player=p1, card=instant),
        )
        assert not game.stack.is_empty()

    def test_miracle_not_offered_for_non_instant_sorcery(self) -> None:
        """Creatures don't get miracle."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1)

        p1.cards_drawn_this_turn = 1
        game.trigger_manager.fire_event(
            game,
            DrawsCardTriggeredEvent(player=p1, card=creature),
        )
        # No trigger pushed (creature, not instant/sorcery)
        assert game.stack.is_empty()

    def test_miracle_cast_costs_two(self) -> None:
        """Miracle cast costs {2} regardless of the card's printed cost."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        # Expensive instant that would cost more normally
        instant = Instant(
            name="Expensive Instant",
            mana_cost=ManaCost.parse("{5}{U}"),
            owner=p1, controller=p1,
        )
        p1.zones[Zone.HAND].add(instant)

        # Give player only 2 colorless mana
        from engine.types import ManaType
        p1.mana_pool.add(ManaType.COLORLESS, 2)

        # Simulate first card drawn this turn
        p1.cards_drawn_this_turn = 1

        game.trigger_manager.fire_event(
            game, DrawsCardTriggeredEvent(player=p1, card=instant),
        )
        # Trigger should be on stack - resolve it
        # Script: yes to miracle cast
        p1._script.appendleft(True)

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        # The card was cast for free (2 mana was enough)
        assert not p1.zones[Zone.HAND].contains(instant)


class TestLoreholdOpponentUpkeep:
    """At beginning of each opponent's upkeep: may discard, if so draw."""

    def test_upkeep_trigger_registers(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        lorehold.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(lorehold)
        assert len(triggers) >= 1

    def test_discard_and_draw_at_opponent_upkeep(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        # Put cards in p1's hand and library
        card_in_hand = Instant(name="Discard Me", owner=p1)
        p1.zones[Zone.HAND].add(card_in_hand)
        library_card = Creature(name="Draw Me", owner=p1)
        p1.zones[Zone.LIBRARY].add(library_card)

        # Make it opponent's upkeep (p2 is active player)
        game.active_player_index = 1

        # Fire upkeep event
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        # Script: yes to discard, choose card_in_hand
        p1._script.appendleft(card_in_hand)  # which card to discard
        p1._script.appendleft(True)           # yes, discard

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        # card_in_hand should be discarded
        assert p1.zones[Zone.GRAVEYARD].contains(card_in_hand)
        # library_card should be drawn
        assert p1.zones[Zone.HAND].contains(library_card)

    def test_no_discard_no_draw(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        library_card = Creature(name="Draw Me", owner=p1)
        p1.zones[Zone.LIBRARY].add(library_card)
        game.active_player_index = 1

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        # Say no to discard
        p1._script.appendleft(False)

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        # Library card not drawn
        assert not p1.zones[Zone.HAND].contains(library_card)

    def test_own_upkeep_does_not_trigger(self) -> None:
        """Trigger only fires at opponents' upkeep, not Lorehold's controller's upkeep."""
        game = create_game()
        p1 = game.players[0]
        lorehold = LoreholdTheHistorian(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lorehold)
        lorehold.register_triggers(game)

        # p1 is the active player (own upkeep)
        game.active_player_index = 0
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        # No trigger should be pushed
        assert game.stack.is_empty()
