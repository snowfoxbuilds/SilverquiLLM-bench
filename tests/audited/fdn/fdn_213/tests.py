"""Audited tests for FDN 213 — Blanchwood Armor."""

from __future__ import annotations

import pytest

from card_impl import BlanchwoodArmor
from engine.card import Aura, Creature, Land
from engine.continuous_effects import Layer, SubLayer
from engine.types import CardType, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestBlanchwoodArmorBasics:
    """Basic properties of the card."""

    def test_is_aura(self) -> None:
        card = BlanchwoodArmor(owner=None)
        assert isinstance(card, Aura)

    def test_mana_cost_is_2G(self) -> None:
        card = BlanchwoodArmor(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{G}")

    def test_name(self) -> None:
        card = BlanchwoodArmor(owner=None)
        assert card.name == "Blanchwood Armor"


class TestBlanchwoodArmorEffect:
    """Continuous effect: +1/+1 per Forest you control."""

    def _make_forest(self, owner):
        """Create a Forest land."""
        return Land(name="Forest", owner=owner, controller=owner, subtypes={"Forest"})

    def _setup_with_forests(self, num_forests: int):
        """Create game with creature enchanted by Blanchwood Armor and N forests."""
        game = create_game()
        p1 = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        aura = BlanchwoodArmor(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(creature)
        bf.add(aura)
        for _ in range(num_forests):
            bf.add(self._make_forest(p1))
        aura.chosen_targets = [creature]
        aura.on_resolve(game)
        return game, aura, creature

    def test_no_forests_no_bonus(self) -> None:
        game, aura, creature = self._setup_with_forests(0)
        game.effect_manager.apply_all(game)
        assert creature.base_power == 2
        assert creature.base_toughness == 2

    def test_one_forest_plus_one(self) -> None:
        game, aura, creature = self._setup_with_forests(1)
        game.effect_manager.apply_all(game)
        assert creature.modified_power == 3
        assert creature.modified_toughness == 3

    def test_three_forests_plus_three(self) -> None:
        game, aura, creature = self._setup_with_forests(3)
        game.effect_manager.apply_all(game)
        assert creature.modified_power == 5
        assert creature.modified_toughness == 5

    def test_opponent_forests_not_counted(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        aura = BlanchwoodArmor(owner=p1, controller=p1)
        bf1 = game.get_battlefield(p1)
        bf2 = game.get_battlefield(p2)
        bf1.add(creature)
        bf1.add(aura)
        # 1 forest for p1, 3 for p2
        bf1.add(self._make_forest(p1))
        for _ in range(3):
            bf2.add(Land(name="Forest", owner=p2, controller=p2, subtypes={"Forest"}))
        aura.chosen_targets = [creature]
        aura.on_resolve(game)
        game.effect_manager.apply_all(game)
        # Should only get +1 from p1's single forest
        assert creature.modified_power == 3
        assert creature.modified_toughness == 3

    def test_effect_in_layer_7c(self) -> None:
        game, aura, creature = self._setup_with_forests(1)
        effects = game.effect_manager.get_effects_by_source(aura)
        pt_effects = [e for e in effects if e.layer == Layer.POWER_TOUGHNESS and e.sublayer == SubLayer.MODIFY_PT]
        assert len(pt_effects) == 1

    def test_dynamic_bonus_updates_when_forest_added(self) -> None:
        """Bonus should reflect current forest count on reapply."""
        game, aura, creature = self._setup_with_forests(1)
        game.effect_manager.apply_all(game)
        assert creature.modified_power == 3
        # Add another forest
        p1 = game.players[0]
        game.get_battlefield(p1).add(self._make_forest(p1))
        game.effect_manager.apply_all(game)
        assert creature.modified_power == 4
        assert creature.modified_toughness == 4

    def test_effect_idempotent_on_reapply(self) -> None:
        """Calling apply_all twice doesn't double the bonus."""
        game, aura, creature = self._setup_with_forests(2)
        game.effect_manager.apply_all(game)
        game.effect_manager.apply_all(game)
        assert creature.modified_power == 4
        assert creature.modified_toughness == 4

    def test_counts_forest_subtype_not_name(self) -> None:
        """A land with Forest subtype but different name should count."""
        game = create_game()
        p1 = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        aura = BlanchwoodArmor(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(creature)
        bf.add(aura)
        # A dual land with Forest subtype
        dual = Land(name="Tropical Island", owner=p1, controller=p1, subtypes={"Forest", "Island"})
        bf.add(dual)
        aura.chosen_targets = [creature]
        aura.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert creature.modified_power == 3
        assert creature.modified_toughness == 3

