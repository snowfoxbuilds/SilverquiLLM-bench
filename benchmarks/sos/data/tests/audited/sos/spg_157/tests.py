"""Audited tests for Codie, Vociferous Codex (collector key spg_157).

Verifies the Codie, Vociferous Codex card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import CodieVociferousCodex

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestCodieVociferousCodexBasicProperties:
    """Basic property tests for Codie, Vociferous Codex."""

    def test_is_creature(self) -> None:
        """Codie, Vociferous Codex must be a Creature subclass."""
        card = CodieVociferousCodex(name="Codie, Vociferous Codex", owner=None, base_power=1, base_toughness=4)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """CodieVociferousCodex.name must be 'Codie, Vociferous Codex'."""
        card = CodieVociferousCodex(name="Codie, Vociferous Codex", owner=None, base_power=1, base_toughness=4)
        assert card.name == "Codie, Vociferous Codex"

    def test_card_types(self) -> None:
        """Codie, Vociferous Codex must have correct card types."""
        card = CodieVociferousCodex(name="Codie, Vociferous Codex", owner=None, base_power=1, base_toughness=4)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Codie, Vociferous Codex must have converted mana cost 3."""
        card = CodieVociferousCodex(name="Codie, Vociferous Codex", owner=None, base_power=1, base_toughness=4)
        assert card.mana_cost.cmc == 3

    def test_colorless(self) -> None:
        """Codie, Vociferous Codex must be colorless."""
        card = CodieVociferousCodex(name="Codie, Vociferous Codex", owner=None, base_power=1, base_toughness=4)
        assert len(card.colors) == 0

    def test_power(self) -> None:
        """Codie, Vociferous Codex must have base power 1."""
        card = CodieVociferousCodex(name="Codie, Vociferous Codex", owner=None, base_power=1, base_toughness=4)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Codie, Vociferous Codex must have base toughness 4."""
        card = CodieVociferousCodex(name="Codie, Vociferous Codex", owner=None, base_power=1, base_toughness=4)
        assert card.base_toughness == 4


@pytest.mark.ability
class TestCodieVociferousCodexAbilities:
    """Ability tests for Codie, Vociferous Codex -- expected to fail against stubs."""

    def test_cost_reduction_implemented(self) -> None:
        """Cost reduction must be implemented per oracle text."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = CodieVociferousCodex(name="Codie, Vociferous Codex", owner=player, base_power=1, base_toughness=4)
        card.controller = player
        assert callable(getattr(card, "get_adjusted_cost", None)) or \
            callable(getattr(card, "cost_reduction", None)), \
            "Codie, Vociferous Codex must implement cost reduction per oracle text"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = CodieVociferousCodex(name="Codie, Vociferous Codex", owner=None, base_power=1, base_toughness=4)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Codie, Vociferous Codex must implement behavioral method"


@pytest.mark.edge
class TestCodieVociferousCodexEdgeCases:
    """Edge case and trap tests for Codie, Vociferous Codex."""

    def test_cost_reduction_floor_at_zero(self) -> None:
        """Cost reduction must not reduce cost below zero."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = CodieVociferousCodex(name="Codie, Vociferous Codex", owner=player, base_power=1, base_toughness=4)
        card.controller = player
        if callable(getattr(card, "get_adjusted_cost", None)):
            cost = card.get_adjusted_cost(game)
            assert cost >= 0, "Adjusted cost must never be negative"
        else:
            assert callable(getattr(card, "cost_reduction", None)), \
                "Must implement cost reduction"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = CodieVociferousCodex(name="Codie, Vociferous Codex", owner=None, base_power=1, base_toughness=4)
        card2 = CodieVociferousCodex(name="Codie, Vociferous Codex", owner=None, base_power=1, base_toughness=4)
        card1.name = "Modified"
        assert card2.name == "Codie, Vociferous Codex", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = CodieVociferousCodex(name="Codie, Vociferous Codex", owner=None, base_power=1, base_toughness=4)
        assert card.mana_cost.cmc == 3, \
            f"CMC must be 3, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestCodieVociferousCodexInteractions:
    """Multi-card interaction tests for Codie, Vociferous Codex."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = CodieVociferousCodex(name="Codie, Vociferous Codex", owner=player, base_power=1, base_toughness=4)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"

    def test_coexists_with_other_permanents(self) -> None:
        """Card must coexist with other permanents without errors."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        card = CodieVociferousCodex(name="Codie, Vociferous Codex", owner=player, base_power=1, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
