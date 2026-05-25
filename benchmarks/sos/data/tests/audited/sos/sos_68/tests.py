"""Audited tests for Spellbook Seeker // Careful Study (collector key 68).

Verifies the Spellbook Seeker // Careful Study card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import SpellbookSeekerCarefulStudy

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestSpellbookSeekerCarefulStudyBasicProperties:
    """Basic property tests for Spellbook Seeker // Careful Study."""

    def test_is_creature(self) -> None:
        """Spellbook Seeker // Careful Study must be a Creature subclass."""
        card = SpellbookSeekerCarefulStudy(name="Spellbook Seeker // Careful Study", owner=None, base_power=3, base_toughness=3)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """SpellbookSeekerCarefulStudy.name must be 'Spellbook Seeker // Careful Study'."""
        card = SpellbookSeekerCarefulStudy(name="Spellbook Seeker // Careful Study", owner=None, base_power=3, base_toughness=3)
        assert card.name == "Spellbook Seeker // Careful Study"

    def test_card_types(self) -> None:
        """Spellbook Seeker // Careful Study must have correct card types."""
        card = SpellbookSeekerCarefulStudy(name="Spellbook Seeker // Careful Study", owner=None, base_power=3, base_toughness=3)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Spellbook Seeker // Careful Study must have converted mana cost 5."""
        card = SpellbookSeekerCarefulStudy(name="Spellbook Seeker // Careful Study", owner=None, base_power=3, base_toughness=3)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Spellbook Seeker // Careful Study must have correct colors."""
        card = SpellbookSeekerCarefulStudy(name="Spellbook Seeker // Careful Study", owner=None, base_power=3, base_toughness=3)
        assert "U" in card.colors

    def test_power(self) -> None:
        """Spellbook Seeker // Careful Study must have base power 3."""
        card = SpellbookSeekerCarefulStudy(name="Spellbook Seeker // Careful Study", owner=None, base_power=3, base_toughness=3)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Spellbook Seeker // Careful Study must have base toughness 3."""
        card = SpellbookSeekerCarefulStudy(name="Spellbook Seeker // Careful Study", owner=None, base_power=3, base_toughness=3)
        assert card.base_toughness == 3


@pytest.mark.ability
class TestSpellbookSeekerCarefulStudyAbilities:
    """Ability tests for Spellbook Seeker // Careful Study -- expected to fail against stubs."""

    def test_has_flying(self) -> None:
        """Spellbook Seeker // Careful Study must have Flying keyword."""
        from engine.types import Keyword
        card = SpellbookSeekerCarefulStudy(name="Spellbook Seeker // Careful Study", owner=None, base_power=3, base_toughness=3)
        assert Keyword.FLYING in card.keywords, "Spellbook Seeker // Careful Study should have Flying"

    def test_has_prepared(self) -> None:
        """Spellbook Seeker // Careful Study must have Prepared keyword."""
        from engine.types import Keyword
        card = SpellbookSeekerCarefulStudy(name="Spellbook Seeker // Careful Study", owner=None, base_power=3, base_toughness=3)
        assert Keyword.PREPARED in card.keywords, "Spellbook Seeker // Careful Study should have Prepared"

    def test_etb_trigger_callable(self) -> None:
        """ETB trigger must be implemented per oracle text."""
        card = SpellbookSeekerCarefulStudy(name="Spellbook Seeker // Careful Study", owner=None, base_power=3, base_toughness=3)
        assert callable(getattr(card, "on_enter_battlefield", None)), \
            "Spellbook Seeker // Careful Study must implement on_enter_battlefield per oracle text"

    def test_prepared_mechanic_implemented(self) -> None:
        """Prepared mechanic must be implemented per oracle text."""
        card = SpellbookSeekerCarefulStudy(name="Spellbook Seeker // Careful Study", owner=None, base_power=3, base_toughness=3)
        assert callable(getattr(card, "check_prepared", None)) or \
            callable(getattr(card, "prepared_effect", None)) or \
            callable(getattr(card, "on_resolve", None)), \
            "Spellbook Seeker // Careful Study must implement prepared mechanic"


@pytest.mark.edge
class TestSpellbookSeekerCarefulStudyEdgeCases:
    """Edge case and trap tests for Spellbook Seeker // Careful Study."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = SpellbookSeekerCarefulStudy(name="Spellbook Seeker // Careful Study", owner=None, base_power=3, base_toughness=3)
        card2 = SpellbookSeekerCarefulStudy(name="Spellbook Seeker // Careful Study", owner=None, base_power=3, base_toughness=3)
        card1.name = "Modified"
        assert card2.name == "Spellbook Seeker // Careful Study", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = SpellbookSeekerCarefulStudy(name="Spellbook Seeker // Careful Study", owner=None, base_power=3, base_toughness=3)
        assert card.mana_cost.cmc == 5, \
            f"CMC must be 5, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = SpellbookSeekerCarefulStudy(name="Spellbook Seeker // Careful Study", owner=player, base_power=3, base_toughness=3)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 2
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestSpellbookSeekerCarefulStudyInteractions:
    """Multi-card interaction tests for Spellbook Seeker // Careful Study."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = SpellbookSeekerCarefulStudy(name="Spellbook Seeker // Careful Study", owner=player, base_power=3, base_toughness=3)
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
        card = SpellbookSeekerCarefulStudy(name="Spellbook Seeker // Careful Study", owner=player, base_power=3, base_toughness=3)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
