"""Audited tests for FDN 13 — Fleeting Flight."""

from __future__ import annotations

from card_impl import FleetingFlight
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost
from test_utils import create_game


class TestFleetingFlightBasics:
    """Basic card properties."""

    def test_is_instant(self) -> None:
        card = FleetingFlight(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = FleetingFlight(owner=None)
        assert card.name == "Fleeting Flight"

    def test_mana_cost(self) -> None:
        card = FleetingFlight(owner=None)
        assert card.mana_cost == ManaCost.parse("{W}")


class TestFleetingFlightResolve:
    """Put +1/+1 counter, grant flying, prevent combat damage."""

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        target = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        spell = FleetingFlight(owner=p1, controller=p1)
        return game, p1, target, spell

    def test_adds_plus_one_counter(self) -> None:
        game, p1, target, spell = self._setup()
        spell.chosen_targets = [target]
        spell.on_resolve(game)
        assert getattr(target, "plus_one_counters", 0) >= 1

    def test_grants_flying(self) -> None:
        game, p1, target, spell = self._setup()
        spell.chosen_targets = [target]
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.FLYING in target.keywords

    def test_sets_combat_damage_prevented_flag(self) -> None:
        game, p1, target, spell = self._setup()
        spell.chosen_targets = [target]
        spell.on_resolve(game)
        assert getattr(target, "combat_damage_prevented", False) is True

    def test_no_target_does_not_error(self) -> None:
        game, p1, target, spell = self._setup()
        spell.chosen_targets = []
        spell.on_resolve(game)  # Should not raise

    def test_has_target_requirement(self) -> None:
        game, p1, target, spell = self._setup()
        targets = spell.get_targets(game)
        assert len(targets) == 1
        assert "creature" in targets[0].description.lower()
