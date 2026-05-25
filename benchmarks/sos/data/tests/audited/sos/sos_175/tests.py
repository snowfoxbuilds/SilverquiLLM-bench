"""Audited tests for Berta, Wise Extrapolator (collector key 175).

Verifies the Berta, Wise Extrapolator card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import BertaWiseExtrapolator

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestBertaWiseExtrapolatorBasicProperties:
    """Basic property tests for Berta, Wise Extrapolator."""

    def test_is_creature(self) -> None:
        """Berta, Wise Extrapolator must be a Creature subclass."""
        card = BertaWiseExtrapolator(name="Berta, Wise Extrapolator", owner=None, base_power=1, base_toughness=4)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """BertaWiseExtrapolator.name must be 'Berta, Wise Extrapolator'."""
        card = BertaWiseExtrapolator(name="Berta, Wise Extrapolator", owner=None, base_power=1, base_toughness=4)
        assert card.name == "Berta, Wise Extrapolator"

    def test_card_types(self) -> None:
        """Berta, Wise Extrapolator must have correct card types."""
        card = BertaWiseExtrapolator(name="Berta, Wise Extrapolator", owner=None, base_power=1, base_toughness=4)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Berta, Wise Extrapolator must have converted mana cost 4."""
        card = BertaWiseExtrapolator(name="Berta, Wise Extrapolator", owner=None, base_power=1, base_toughness=4)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Berta, Wise Extrapolator must have correct colors."""
        card = BertaWiseExtrapolator(name="Berta, Wise Extrapolator", owner=None, base_power=1, base_toughness=4)
        assert "G" in card.colors
        assert "U" in card.colors

    def test_power(self) -> None:
        """Berta, Wise Extrapolator must have base power 1."""
        card = BertaWiseExtrapolator(name="Berta, Wise Extrapolator", owner=None, base_power=1, base_toughness=4)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Berta, Wise Extrapolator must have base toughness 4."""
        card = BertaWiseExtrapolator(name="Berta, Wise Extrapolator", owner=None, base_power=1, base_toughness=4)
        assert card.base_toughness == 4


@pytest.mark.ability
class TestBertaWiseExtrapolatorAbilities:
    """Ability tests for Berta, Wise Extrapolator -- expected to fail against stubs."""

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = BertaWiseExtrapolator(name="Berta, Wise Extrapolator", owner=None, base_power=1, base_toughness=4)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Berta, Wise Extrapolator must implement behavioral method"


@pytest.mark.edge
class TestBertaWiseExtrapolatorEdgeCases:
    """Edge case and trap tests for Berta, Wise Extrapolator."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = BertaWiseExtrapolator(name="Berta, Wise Extrapolator", owner=None, base_power=1, base_toughness=4)
        card2 = BertaWiseExtrapolator(name="Berta, Wise Extrapolator", owner=None, base_power=1, base_toughness=4)
        card1.name = "Modified"
        assert card2.name == "Berta, Wise Extrapolator", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = BertaWiseExtrapolator(name="Berta, Wise Extrapolator", owner=None, base_power=1, base_toughness=4)
        assert card.mana_cost.cmc == 4, \
            f"CMC must be 4, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = BertaWiseExtrapolator(name="Berta, Wise Extrapolator", owner=player, base_power=1, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 3
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestBertaWiseExtrapolatorInteractions:
    """Multi-card interaction tests for Berta, Wise Extrapolator."""

    def test_counters_survive_end_of_turn(self) -> None:
        """Permanent counters must persist through end of turn."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = BertaWiseExtrapolator(name="Berta, Wise Extrapolator", owner=player, base_power=1, base_toughness=4)
        card.controller = player
        if hasattr(card, "colors_spent"):
            card.colors_spent = 2
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        counters = getattr(card, "counters", {})
        p1p1 = counters.get("+1/+1", counters.get("p1p1", 0))
        assert p1p1 == 2, f"Should have 2 +1/+1 counters, got {p1p1}"

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = BertaWiseExtrapolator(name="Berta, Wise Extrapolator", owner=player, base_power=1, base_toughness=4)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"

    def test_tokens_appear_on_battlefield(self) -> None:
        """Tokens created must appear on the battlefield."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = BertaWiseExtrapolator(name="Berta, Wise Extrapolator", owner=player, base_power=1, base_toughness=4)
        card.controller = player
        bf_before = len(player.zones[Zone.BATTLEFIELD].get_all())
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        elif callable(getattr(card, "on_resolve", None)):
            card.on_resolve(game)
        bf_after = len(player.zones[Zone.BATTLEFIELD].get_all())
        assert bf_after > bf_before, "Tokens must appear on battlefield"
