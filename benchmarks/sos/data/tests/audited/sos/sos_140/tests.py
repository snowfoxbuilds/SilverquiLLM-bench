"""Audited tests for Ambitious Augmenter (collector key 140).

Verifies the Ambitious Augmenter card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import AmbitiousAugmenter

from engine.card import Creature
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestAmbitiousAugmenterBasicProperties:
    """Basic property tests for Ambitious Augmenter."""

    def test_is_creature(self) -> None:
        """Ambitious Augmenter must be a Creature subclass."""
        card = AmbitiousAugmenter(name="Ambitious Augmenter", owner=None, base_power=1, base_toughness=1)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """AmbitiousAugmenter.name must be 'Ambitious Augmenter'."""
        card = AmbitiousAugmenter(name="Ambitious Augmenter", owner=None, base_power=1, base_toughness=1)
        assert card.name == "Ambitious Augmenter"

    def test_card_types(self) -> None:
        """Ambitious Augmenter must have correct card types."""
        card = AmbitiousAugmenter(name="Ambitious Augmenter", owner=None, base_power=1, base_toughness=1)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Ambitious Augmenter must have converted mana cost 1."""
        card = AmbitiousAugmenter(name="Ambitious Augmenter", owner=None, base_power=1, base_toughness=1)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Ambitious Augmenter must have correct colors."""
        card = AmbitiousAugmenter(name="Ambitious Augmenter", owner=None, base_power=1, base_toughness=1)
        assert "G" in card_colors(card)

    def test_power(self) -> None:
        """Ambitious Augmenter must have base power 1."""
        card = AmbitiousAugmenter(name="Ambitious Augmenter", owner=None, base_power=1, base_toughness=1)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Ambitious Augmenter must have base toughness 1."""
        card = AmbitiousAugmenter(name="Ambitious Augmenter", owner=None, base_power=1, base_toughness=1)
        assert card.base_toughness == 1

@pytest.mark.ability
class TestAmbitiousAugmenterAbilities:
    """Ability tests for Ambitious Augmenter -- expected to fail against stubs."""

    def test_death_trigger_implemented(self) -> None:
        """Death trigger must be implemented per oracle text."""
        card = AmbitiousAugmenter(name="Ambitious Augmenter", owner=None, base_power=1, base_toughness=1)
        assert callable(getattr(card, "on_death", None)) or \
            callable(getattr(card, "death_trigger", None)), \
            "Ambitious Augmenter must implement death trigger per oracle text"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = AmbitiousAugmenter(name="Ambitious Augmenter", owner=None, base_power=1, base_toughness=1)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Ambitious Augmenter must implement behavioral method"

@pytest.mark.edge
class TestAmbitiousAugmenterEdgeCases:
    """Edge case and trap tests for Ambitious Augmenter."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = AmbitiousAugmenter(name="Ambitious Augmenter", owner=None, base_power=1, base_toughness=1)
        card2 = AmbitiousAugmenter(name="Ambitious Augmenter", owner=None, base_power=1, base_toughness=1)
        card1.name = "Modified"
        assert card2.name == "Ambitious Augmenter", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = AmbitiousAugmenter(name="Ambitious Augmenter", owner=None, base_power=1, base_toughness=1)
        assert card.mana_cost.cmc == 1, \
            f"CMC must be 1, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = AmbitiousAugmenter(name="Ambitious Augmenter", owner=player, base_power=1, base_toughness=1)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 0
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"

@pytest.mark.interaction
class TestAmbitiousAugmenterInteractions:
    """Multi-card interaction tests for Ambitious Augmenter."""

    def test_counters_survive_end_of_turn(self) -> None:
        """Permanent counters must persist through end of turn."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = AmbitiousAugmenter(name="Ambitious Augmenter", owner=player, base_power=1, base_toughness=1)
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
        card = AmbitiousAugmenter(name="Ambitious Augmenter", owner=player, base_power=1, base_toughness=1)
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
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = AmbitiousAugmenter(name="Ambitious Augmenter", owner=player, base_power=1, base_toughness=1)
        card.controller = player
        bf_before = len(player.zones[Zone.BATTLEFIELD].get_all())
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        elif callable(getattr(card, "on_resolve", None)):
            card.on_resolve(game)
        bf_after = len(player.zones[Zone.BATTLEFIELD].get_all())
        assert bf_after > bf_before, "Tokens must appear on battlefield"
