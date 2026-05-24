"""Audited tests for FDN 156 — Imprisoned in the Moon."""

from __future__ import annotations

import pytest

from card_impl import ImprisonedInTheMoon
from benchmarks.sos.workspace.engine.card import Aura, Creature, Land
from benchmarks.sos.workspace.engine.continuous_effects import Layer
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestImprisonedBasics:
    """Basic properties of the card."""

    def test_is_aura(self) -> None:
        card = ImprisonedInTheMoon(owner=None)
        assert isinstance(card, Aura)

    def test_mana_cost_is_2U(self) -> None:
        card = ImprisonedInTheMoon(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{U}")

    def test_name(self) -> None:
        card = ImprisonedInTheMoon(owner=None)
        assert card.name == "Imprisoned in the Moon"


class TestImprisonedTargeting:
    """Targets creatures, lands, or planeswalkers."""

    def test_can_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(creature)
        aura = ImprisonedInTheMoon(owner=p1, controller=p1)
        targets = aura.get_targets(game)
        assert len(targets) > 0

    def test_can_target_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = Land(name="Forest", owner=p1, controller=p1)
        game.get_battlefield(p1).add(land)
        aura = ImprisonedInTheMoon(owner=p1, controller=p1)
        targets = aura.get_targets(game)
        assert len(targets) > 0


class TestImprisonedEffect:
    """Continuous effect: becomes colorless land, loses types/abilities."""

    def _setup_attached_creature(self):
        game = create_game()
        p1 = game.players[0]
        creature = Creature(
            name="Dragon",
            base_power=5,
            base_toughness=5,
            owner=p1,
            controller=p1,
            keywords=Keyword.FLYING,
        )
        aura = ImprisonedInTheMoon(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(creature)
        bf.add(aura)
        aura.chosen_targets = [creature]
        aura.on_resolve(game)
        return game, aura, creature

    def test_enchanted_becomes_land(self) -> None:
        game, aura, creature = self._setup_attached_creature()
        game.effect_manager.apply_all(game)
        assert CardType.LAND in creature.card_types

    def test_enchanted_loses_creature_type(self) -> None:
        game, aura, creature = self._setup_attached_creature()
        game.effect_manager.apply_all(game)
        assert CardType.CREATURE not in creature.card_types

    def test_enchanted_loses_all_abilities(self) -> None:
        game, aura, creature = self._setup_attached_creature()
        game.effect_manager.apply_all(game)
        assert Keyword.FLYING not in creature.keywords

    def test_enchanted_becomes_colorless(self) -> None:
        game, aura, creature = self._setup_attached_creature()
        game.effect_manager.apply_all(game)
        colors = getattr(creature, "colors", set())
        assert colors == set()

    def test_enchanted_loses_subtypes(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = Creature(
            name="Elf",
            base_power=1,
            base_toughness=1,
            owner=p1,
            controller=p1,
            subtypes={"Elf", "Warrior"},
        )
        aura = ImprisonedInTheMoon(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(creature)
        bf.add(aura)
        aura.chosen_targets = [creature]
        aura.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert creature.subtypes == set()

    def test_type_effect_in_layer_4(self) -> None:
        game, aura, creature = self._setup_attached_creature()
        effects = game.effect_manager.get_effects_by_source(aura)
        type_effects = [e for e in effects if e.layer == Layer.TYPE]
        assert len(type_effects) >= 1

    def test_ability_effect_in_layer_6(self) -> None:
        game, aura, creature = self._setup_attached_creature()
        effects = game.effect_manager.get_effects_by_source(aura)
        ability_effects = [e for e in effects if e.layer == Layer.ABILITY]
        assert len(ability_effects) >= 1

    def test_on_resolve_with_invalid_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        aura = ImprisonedInTheMoon(owner=p1, controller=p1)
        game.get_battlefield(p1).add(aura)
        # creature NOT on battlefield
        aura.chosen_targets = [creature]
        aura.on_resolve(game)
        assert aura.attached_to is None or aura.attached_to is not creature

