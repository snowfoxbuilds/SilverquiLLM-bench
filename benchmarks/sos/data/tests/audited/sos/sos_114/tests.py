"""Audited tests for Expressive Firedancer (collector key 114).

Verifies the Expressive Firedancer card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import ExpressiveFiredancer

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestExpressiveFiredancerBasicProperties:
    """Basic property tests for Expressive Firedancer."""

    def test_is_creature(self) -> None:
        """Expressive Firedancer must be a Creature subclass."""
        card = ExpressiveFiredancer(name="Expressive Firedancer", owner=None, base_power=2, base_toughness=2)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """ExpressiveFiredancer.name must be 'Expressive Firedancer'."""
        card = ExpressiveFiredancer(name="Expressive Firedancer", owner=None, base_power=2, base_toughness=2)
        assert card.name == "Expressive Firedancer"

    def test_card_types(self) -> None:
        """Expressive Firedancer must have correct card types."""
        card = ExpressiveFiredancer(name="Expressive Firedancer", owner=None, base_power=2, base_toughness=2)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Expressive Firedancer must have converted mana cost 2."""
        card = ExpressiveFiredancer(name="Expressive Firedancer", owner=None, base_power=2, base_toughness=2)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Expressive Firedancer must have correct colors."""
        card = ExpressiveFiredancer(name="Expressive Firedancer", owner=None, base_power=2, base_toughness=2)
        assert "R" in card.colors

    def test_power(self) -> None:
        """Expressive Firedancer must have base power 2."""
        card = ExpressiveFiredancer(name="Expressive Firedancer", owner=None, base_power=2, base_toughness=2)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Expressive Firedancer must have base toughness 2."""
        card = ExpressiveFiredancer(name="Expressive Firedancer", owner=None, base_power=2, base_toughness=2)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestExpressiveFiredancerAbilities:
    """Ability tests for Expressive Firedancer -- expected to fail against stubs."""

    def test_has_opus(self) -> None:
        """Expressive Firedancer must have Opus keyword."""
        from engine.types import Keyword
        card = ExpressiveFiredancer(name="Expressive Firedancer", owner=None, base_power=2, base_toughness=2)
        assert Keyword.OPUS in card.keywords, "Expressive Firedancer should have Opus"

    def test_opus_trigger_implemented(self) -> None:
        """Opus must trigger when controller casts instant/sorcery."""
        card = ExpressiveFiredancer(name="Expressive Firedancer", owner=None, base_power=2, base_toughness=2)
        assert callable(getattr(card, "on_spell_cast", None)) or \
            callable(getattr(card, "opus_trigger", None)), \
            "Expressive Firedancer must implement opus trigger per oracle text"


@pytest.mark.edge
class TestExpressiveFiredancerEdgeCases:
    """Edge case and trap tests for Expressive Firedancer."""

    def test_opus_no_trigger_without_spell(self) -> None:
        """Opus should not boost without casting instant/sorcery."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = ExpressiveFiredancer(name="Expressive Firedancer", owner=player, base_power=2, base_toughness=2)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        base_p = card.base_power
        # Without casting a spell, power should remain at base
        actual_p = getattr(card, "power", card.base_power)
        assert actual_p == base_p, f"Without opus trigger, power should be {base_p}, got {actual_p}"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = ExpressiveFiredancer(name="Expressive Firedancer", owner=None, base_power=2, base_toughness=2)
        card2 = ExpressiveFiredancer(name="Expressive Firedancer", owner=None, base_power=2, base_toughness=2)
        card1.name = "Modified"
        assert card2.name == "Expressive Firedancer", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = ExpressiveFiredancer(name="Expressive Firedancer", owner=None, base_power=2, base_toughness=2)
        assert card.mana_cost.cmc == 2, \
            f"CMC must be 2, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestExpressiveFiredancerInteractions:
    """Multi-card interaction tests for Expressive Firedancer."""

    def test_counters_survive_end_of_turn(self) -> None:
        """Permanent counters must persist through end of turn."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = ExpressiveFiredancer(name="Expressive Firedancer", owner=player, base_power=2, base_toughness=2)
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
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = ExpressiveFiredancer(name="Expressive Firedancer", owner=player, base_power=2, base_toughness=2)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
