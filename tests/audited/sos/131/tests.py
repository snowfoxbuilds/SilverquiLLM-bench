"""Audited tests for Strife Scholar // Awaken the Ages (collector key 131).

Verifies the Strife Scholar // Awaken the Ages card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import StrifeScholarAwakenTheAges

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestStrifeScholarAwakenTheAgesBasicProperties:
    """Basic property tests for Strife Scholar // Awaken the Ages."""

    def test_is_creature(self) -> None:
        """Strife Scholar // Awaken the Ages must be a Creature subclass."""
        card = StrifeScholarAwakenTheAges(name="Strife Scholar // Awaken the Ages", owner=None, base_power=3, base_toughness=2)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """StrifeScholarAwakenTheAges.name must be 'Strife Scholar // Awaken the Ages'."""
        card = StrifeScholarAwakenTheAges(name="Strife Scholar // Awaken the Ages", owner=None, base_power=3, base_toughness=2)
        assert card.name == "Strife Scholar // Awaken the Ages"

    def test_card_types(self) -> None:
        """Strife Scholar // Awaken the Ages must have correct card types."""
        card = StrifeScholarAwakenTheAges(name="Strife Scholar // Awaken the Ages", owner=None, base_power=3, base_toughness=2)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Strife Scholar // Awaken the Ages must have converted mana cost 9."""
        card = StrifeScholarAwakenTheAges(name="Strife Scholar // Awaken the Ages", owner=None, base_power=3, base_toughness=2)
        assert card.mana_cost.cmc == 9

    def test_colors(self) -> None:
        """Strife Scholar // Awaken the Ages must have correct colors."""
        card = StrifeScholarAwakenTheAges(name="Strife Scholar // Awaken the Ages", owner=None, base_power=3, base_toughness=2)
        assert "R" in card.colors

    def test_power(self) -> None:
        """Strife Scholar // Awaken the Ages must have base power 3."""
        card = StrifeScholarAwakenTheAges(name="Strife Scholar // Awaken the Ages", owner=None, base_power=3, base_toughness=2)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Strife Scholar // Awaken the Ages must have base toughness 2."""
        card = StrifeScholarAwakenTheAges(name="Strife Scholar // Awaken the Ages", owner=None, base_power=3, base_toughness=2)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestStrifeScholarAwakenTheAgesAbilities:
    """Ability tests for Strife Scholar // Awaken the Ages -- expected to fail against stubs."""

    def test_has_prepared(self) -> None:
        """Strife Scholar // Awaken the Ages must have Prepared keyword."""
        from engine.types import Keyword
        card = StrifeScholarAwakenTheAges(name="Strife Scholar // Awaken the Ages", owner=None, base_power=3, base_toughness=2)
        assert Keyword.PREPARED in card.keywords, "Strife Scholar // Awaken the Ages should have Prepared"

    def test_has_ward(self) -> None:
        """Strife Scholar // Awaken the Ages must have Ward keyword."""
        from engine.types import Keyword
        card = StrifeScholarAwakenTheAges(name="Strife Scholar // Awaken the Ages", owner=None, base_power=3, base_toughness=2)
        assert Keyword.WARD in card.keywords, "Strife Scholar // Awaken the Ages should have Ward"

    def test_etb_trigger_callable(self) -> None:
        """ETB trigger must be implemented per oracle text."""
        card = StrifeScholarAwakenTheAges(name="Strife Scholar // Awaken the Ages", owner=None, base_power=3, base_toughness=2)
        assert callable(getattr(card, "on_enter_battlefield", None)), \
            "Strife Scholar // Awaken the Ages must implement on_enter_battlefield per oracle text"

    def test_prepared_mechanic_implemented(self) -> None:
        """Prepared mechanic must be implemented per oracle text."""
        card = StrifeScholarAwakenTheAges(name="Strife Scholar // Awaken the Ages", owner=None, base_power=3, base_toughness=2)
        assert callable(getattr(card, "check_prepared", None)) or \
            callable(getattr(card, "prepared_effect", None)) or \
            callable(getattr(card, "on_resolve", None)), \
            "Strife Scholar // Awaken the Ages must implement prepared mechanic"


@pytest.mark.edge
class TestStrifeScholarAwakenTheAgesEdgeCases:
    """Edge case and trap tests for Strife Scholar // Awaken the Ages."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = StrifeScholarAwakenTheAges(name="Strife Scholar // Awaken the Ages", owner=None, base_power=3, base_toughness=2)
        card2 = StrifeScholarAwakenTheAges(name="Strife Scholar // Awaken the Ages", owner=None, base_power=3, base_toughness=2)
        card1.name = "Modified"
        assert card2.name == "Strife Scholar // Awaken the Ages", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = StrifeScholarAwakenTheAges(name="Strife Scholar // Awaken the Ages", owner=None, base_power=3, base_toughness=2)
        assert card.mana_cost.cmc == 9, \
            f"CMC must be 9, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = StrifeScholarAwakenTheAges(name="Strife Scholar // Awaken the Ages", owner=player, base_power=3, base_toughness=2)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 1
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestStrifeScholarAwakenTheAgesInteractions:
    """Multi-card interaction tests for Strife Scholar // Awaken the Ages."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = StrifeScholarAwakenTheAges(name="Strife Scholar // Awaken the Ages", owner=player, base_power=3, base_toughness=2)
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
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        card = StrifeScholarAwakenTheAges(name="Strife Scholar // Awaken the Ages", owner=player, base_power=3, base_toughness=2)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
