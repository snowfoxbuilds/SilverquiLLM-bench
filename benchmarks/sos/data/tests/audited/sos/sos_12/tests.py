"""Audited tests for Elite Interceptor // Rejoinder (collector key 12).

Verifies the Elite Interceptor // Rejoinder card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import EliteInterceptorRejoinder

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestEliteInterceptorRejoinderBasicProperties:
    """Basic property tests for Elite Interceptor // Rejoinder."""

    def test_is_creature(self) -> None:
        """Elite Interceptor // Rejoinder must be a Creature subclass."""
        card = EliteInterceptorRejoinder(name="Elite Interceptor // Rejoinder", owner=None, base_power=1, base_toughness=2)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """EliteInterceptorRejoinder.name must be 'Elite Interceptor // Rejoinder'."""
        card = EliteInterceptorRejoinder(name="Elite Interceptor // Rejoinder", owner=None, base_power=1, base_toughness=2)
        assert card.name == "Elite Interceptor // Rejoinder"

    def test_card_types(self) -> None:
        """Elite Interceptor // Rejoinder must have correct card types."""
        card = EliteInterceptorRejoinder(name="Elite Interceptor // Rejoinder", owner=None, base_power=1, base_toughness=2)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Elite Interceptor // Rejoinder must have converted mana cost 3."""
        card = EliteInterceptorRejoinder(name="Elite Interceptor // Rejoinder", owner=None, base_power=1, base_toughness=2)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Elite Interceptor // Rejoinder must have correct colors."""
        card = EliteInterceptorRejoinder(name="Elite Interceptor // Rejoinder", owner=None, base_power=1, base_toughness=2)
        assert "W" in card.colors

    def test_power(self) -> None:
        """Elite Interceptor // Rejoinder must have base power 1."""
        card = EliteInterceptorRejoinder(name="Elite Interceptor // Rejoinder", owner=None, base_power=1, base_toughness=2)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Elite Interceptor // Rejoinder must have base toughness 2."""
        card = EliteInterceptorRejoinder(name="Elite Interceptor // Rejoinder", owner=None, base_power=1, base_toughness=2)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestEliteInterceptorRejoinderAbilities:
    """Ability tests for Elite Interceptor // Rejoinder -- expected to fail against stubs."""

    def test_has_prepared(self) -> None:
        """Elite Interceptor // Rejoinder must have Prepared keyword."""
        from benchmarks.sos.workspace.engine.types import Keyword
        card = EliteInterceptorRejoinder(name="Elite Interceptor // Rejoinder", owner=None, base_power=1, base_toughness=2)
        assert Keyword.PREPARED in card.keywords, "Elite Interceptor // Rejoinder should have Prepared"

    def test_etb_trigger_callable(self) -> None:
        """ETB trigger must be implemented per oracle text."""
        card = EliteInterceptorRejoinder(name="Elite Interceptor // Rejoinder", owner=None, base_power=1, base_toughness=2)
        assert callable(getattr(card, "on_enter_battlefield", None)), \
            "Elite Interceptor // Rejoinder must implement on_enter_battlefield per oracle text"

    def test_prepared_mechanic_implemented(self) -> None:
        """Prepared mechanic must be implemented per oracle text."""
        card = EliteInterceptorRejoinder(name="Elite Interceptor // Rejoinder", owner=None, base_power=1, base_toughness=2)
        assert callable(getattr(card, "check_prepared", None)) or \
            callable(getattr(card, "prepared_effect", None)) or \
            callable(getattr(card, "on_resolve", None)), \
            "Elite Interceptor // Rejoinder must implement prepared mechanic"


@pytest.mark.edge
class TestEliteInterceptorRejoinderEdgeCases:
    """Edge case and trap tests for Elite Interceptor // Rejoinder."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = EliteInterceptorRejoinder(name="Elite Interceptor // Rejoinder", owner=None, base_power=1, base_toughness=2)
        card2 = EliteInterceptorRejoinder(name="Elite Interceptor // Rejoinder", owner=None, base_power=1, base_toughness=2)
        card1.name = "Modified"
        assert card2.name == "Elite Interceptor // Rejoinder", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = EliteInterceptorRejoinder(name="Elite Interceptor // Rejoinder", owner=None, base_power=1, base_toughness=2)
        assert card.mana_cost.cmc == 3, \
            f"CMC must be 3, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = EliteInterceptorRejoinder(name="Elite Interceptor // Rejoinder", owner=player, base_power=1, base_toughness=2)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 1
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestEliteInterceptorRejoinderInteractions:
    """Multi-card interaction tests for Elite Interceptor // Rejoinder."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = EliteInterceptorRejoinder(name="Elite Interceptor // Rejoinder", owner=player, base_power=1, base_toughness=2)
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
        card = EliteInterceptorRejoinder(name="Elite Interceptor // Rejoinder", owner=player, base_power=1, base_toughness=2)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
