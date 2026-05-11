"""Audited tests for Shipwreck Dowser (FDN collector number 596) — ETB return instant/sorcery."""
from __future__ import annotations
import pytest
from card_impl import ShipwreckDowser
from engine.card import CardImpl, Creature
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.triggers import EventType
from engine.types import Keyword, ManaCost, Phase, Zone

from engine.card import Instant

def _make_game():
    p1 = DeterministicPlayer("Alice", [])
    p2 = DeterministicPlayer("Bob", [])
    game = GameState([p1, p2])
    game.phase = Phase.PRECOMBAT_MAIN
    game.active_player_index = 0
    return game

def _add_library(player, n):
    cards = []
    for i in range(n):
        c = CardImpl(name=f"LibCard{i}")
        c.owner = player
        player.zones[Zone.LIBRARY].add(c)
        cards.append(c)
    return cards

def _simulate_etb(game, creature, controller=None):
    if controller is None:
        controller = getattr(creature, "controller", game.players[0])
    creature.register_triggers(game)
    game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {"permanent": creature, "controller": controller})
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)

def _place_on_battlefield(game, creature, player):
    creature.owner = player
    creature.controller = player
    game.get_battlefield(player).add(creature)

@pytest.mark.basic
class TestShipwreckDowserProperties:
    def test_is_creature(self):
        assert isinstance(ShipwreckDowser(), Creature)
    def test_power_toughness(self):
        c = ShipwreckDowser()
        assert c.base_power == 3 and c.base_toughness == 3
    def test_mana_cost(self):
        assert ShipwreckDowser().mana_cost == ManaCost.parse("{3}{U}{U}")

@pytest.mark.ability
class TestShipwreckDowserETB:
    def test_etb_returns_instant_from_graveyard(self):
        game = _make_game()
        p1 = game.players[0]
        spell = Instant(name="Lightning Bolt", owner=p1)
        p1.zones[Zone.GRAVEYARD].add(spell)
        c = ShipwreckDowser(owner=p1, controller=p1)
        c.chosen_targets = [spell]
        _simulate_etb(game, c)
        assert p1.zones[Zone.HAND].contains(spell)
