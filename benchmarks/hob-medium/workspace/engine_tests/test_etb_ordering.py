"""Phase F — own-ETB trigger ordering (rule 603.3a).

The engine now registers an entering permanent's own triggers/replacement
effects *before* firing its ``EntersBattlefieldTriggeredEvent``, so a
permanent's own enters-trigger fires on its own entry (rule 603.3a). Before
Phase F the event fired first, silently suppressing every own-enters ability.

These tests prove both directions:
* an own-enters ("when this creature enters") trigger fires on its own entry;
* an "another …"-filtered trigger does **not** self-fire on its own entry, but
  still fires when a *different* permanent enters;
* a token minted via :func:`engine.game.create_token` fires its own ETB once
  and does not loop.
"""
from __future__ import annotations

import pytest

from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.game import create_token
from engine.game_state import GameState
from engine.intent_player import DeterministicPlayer
from engine.triggers import TriggerRegistration
from engine.types import CardType, Zone
from engine.zones import move_to_zone


@pytest.fixture()
def players() -> list[DeterministicPlayer]:
    return [DeterministicPlayer("Alice"), DeterministicPlayer("Bob")]


@pytest.fixture()
def game(players: list[DeterministicPlayer]) -> GameState:
    return GameState(players)


def _resolve_all(game: GameState) -> None:
    from engine.stack import resolve_top_of_stack

    while not game.stack.is_empty():
        resolve_top_of_stack(game)


class _SelfETBCreature(Creature):
    """"When this creature enters, <fire>." — own-enters trigger."""

    def __init__(self, log: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self._log = log

    def register_triggers(self, game: GameState) -> None:
        source = self

        def _cond(g, event) -> bool:
            return event.permanent is source

        def _effect(g) -> None:
            source._log.append(source.name)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_cond,
                effect=_effect,
                source=self,
                controller=self.controller,
            )
        )


class _AnotherCreatureETB(Creature):
    """"Whenever another creature you control enters, <fire>." — excludes self."""

    def __init__(self, log: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self._log = log

    def register_triggers(self, game: GameState) -> None:
        source = self

        def _cond(g, event) -> bool:
            permanent = event.permanent
            if permanent is None or permanent is source:
                return False
            if getattr(permanent, "controller", None) is not source.controller:
                return False
            return CardType.CREATURE in getattr(permanent, "card_types", set())

        def _effect(g) -> None:
            source._log.append("another")

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_cond,
                effect=_effect,
                source=self,
                controller=self.controller,
            )
        )


def _enter(game: GameState, player, card) -> None:
    """Put *card* into hand then move it to the battlefield (an entry)."""
    card.owner = player
    card.controller = player
    player.zones[Zone.HAND].add(card)
    move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)


class TestOwnETBFiresOnOwnEntry:
    def test_self_etb_fires_exactly_once(self, game, players) -> None:
        log: list[str] = []
        p = players[0]
        card = _SelfETBCreature(log, name="Prober", owner=p, controller=p,
                                base_power=2, base_toughness=2)
        _enter(game, p, card)
        # The own-enters trigger went on the stack; resolve it.
        assert not game.stack.is_empty()
        _resolve_all(game)
        assert log == ["Prober"]

    def test_self_etb_via_create_token_no_loop(self, game, players) -> None:
        log: list[str] = []
        p = players[0]
        # A *token* with its own benign enters-trigger: fires once, no loop.
        token = _SelfETBCreature(log, name="Spark", owner=p, controller=p,
                                 base_power=1, base_toughness=1)
        create_token(game, p, token)
        _resolve_all(game)
        assert log == ["Spark"]
        assert token.is_token is True


class TestAnotherFilteredETBDoesNotSelfFire:
    def test_another_filter_does_not_self_fire(self, game, players) -> None:
        log: list[str] = []
        p = players[0]
        watcher = _AnotherCreatureETB(log, name="Watcher", owner=p, controller=p,
                                      base_power=1, base_toughness=1)
        _enter(game, p, watcher)
        _resolve_all(game)
        # Its own entry must NOT fire the "another creature" trigger.
        assert log == []

    def test_another_filter_fires_for_a_different_creature(self, game, players) -> None:
        log: list[str] = []
        p = players[0]
        watcher = _AnotherCreatureETB(log, name="Watcher", owner=p, controller=p,
                                      base_power=1, base_toughness=1)
        _enter(game, p, watcher)
        _resolve_all(game)
        assert log == []
        # A different creature entering fires it exactly once.
        other = Creature(name="Bear", owner=p, controller=p, base_power=2, base_toughness=2)
        _enter(game, p, other)
        _resolve_all(game)
        assert log == ["another"]
