"""Audited tests for FDN 168 — Witness Protection."""

from __future__ import annotations

import pytest

from card_impl import WitnessProtection
from engine.card import Aura, Creature
from engine.continuous_effects import Layer, SubLayer
from engine.types import CardType, Color, Keyword, ManaCost
from test_utils import create_game


class TestWitnessProtectionBasics:
    """Basic properties of the card."""

    def test_is_aura(self) -> None:
        card = WitnessProtection(owner=None)
        assert isinstance(card, Aura)

    def test_mana_cost_is_U(self) -> None:
        card = WitnessProtection(owner=None)
        assert card.mana_cost == ManaCost.parse("{U}")

    def test_name(self) -> None:
        card = WitnessProtection(owner=None)
        assert card.name == "Witness Protection"


class TestWitnessProtectionEffect:
    """Continuous effect: name, types, colors, P/T, ability removal."""

    def _setup_attached(self):
        game = create_game()
        p1 = game.players[0]
        creature = Creature(
            name="Dragon",
            base_power=5,
            base_toughness=5,
            owner=p1,
            controller=p1,
            keywords=Keyword.FLYING | Keyword.TRAMPLE,
            subtypes={"Dragon"},
        )
        aura = WitnessProtection(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(creature)
        bf.add(aura)
        aura.chosen_targets = [creature]
        aura.on_resolve(game)
        return game, aura, creature

    def test_name_becomes_legitimate_businessperson(self) -> None:
        game, aura, creature = self._setup_attached()
        game.effect_manager.apply_all(game)
        assert creature.name == "Legitimate Businessperson"

    def test_becomes_creature_type_only(self) -> None:
        game, aura, creature = self._setup_attached()
        game.effect_manager.apply_all(game)
        assert CardType.CREATURE in creature.card_types

    def test_subtype_becomes_citizen(self) -> None:
        game, aura, creature = self._setup_attached()
        game.effect_manager.apply_all(game)
        assert "Citizen" in creature.subtypes
        # Loses old subtypes
        assert "Dragon" not in creature.subtypes

    def test_colors_become_green_white(self) -> None:
        game, aura, creature = self._setup_attached()
        game.effect_manager.apply_all(game)
        colors = getattr(creature, "colors", set())
        assert Color.GREEN in colors
        assert Color.WHITE in colors
        # Should have exactly these two colors
        assert len(colors) == 2

    def test_loses_all_abilities(self) -> None:
        game, aura, creature = self._setup_attached()
        game.effect_manager.apply_all(game)
        assert Keyword.FLYING not in creature.keywords
        assert Keyword.TRAMPLE not in creature.keywords

    def test_base_power_becomes_1(self) -> None:
        game, aura, creature = self._setup_attached()
        game.effect_manager.apply_all(game)
        assert creature.modified_power == 1

    def test_base_toughness_becomes_1(self) -> None:
        game, aura, creature = self._setup_attached()
        game.effect_manager.apply_all(game)
        assert creature.modified_toughness == 1

    def test_type_effect_in_layer_4(self) -> None:
        game, aura, creature = self._setup_attached()
        effects = game.effect_manager.get_effects_by_source(aura)
        type_effects = [e for e in effects if e.layer == Layer.TYPE]
        assert len(type_effects) >= 1

    def test_color_effect_in_layer_5(self) -> None:
        game, aura, creature = self._setup_attached()
        effects = game.effect_manager.get_effects_by_source(aura)
        color_effects = [e for e in effects if e.layer == Layer.COLOR]
        assert len(color_effects) >= 1

    def test_ability_effect_in_layer_6(self) -> None:
        game, aura, creature = self._setup_attached()
        effects = game.effect_manager.get_effects_by_source(aura)
        ability_effects = [e for e in effects if e.layer == Layer.ABILITY]
        assert len(ability_effects) >= 1

    def test_pt_effect_in_layer_7b(self) -> None:
        game, aura, creature = self._setup_attached()
        effects = game.effect_manager.get_effects_by_source(aura)
        pt_effects = [e for e in effects if e.layer == Layer.POWER_TOUGHNESS and e.sublayer == SubLayer.SET_PT]
        assert len(pt_effects) >= 1

    def test_effect_idempotent_on_reapply(self) -> None:
        game, aura, creature = self._setup_attached()
        game.effect_manager.apply_all(game)
        game.effect_manager.apply_all(game)
        assert creature.modified_power == 1
        assert creature.modified_toughness == 1
        assert creature.name == "Legitimate Businessperson"

