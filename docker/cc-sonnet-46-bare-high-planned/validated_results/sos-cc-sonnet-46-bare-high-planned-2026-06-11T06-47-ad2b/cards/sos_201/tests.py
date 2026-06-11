"""Tests for Lorehold, the Historian (sos_201)."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery, Land
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Step, Zone
from test_utils import _resolve_top_of_stack, advance_to_phase, create_game


def _put_on_battlefield(game, player_index, card):
    p = game.players[player_index]
    card.owner = p
    card.controller = p
    p.zones[Zone.BATTLEFIELD].add(card)
    if hasattr(card, "register_triggers"):
        card.register_triggers(game)


def _add_to_hand(game, player_index, card):
    p = game.players[player_index]
    card.owner = p
    card.controller = p
    p.zones[Zone.HAND].add(card)


def _add_to_library(game, player_index, card):
    p = game.players[player_index]
    card.owner = p
    card.controller = p
    p.zones[Zone.LIBRARY].add(card)


class TestLoreholdProperties:
    def test_name(self) -> None:
        assert LoreholdTheHistorian().name == "Lorehold, the Historian"

    def test_stats(self) -> None:
        card = LoreholdTheHistorian()
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_keywords(self) -> None:
        card = LoreholdTheHistorian()
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords

    def test_is_creature(self) -> None:
        assert CardType.CREATURE in LoreholdTheHistorian().card_types


class TestMiracleDrawTrigger:
    def test_miracle_fires_on_first_draw_instant(self) -> None:
        """First draw of turn fires miracle if it's an instant."""
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        game.turn_number = 1

        lorehold = LoreholdTheHistorian()
        _put_on_battlefield(game, 0, lorehold)

        # Put an instant in the library (top)
        instant = Instant(name="Shock", mana_cost=ManaCost.parse("{R}"))
        _add_to_library(game, 0, instant)

        # Script: yes, cast the miracle
        p1._script.appendleft(True)

        # Draw the card → triggers miracle → resolves
        from engine.game import draw_card
        draw_card(game, p1)
        # Stack now has the miracle trigger
        assert not game.stack.is_empty()
        _resolve_top_of_stack(game)
        # The instant was cast (moved to stack → graveyard after casting)
        # At minimum: the trigger fired without error

    def test_miracle_does_not_fire_on_second_draw(self) -> None:
        """Second draw of the turn does not trigger miracle."""
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        game.turn_number = 2

        lorehold = LoreholdTheHistorian()
        _put_on_battlefield(game, 0, lorehold)

        # First draw: land (no miracle)
        land = Land(name="Plains")
        _add_to_library(game, 0, land)
        # Second draw: instant (no miracle — not first draw)
        instant = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        _add_to_library(game, 0, instant)

        from engine.game import draw_card
        # Draw land first (top is last element; we add land first, instant second)
        # Library top = last added = instant
        # So draw instant first, then land
        draw_card(game, p1)  # draws instant (first draw this turn)
        # Miracle should fire for instant
        if not game.stack.is_empty():
            p1._script.appendleft(False)  # decline miracle
            _resolve_top_of_stack(game)

        draw_card(game, p1)  # draws land (second draw — no miracle)
        # Stack should still be empty (no miracle for second draw)
        assert game.stack.is_empty()

    def test_miracle_does_not_fire_if_first_draw_is_non_spell(self) -> None:
        """If first draw is a land, miracle doesn't fire even for subsequent spells."""
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        game.turn_number = 3

        lorehold = LoreholdTheHistorian()
        _put_on_battlefield(game, 0, lorehold)

        # Add instant to library bottom, land on top
        instant = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        land = Land(name="Plains")
        _add_to_library(game, 0, instant)  # bottom (added first)
        _add_to_library(game, 0, land)     # top (added second, drawn first)

        from engine.game import draw_card
        draw_card(game, p1)  # draws land (first draw — not inst/sorc → miracle condition fails)
        assert game.stack.is_empty()

        draw_card(game, p1)  # draws instant (second draw — miracle not eligible)
        assert game.stack.is_empty()


class TestOpponentUpkeepLoot:
    def test_loot_trigger_fires_on_opponent_upkeep(self) -> None:
        """Loot trigger fires at the beginning of each opponent's upkeep."""
        game = create_game()
        p1, p2 = game.players

        lorehold = LoreholdTheHistorian()
        _put_on_battlefield(game, 0, lorehold)

        # Give p1 a card in hand to discard
        hand_card = Instant(name="Junk", mana_cost=ManaCost.parse("{1}"))
        _add_to_hand(game, 0, hand_card)

        # Give p1 a card in library to draw
        draw_card_obj = Sorcery(name="DrawMe", mana_cost=ManaCost.parse("{1}"))
        _add_to_library(game, 0, draw_card_obj)

        # Set up p2's upkeep
        game.active_player_index = 1
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP
        from engine.events import BeginningOfUpkeepTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        # Script: yes discard, choose hand_card.
        # appendleft pushes to front; popleft takes from front → last appendleft = first consumed.
        p1._script.appendleft(hand_card)  # second choice (choose_card)
        p1._script.appendleft(True)       # first choice (choose_yes_no)
        _resolve_top_of_stack(game)

        # p1 should have discarded hand_card and drawn draw_card_obj
        assert not p1.zones[Zone.HAND].contains(hand_card)
        assert p1.zones[Zone.HAND].contains(draw_card_obj)

    def test_loot_does_not_fire_on_own_upkeep(self) -> None:
        """Loot trigger does NOT fire during controller's own upkeep."""
        game = create_game()
        p1, p2 = game.players

        lorehold = LoreholdTheHistorian()
        _put_on_battlefield(game, 0, lorehold)

        # p1's own upkeep
        game.active_player_index = 0
        from engine.events import BeginningOfUpkeepTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        # Stack should be empty — trigger doesn't fire on own upkeep
        assert game.stack.is_empty()

    def test_loot_decline_draws_no_card(self) -> None:
        """Declining to discard means no card is drawn."""
        game = create_game()
        p1, p2 = game.players

        lorehold = LoreholdTheHistorian()
        _put_on_battlefield(game, 0, lorehold)

        hand_card = Instant(name="Junk", mana_cost=ManaCost.parse("{1}"))
        _add_to_hand(game, 0, hand_card)

        game.active_player_index = 1
        from engine.events import BeginningOfUpkeepTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        p1._script.appendleft(False)  # decline
        hand_before = list(p1.zones[Zone.HAND].get_all())
        _resolve_top_of_stack(game)

        # Hand unchanged — no discard, no draw
        assert list(p1.zones[Zone.HAND].get_all()) == hand_before
