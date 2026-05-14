"""Audited tests for FDN 75 — Vampire Soulcaller."""

from __future__ import annotations

from card_impl import VampireSoulcaller
from engine.card import Creature
from engine.triggers import EventType
from engine.types import Keyword, ManaCost, Zone
from tests.test_utils import create_game


class TestVampireSoulcallerBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = VampireSoulcaller(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = VampireSoulcaller(owner=None)
        assert card.name == "Vampire Soulcaller"

    def test_mana_cost(self) -> None:
        card = VampireSoulcaller(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}{B}")

    def test_power_toughness(self) -> None:
        card = VampireSoulcaller(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 2

    def test_has_flying(self) -> None:
        card = VampireSoulcaller(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_subtypes(self) -> None:
        card = VampireSoulcaller(owner=None)
        assert "Vampire" in card.subtypes
        assert "Warlock" in card.subtypes


class TestVampireSoulcallerETB:
    """ETB: return target creature card from your graveyard to hand."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def test_returns_creature_from_graveyard_to_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = VampireSoulcaller(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        target = Creature(name="Dead", base_power=2, base_toughness=2, owner=p1)
        p1.zones[Zone.GRAVEYARD].add(target)
        card.chosen_targets = [target]
        card.register_triggers(game)
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {"permanent": card})
        self._resolve_stack(game)
        assert p1.zones[Zone.HAND].contains(target)
        assert not p1.zones[Zone.GRAVEYARD].contains(target)

    def test_no_effect_with_no_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = VampireSoulcaller(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.chosen_targets = [None]
        card.register_triggers(game)
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {"permanent": card})
        self._resolve_stack(game)
        # No crash, nothing happens

    def test_no_effect_if_target_not_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = VampireSoulcaller(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        target = Creature(name="Dead", base_power=2, base_toughness=2, owner=p1)
        # Target is NOT in graveyard
        card.chosen_targets = [target]
        card.register_triggers(game)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {"permanent": card})
        self._resolve_stack(game)
        hand_after = len(p1.zones[Zone.HAND].get_all())
        assert hand_after == hand_before
