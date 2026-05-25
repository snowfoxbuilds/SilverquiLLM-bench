"""Audited tests for FDN 26 — Twinblade Blessing."""

from __future__ import annotations

import pytest

from card_impl import TwinbladeBlessing
from benchmarks.sos.workspace.engine.card import Aura, Creature
from benchmarks.sos.workspace.engine.continuous_effects import Layer
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestTwinblessingBasics:
    """Basic properties of the card."""

    def test_is_aura(self) -> None:
        card = TwinbladeBlessing(owner=None)
        assert isinstance(card, Aura)
        assert card.is_aura is True

    def test_mana_cost_is_1WW(self) -> None:
        card = TwinbladeBlessing(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_has_flash_keyword(self) -> None:
        card = TwinbladeBlessing(owner=None)
        assert Keyword.FLASH in card.keywords

    def test_name(self) -> None:
        card = TwinbladeBlessing(owner=None)
        assert card.name == "Twinblade Blessing"

    def test_has_aura_subtype(self) -> None:
        card = TwinbladeBlessing(owner=None)
        assert "Aura" in card.subtypes


class TestTwinblessingEffect:
    """Continuous effect granting double strike."""

    def _setup_attached(self):
        """Create a game with Twinblade Blessing attached to a creature."""
        game = create_game()
        p1 = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        aura = TwinbladeBlessing(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(creature)
        bf.add(aura)
        aura.attached_to = creature
        aura.chosen_targets = [creature]
        aura._register_effect(game)
        return game, aura, creature

    def test_grants_double_strike_after_apply_all(self) -> None:
        game, aura, creature = self._setup_attached()
        game.effect_manager.apply_all(game)
        assert Keyword.DOUBLE_STRIKE in creature.keywords

    def test_effect_registered_in_layer_6(self) -> None:
        game, aura, creature = self._setup_attached()
        effects = game.effect_manager.get_effects_by_source(aura)
        assert len(effects) >= 1
        layer6_effects = [e for e in effects if e.layer == Layer.ABILITY]
        assert len(layer6_effects) == 1

    def test_creature_without_aura_no_double_strike(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(creature)
        game.effect_manager.apply_all(game)
        assert Keyword.DOUBLE_STRIKE not in creature.keywords

    def test_effect_idempotent_on_reapply(self) -> None:
        """Calling apply_all multiple times doesn't stack double strike."""
        game, aura, creature = self._setup_attached()
        game.effect_manager.apply_all(game)
        game.effect_manager.apply_all(game)
        assert Keyword.DOUBLE_STRIKE in creature.keywords

    def test_on_resolve_attaches_to_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        aura = TwinbladeBlessing(owner=p1, controller=p1)
        game.get_battlefield(p1).add(creature)
        game.get_battlefield(p1).add(aura)
        aura.chosen_targets = [creature]
        aura.on_resolve(game)
        assert aura.attached_to is creature

    def test_on_resolve_registers_effect(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        aura = TwinbladeBlessing(owner=p1, controller=p1)
        game.get_battlefield(p1).add(creature)
        game.get_battlefield(p1).add(aura)
        aura.chosen_targets = [creature]
        aura.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.DOUBLE_STRIKE in creature.keywords

    def test_on_resolve_with_invalid_target_does_not_attach(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        aura = TwinbladeBlessing(owner=p1, controller=p1)
        # creature not on battlefield
        game.get_battlefield(p1).add(aura)
        aura.chosen_targets = [creature]
        aura.on_resolve(game)
        assert aura.attached_to is None or aura.attached_to is not creature

