"""Audited tests for Reclamation Sage (FDN collector number 231) — ETB destroy artifact/enchantment."""
from __future__ import annotations
import pytest
from card_impl import ReclamationSage
from engine.card import CardImpl, Creature
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.triggers import EventType
from engine.types import Keyword, ManaCost, Phase, Zone

from engine.card import Artifact, Enchantment

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
class TestReclamationSageProperties:
    def test_is_creature(self):
        assert isinstance(ReclamationSage(), Creature)
    def test_power_toughness(self):
        c = ReclamationSage()
        assert c.base_power == 2 and c.base_toughness == 1
    def test_mana_cost(self):
        assert ReclamationSage().mana_cost == ManaCost.parse("{2}{G}")

@pytest.mark.ability
class TestReclamationSageETB:
    def test_etb_destroys_artifact(self):
        game = _make_game()
        p1, p2 = game.players
        artifact = Artifact(name="Sol Ring", owner=p2, controller=p2)
        game.get_battlefield(p2).add(artifact)
        c = ReclamationSage(owner=p1, controller=p1)
        c.chosen_targets = [artifact]
        _simulate_etb(game, c)
        assert not game.get_battlefield(p2).contains(artifact)

    def test_etb_no_target_no_crash(self):
        game = _make_game()
        p1 = game.players[0]
        c = ReclamationSage(owner=p1, controller=p1)
        _simulate_etb(game, c)  # Should not crash
