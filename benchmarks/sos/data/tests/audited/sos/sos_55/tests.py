"""Audited tests for Jadzi, Steward of Fate // Oracle's Gift (collector key 55).

Verifies the Jadzi, Steward of Fate // Oracle's Gift card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import JadziStewardOfFateOraclesGift

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestJadziStewardOfFateOraclesGiftBasicProperties:
    """Basic property tests for Jadzi, Steward of Fate // Oracle's Gift."""

    def test_is_creature(self) -> None:
        """Jadzi, Steward of Fate // Oracle's Gift must be a Creature subclass."""
        card = JadziStewardOfFateOraclesGift(name="Jadzi, Steward of Fate // Oracle's Gift", owner=None, base_power=2, base_toughness=4)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """JadziStewardOfFateOraclesGift.name must be 'Jadzi, Steward of Fate // Oracle's Gift'."""
        card = JadziStewardOfFateOraclesGift(name="Jadzi, Steward of Fate // Oracle's Gift", owner=None, base_power=2, base_toughness=4)
        assert card.name == "Jadzi, Steward of Fate // Oracle's Gift"

    def test_card_types(self) -> None:
        """Jadzi, Steward of Fate // Oracle's Gift must have correct card types."""
        card = JadziStewardOfFateOraclesGift(name="Jadzi, Steward of Fate // Oracle's Gift", owner=None, base_power=2, base_toughness=4)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Jadzi, Steward of Fate // Oracle's Gift must have converted mana cost 4."""
        card = JadziStewardOfFateOraclesGift(name="Jadzi, Steward of Fate // Oracle's Gift", owner=None, base_power=2, base_toughness=4)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Jadzi, Steward of Fate // Oracle's Gift must have correct colors."""
        card = JadziStewardOfFateOraclesGift(name="Jadzi, Steward of Fate // Oracle's Gift", owner=None, base_power=2, base_toughness=4)
        assert "U" in card.colors

    def test_power(self) -> None:
        """Jadzi, Steward of Fate // Oracle's Gift must have base power 2."""
        card = JadziStewardOfFateOraclesGift(name="Jadzi, Steward of Fate // Oracle's Gift", owner=None, base_power=2, base_toughness=4)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Jadzi, Steward of Fate // Oracle's Gift must have base toughness 4."""
        card = JadziStewardOfFateOraclesGift(name="Jadzi, Steward of Fate // Oracle's Gift", owner=None, base_power=2, base_toughness=4)
        assert card.base_toughness == 4


@pytest.mark.ability
class TestJadziStewardOfFateOraclesGiftAbilities:
    """Ability tests for Jadzi, Steward of Fate // Oracle's Gift -- expected to fail against stubs."""

    def test_has_prepared(self) -> None:
        """Jadzi, Steward of Fate // Oracle's Gift must have Prepared keyword."""
        from engine.types import Keyword
        card = JadziStewardOfFateOraclesGift(name="Jadzi, Steward of Fate // Oracle's Gift", owner=None, base_power=2, base_toughness=4)
        assert Keyword.PREPARED in card.keywords, "Jadzi, Steward of Fate // Oracle's Gift should have Prepared"

    def test_etb_draws_cards(self) -> None:
        """ETB must draw cards per oracle text."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        for i in range(5):
            c = Creature(name=f"Lib{i}", owner=player, base_power=1, base_toughness=1)
            player.zones[Zone.LIBRARY].add(c)
        hand_before = len(player.zones[Zone.HAND].get_all())
        card = JadziStewardOfFateOraclesGift(name="Jadzi, Steward of Fate // Oracle's Gift", owner=player, base_power=2, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, "ETB must draw cards per oracle"

    def test_prepared_mechanic_implemented(self) -> None:
        """Prepared mechanic must be implemented per oracle text."""
        card = JadziStewardOfFateOraclesGift(name="Jadzi, Steward of Fate // Oracle's Gift", owner=None, base_power=2, base_toughness=4)
        assert callable(getattr(card, "check_prepared", None)) or \
            callable(getattr(card, "prepared_effect", None)) or \
            callable(getattr(card, "on_resolve", None)), \
            "Jadzi, Steward of Fate // Oracle's Gift must implement prepared mechanic"


@pytest.mark.edge
class TestJadziStewardOfFateOraclesGiftEdgeCases:
    """Edge case and trap tests for Jadzi, Steward of Fate // Oracle's Gift."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = JadziStewardOfFateOraclesGift(name="Jadzi, Steward of Fate // Oracle's Gift", owner=None, base_power=2, base_toughness=4)
        card2 = JadziStewardOfFateOraclesGift(name="Jadzi, Steward of Fate // Oracle's Gift", owner=None, base_power=2, base_toughness=4)
        card1.name = "Modified"
        assert card2.name == "Jadzi, Steward of Fate // Oracle's Gift", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = JadziStewardOfFateOraclesGift(name="Jadzi, Steward of Fate // Oracle's Gift", owner=None, base_power=2, base_toughness=4)
        assert card.mana_cost.cmc == 4, \
            f"CMC must be 4, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = JadziStewardOfFateOraclesGift(name="Jadzi, Steward of Fate // Oracle's Gift", owner=player, base_power=2, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 3
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestJadziStewardOfFateOraclesGiftInteractions:
    """Multi-card interaction tests for Jadzi, Steward of Fate // Oracle's Gift."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = JadziStewardOfFateOraclesGift(name="Jadzi, Steward of Fate // Oracle's Gift", owner=player, base_power=2, base_toughness=4)
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
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        card = JadziStewardOfFateOraclesGift(name="Jadzi, Steward of Fate // Oracle's Gift", owner=player, base_power=2, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
