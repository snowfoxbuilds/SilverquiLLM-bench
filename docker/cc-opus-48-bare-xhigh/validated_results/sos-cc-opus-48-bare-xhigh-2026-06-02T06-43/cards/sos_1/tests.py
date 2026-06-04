"""Tests for The Dawning Archaic (SOS 1)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class _Pinger(Instant):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pinger")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        game._resolved = getattr(game, "_resolved", 0) + 1


def _resolve_stack(game: Any) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


def _instant(name: str = "I") -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse("{1}"))


def _sorcery(name: str = "S") -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse("{1}"))


class TestArchaicProperties:
    def test_is_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_power_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.power == 7
        assert card.toughness == 7

    def test_reach(self) -> None:
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords

    def test_legendary_avatar(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes


class TestArchaicCostReduction:
    def test_no_graveyard_no_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        assert archaic.cost_reduction(game) == 0

    def test_counts_only_instants_and_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]
        set_board_state(
            game,
            0,
            graveyard=[
                _instant("a"),
                _instant("b"),
                _sorcery("c"),
                Creature(name="Body", base_power=1, base_toughness=1),
            ],
        )
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        assert archaic.cost_reduction(game) == 3

    def test_get_cost_reduction_clamped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, graveyard=[_instant(f"i{i}") for i in range(12)])
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        assert get_cost_reduction(game, archaic, p1) == 10


class TestArchaicAttackTrigger:
    def _setup(self, scripts):
        game = create_game(scripts=scripts)
        p1, p2 = game.players
        archaic = TheDawningArchaic()
        set_board_state(game, 0, battlefield=[archaic])
        archaic.register_triggers(game)
        return game, p1, p2, archaic

    def test_registers_trigger(self) -> None:
        game, p1, p2, archaic = self._setup(([], []))
        assert len(game.trigger_manager.get_triggers_for_source(archaic)) == 1

    def test_casts_and_exiles_instead_of_graveyard(self) -> None:
        pinger = _Pinger()
        game, p1, p2, archaic = self._setup(([True, pinger], []))
        pinger.owner = p1
        pinger.controller = p1
        p1.zones[Zone.GRAVEYARD].add(pinger)

        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=archaic, attacker=archaic)
        )
        _resolve_stack(game)

        assert game._resolved == 1
        assert p1.zones[Zone.EXILE].contains(pinger)
        assert not p1.zones[Zone.GRAVEYARD].contains(pinger)

    def test_decline_does_nothing(self) -> None:
        pinger = _Pinger()
        game, p1, p2, archaic = self._setup(([False], []))
        pinger.owner = p1
        pinger.controller = p1
        p1.zones[Zone.GRAVEYARD].add(pinger)

        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=archaic, attacker=archaic)
        )
        _resolve_stack(game)

        assert getattr(game, "_resolved", 0) == 0
        assert p1.zones[Zone.GRAVEYARD].contains(pinger)

    def test_no_instant_or_sorcery_in_graveyard(self) -> None:
        game, p1, p2, archaic = self._setup(([], []))
        # Only a creature in the graveyard — nothing to cast.
        body = Creature(name="Body", base_power=1, base_toughness=1)
        body.owner = p1
        p1.zones[Zone.GRAVEYARD].add(body)

        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=archaic, attacker=archaic)
        )
        _resolve_stack(game)
        # No crash; creature still in the graveyard.
        assert p1.zones[Zone.GRAVEYARD].contains(body)

    def test_trigger_only_fires_for_self(self) -> None:
        pinger = _Pinger()
        game, p1, p2, archaic = self._setup(([True, pinger], []))
        pinger.owner = p1
        pinger.controller = p1
        p1.zones[Zone.GRAVEYARD].add(pinger)

        other = Creature(name="Other", base_power=1, base_toughness=1)
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=other, attacker=other)
        )
        _resolve_stack(game)
        # Archaic's trigger should not have fired for a different attacker.
        assert getattr(game, "_resolved", 0) == 0
        assert p1.zones[Zone.GRAVEYARD].contains(pinger)
