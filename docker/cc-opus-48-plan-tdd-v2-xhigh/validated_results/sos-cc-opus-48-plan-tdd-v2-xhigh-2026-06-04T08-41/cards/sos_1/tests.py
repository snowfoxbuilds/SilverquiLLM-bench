"""Tests for The Dawning Archaic (SOS 1)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class _GainLifeInstant(Instant):
    """A no-target instant that gains its controller 3 life on resolve."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Surge")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 3


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestProperties:
    def test_static_data(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")
        assert CardType.CREATURE in card.card_types
        assert card.base_power == 7
        assert card.base_toughness == 7
        assert Keyword.REACH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes


class TestCostReduction:
    def test_counts_graveyard_instants_sorceries(self) -> None:
        game = create_game()
        p1, _ = game.players
        card = TheDawningArchaic(owner=p1, controller=p1)
        gy = [
            Instant(name="I1", mana_cost=ManaCost.parse("{1}")),
            Sorcery(name="S1", mana_cost=ManaCost.parse("{2}")),
            # A creature card in the graveyard should not count.
        ]
        from engine.card import Creature
        gy.append(Creature(name="Beast", base_power=1, base_toughness=1))
        set_board_state(game, 0, graveyard=gy)
        assert card.cost_reduction(game) == 2

    def test_empty_graveyard(self) -> None:
        game = create_game()
        p1, _ = game.players
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0


class TestAttackTrigger:
    def _setup(self, game, p1, *, gy):
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[archaic], graveyard=gy)
        archaic.register_triggers(game)
        return archaic

    def test_recast_resolves_and_exiles(self) -> None:
        game = create_game()
        p1, _ = game.players
        surge = _GainLifeInstant(owner=p1, controller=p1)
        archaic = self._setup(game, p1, gy=[surge])
        p1.life = 20
        p1._script.extend([True, surge])  # yes, then choose surge
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=archaic, attacker=archaic))
        _resolve_stack(game)
        # Spell resolved (gained 3 life) and was exiled, not in graveyard.
        assert p1.life == 23
        assert p1.zones[Zone.EXILE].contains(surge)
        assert not p1.zones[Zone.GRAVEYARD].contains(surge)

    def test_may_decline(self) -> None:
        game = create_game()
        p1, _ = game.players
        surge = _GainLifeInstant(owner=p1, controller=p1)
        archaic = self._setup(game, p1, gy=[surge])
        p1.life = 20
        p1._script.append(False)  # decline
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=archaic, attacker=archaic))
        _resolve_stack(game)
        assert p1.life == 20
        assert p1.zones[Zone.GRAVEYARD].contains(surge)

    def test_empty_graveyard_noop(self) -> None:
        game = create_game()
        p1, _ = game.players
        archaic = self._setup(game, p1, gy=[])
        # No script entries needed; trigger should no-op without asking.
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=archaic, attacker=archaic))
        _resolve_stack(game)
        assert p1.remaining_choices == 0
