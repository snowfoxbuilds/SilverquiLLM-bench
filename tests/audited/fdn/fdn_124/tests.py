"""Audited tests for FDN 124 — Perforating Artist."""

from __future__ import annotations

from card_impl import PerforatingArtist
from engine.card import Creature
from engine.triggers import EventType
from engine.types import Keyword, ManaCost, Zone
from tests.test_utils import create_game


def _resolve_stack(game):
    """Pop and resolve all objects on the stack."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestPerforatingArtistBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = PerforatingArtist(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = PerforatingArtist(owner=None)
        assert card.name == "Perforating Artist"

    def test_mana_cost(self) -> None:
        card = PerforatingArtist(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}{R}")

    def test_power_toughness(self) -> None:
        card = PerforatingArtist(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 2

    def test_has_deathtouch(self) -> None:
        card = PerforatingArtist(owner=None)
        assert Keyword.DEATHTOUCH in card.keywords

    def test_subtypes(self) -> None:
        card = PerforatingArtist(owner=None)
        assert "Devil" in card.subtypes


class TestPerforatingArtistRaid:
    """Raid end-step trigger: opponents lose 3 life or sacrifice/discard."""

    def test_opponent_loses_3_life_no_alternatives(self) -> None:
        """With no permanents or cards in hand, opponent loses 3 life."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        artist = PerforatingArtist(owner=p1, controller=p1)
        game.get_battlefield(p1).add(artist)
        artist.register_triggers(game)
        game.active_player_index = 0
        game.attacked_this_turn = True
        p1.attacked_this_turn = True
        p2_life_before = p2.life
        game.trigger_manager.fire_event(game, EventType.END_STEP, {})
        _resolve_stack(game)
        assert p2.life == p2_life_before - 3

    def test_no_trigger_without_attack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        artist = PerforatingArtist(owner=p1, controller=p1)
        game.get_battlefield(p1).add(artist)
        artist.register_triggers(game)
        game.active_player_index = 0
        game.attacked_this_turn = False
        p1.attacked_this_turn = False
        p2_life_before = p2.life
        game.trigger_manager.fire_event(game, EventType.END_STEP, {})
        _resolve_stack(game)
        assert p2.life == p2_life_before

    def test_active_player_guard(self) -> None:
        """Only triggers on controller's end step."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        artist = PerforatingArtist(owner=p1, controller=p1)
        game.get_battlefield(p1).add(artist)
        artist.register_triggers(game)
        game.active_player_index = 1
        game.attacked_this_turn = True
        p1.attacked_this_turn = True
        p2_life_before = p2.life
        game.trigger_manager.fire_event(game, EventType.END_STEP, {})
        _resolve_stack(game)
        assert p2.life == p2_life_before

    def test_opponent_can_sacrifice_nonland(self) -> None:
        """Opponent can sacrifice a nonland permanent instead of losing life."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        artist = PerforatingArtist(owner=p1, controller=p1)
        game.get_battlefield(p1).add(artist)
        token = Creature(name="Token", base_power=1, base_toughness=1, owner=p2, controller=p2)
        game.get_battlefield(p2).add(token)
        artist.register_triggers(game)
        game.active_player_index = 0
        game.attacked_this_turn = True
        p1.attacked_this_turn = True
        p2._script.appendleft(token)
        p2_life_before = p2.life
        game.trigger_manager.fire_event(game, EventType.END_STEP, {})
        _resolve_stack(game)
        assert p2.life == p2_life_before
        assert not game.get_battlefield(p2).contains(token)
