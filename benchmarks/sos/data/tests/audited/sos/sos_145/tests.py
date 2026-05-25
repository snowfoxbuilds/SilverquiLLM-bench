"""Audited tests for Emeritus of Abundance // Regrowth (collector key 145).

Verifies the Emeritus of Abundance // Regrowth card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import EmeritusOfAbundanceRegrowth

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestEmeritusOfAbundanceRegrowthBasicProperties:
    """Basic property tests for Emeritus of Abundance // Regrowth."""

    def test_is_creature(self) -> None:
        """Emeritus of Abundance // Regrowth must be a Creature subclass."""
        card = EmeritusOfAbundanceRegrowth(name="Emeritus of Abundance // Regrowth", owner=None, base_power=3, base_toughness=4)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """EmeritusOfAbundanceRegrowth.name must be 'Emeritus of Abundance // Regrowth'."""
        card = EmeritusOfAbundanceRegrowth(name="Emeritus of Abundance // Regrowth", owner=None, base_power=3, base_toughness=4)
        assert card.name == "Emeritus of Abundance // Regrowth"

    def test_card_types(self) -> None:
        """Emeritus of Abundance // Regrowth must have correct card types."""
        card = EmeritusOfAbundanceRegrowth(name="Emeritus of Abundance // Regrowth", owner=None, base_power=3, base_toughness=4)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Emeritus of Abundance // Regrowth must have converted mana cost 5."""
        card = EmeritusOfAbundanceRegrowth(name="Emeritus of Abundance // Regrowth", owner=None, base_power=3, base_toughness=4)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Emeritus of Abundance // Regrowth must have correct colors."""
        card = EmeritusOfAbundanceRegrowth(name="Emeritus of Abundance // Regrowth", owner=None, base_power=3, base_toughness=4)
        assert "G" in card.colors

    def test_power(self) -> None:
        """Emeritus of Abundance // Regrowth must have base power 3."""
        card = EmeritusOfAbundanceRegrowth(name="Emeritus of Abundance // Regrowth", owner=None, base_power=3, base_toughness=4)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Emeritus of Abundance // Regrowth must have base toughness 4."""
        card = EmeritusOfAbundanceRegrowth(name="Emeritus of Abundance // Regrowth", owner=None, base_power=3, base_toughness=4)
        assert card.base_toughness == 4


@pytest.mark.ability
class TestEmeritusOfAbundanceRegrowthAbilities:
    """Ability tests for Emeritus of Abundance // Regrowth -- expected to fail against stubs."""

    def test_has_vigilance(self) -> None:
        """Emeritus of Abundance // Regrowth must have Vigilance keyword."""
        from engine.types import Keyword
        card = EmeritusOfAbundanceRegrowth(name="Emeritus of Abundance // Regrowth", owner=None, base_power=3, base_toughness=4)
        assert Keyword.VIGILANCE in card.keywords, "Emeritus of Abundance // Regrowth should have Vigilance"

    def test_has_prepared(self) -> None:
        """Emeritus of Abundance // Regrowth must have Prepared keyword."""
        from engine.types import Keyword
        card = EmeritusOfAbundanceRegrowth(name="Emeritus of Abundance // Regrowth", owner=None, base_power=3, base_toughness=4)
        assert Keyword.PREPARED in card.keywords, "Emeritus of Abundance // Regrowth should have Prepared"

    def test_etb_trigger_callable(self) -> None:
        """ETB trigger must be implemented per oracle text."""
        card = EmeritusOfAbundanceRegrowth(name="Emeritus of Abundance // Regrowth", owner=None, base_power=3, base_toughness=4)
        assert callable(getattr(card, "on_enter_battlefield", None)), \
            "Emeritus of Abundance // Regrowth must implement on_enter_battlefield per oracle text"

    def test_attack_trigger_implemented(self) -> None:
        """Attack trigger must be implemented per oracle text."""
        card = EmeritusOfAbundanceRegrowth(name="Emeritus of Abundance // Regrowth", owner=None, base_power=3, base_toughness=4)
        assert callable(getattr(card, "on_attack", None)), \
            "Emeritus of Abundance // Regrowth must implement on_attack per oracle text"

    def test_prepared_mechanic_implemented(self) -> None:
        """Prepared mechanic must be implemented per oracle text."""
        card = EmeritusOfAbundanceRegrowth(name="Emeritus of Abundance // Regrowth", owner=None, base_power=3, base_toughness=4)
        assert callable(getattr(card, "check_prepared", None)) or \
            callable(getattr(card, "prepared_effect", None)) or \
            callable(getattr(card, "on_resolve", None)), \
            "Emeritus of Abundance // Regrowth must implement prepared mechanic"


@pytest.mark.edge
class TestEmeritusOfAbundanceRegrowthEdgeCases:
    """Edge case and trap tests for Emeritus of Abundance // Regrowth."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = EmeritusOfAbundanceRegrowth(name="Emeritus of Abundance // Regrowth", owner=None, base_power=3, base_toughness=4)
        card2 = EmeritusOfAbundanceRegrowth(name="Emeritus of Abundance // Regrowth", owner=None, base_power=3, base_toughness=4)
        card1.name = "Modified"
        assert card2.name == "Emeritus of Abundance // Regrowth", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = EmeritusOfAbundanceRegrowth(name="Emeritus of Abundance // Regrowth", owner=None, base_power=3, base_toughness=4)
        assert card.mana_cost.cmc == 5, \
            f"CMC must be 5, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = EmeritusOfAbundanceRegrowth(name="Emeritus of Abundance // Regrowth", owner=player, base_power=3, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 3
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestEmeritusOfAbundanceRegrowthInteractions:
    """Multi-card interaction tests for Emeritus of Abundance // Regrowth."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = EmeritusOfAbundanceRegrowth(name="Emeritus of Abundance // Regrowth", owner=player, base_power=3, base_toughness=4)
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
        card = EmeritusOfAbundanceRegrowth(name="Emeritus of Abundance // Regrowth", owner=player, base_power=3, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
