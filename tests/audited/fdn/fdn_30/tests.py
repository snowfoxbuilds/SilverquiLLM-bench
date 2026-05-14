"""Audited tests for FDN 30 — Archmage of Runes."""

from __future__ import annotations

from card_impl import ArchmageOfRunes
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, Zone
from tests.test_utils import create_game


class TestArchmageOfRunesBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = ArchmageOfRunes(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = ArchmageOfRunes(owner=None)
        assert card.name == "Archmage of Runes"

    def test_mana_cost(self) -> None:
        card = ArchmageOfRunes(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{U}{U}")

    def test_power_toughness(self) -> None:
        card = ArchmageOfRunes(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 6

    def test_subtypes(self) -> None:
        card = ArchmageOfRunes(owner=None)
        assert "Giant" in card.subtypes
        assert "Wizard" in card.subtypes


class TestArchmageSpellCastTrigger:
    """Whenever you cast an instant or sorcery spell, draw a card."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        archmage = ArchmageOfRunes(owner=p1, controller=p1)
        game.get_battlefield(p1).add(archmage)
        archmage.register_triggers(game)
        # Add cards to library so draw works
        for i in range(5):
            c = Creature(name=f"LibCard{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        return game, archmage, p1

    def test_draws_on_instant_cast(self) -> None:
        from engine.triggers import EventType
        game, archmage, p1 = self._setup()
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        spell = Instant(name="Bolt", owner=p1, controller=p1)
        game.trigger_manager.fire_event(
            game, EventType.SPELL_CAST, {"player": p1, "spell": spell},
        )
        self._resolve_stack(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        assert hand_after == hand_before + 1

    def test_does_not_draw_on_creature_cast(self) -> None:
        from engine.triggers import EventType
        game, archmage, p1 = self._setup()
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.trigger_manager.fire_event(
            game, EventType.SPELL_CAST, {"player": p1, "spell": creature},
        )
        self._resolve_stack(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        assert hand_after == hand_before

    def test_does_not_trigger_for_opponent_spell(self) -> None:
        from engine.triggers import EventType
        game, archmage, p1 = self._setup()
        p2 = game.players[1]
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        spell = Instant(name="Opp Spell", owner=p2, controller=p2)
        game.trigger_manager.fire_event(
            game, EventType.SPELL_CAST, {"player": p2, "spell": spell},
        )
        self._resolve_stack(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        assert hand_after == hand_before
