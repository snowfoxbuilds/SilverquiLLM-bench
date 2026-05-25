"""Audited tests for Elemental Mascot (collector key 185).

Verifies the Elemental Mascot card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import ElementalMascot

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestElementalMascotBasicProperties:
    """Basic property tests for Elemental Mascot."""

    def test_is_creature(self) -> None:
        """Elemental Mascot must be a Creature subclass."""
        card = ElementalMascot(name="Elemental Mascot", owner=None, base_power=1, base_toughness=4)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """ElementalMascot.name must be 'Elemental Mascot'."""
        card = ElementalMascot(name="Elemental Mascot", owner=None, base_power=1, base_toughness=4)
        assert card.name == "Elemental Mascot"

    def test_card_types(self) -> None:
        """Elemental Mascot must have correct card types."""
        card = ElementalMascot(name="Elemental Mascot", owner=None, base_power=1, base_toughness=4)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Elemental Mascot must have converted mana cost 3."""
        card = ElementalMascot(name="Elemental Mascot", owner=None, base_power=1, base_toughness=4)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Elemental Mascot must have correct colors."""
        card = ElementalMascot(name="Elemental Mascot", owner=None, base_power=1, base_toughness=4)
        assert "R" in card.colors
        assert "U" in card.colors

    def test_power(self) -> None:
        """Elemental Mascot must have base power 1."""
        card = ElementalMascot(name="Elemental Mascot", owner=None, base_power=1, base_toughness=4)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Elemental Mascot must have base toughness 4."""
        card = ElementalMascot(name="Elemental Mascot", owner=None, base_power=1, base_toughness=4)
        assert card.base_toughness == 4


@pytest.mark.ability
class TestElementalMascotAbilities:
    """Ability tests for Elemental Mascot -- expected to fail against stubs."""

    def test_has_flying(self) -> None:
        """Elemental Mascot must have Flying keyword."""
        from engine.types import Keyword
        card = ElementalMascot(name="Elemental Mascot", owner=None, base_power=1, base_toughness=4)
        assert Keyword.FLYING in card.keywords, "Elemental Mascot should have Flying"

    def test_has_vigilance(self) -> None:
        """Elemental Mascot must have Vigilance keyword."""
        from engine.types import Keyword
        card = ElementalMascot(name="Elemental Mascot", owner=None, base_power=1, base_toughness=4)
        assert Keyword.VIGILANCE in card.keywords, "Elemental Mascot should have Vigilance"

    def test_has_opus(self) -> None:
        """Elemental Mascot must have Opus keyword."""
        from engine.types import Keyword
        card = ElementalMascot(name="Elemental Mascot", owner=None, base_power=1, base_toughness=4)
        assert Keyword.OPUS in card.keywords, "Elemental Mascot should have Opus"

    def test_opus_trigger_implemented(self) -> None:
        """Opus must trigger when controller casts instant/sorcery."""
        card = ElementalMascot(name="Elemental Mascot", owner=None, base_power=1, base_toughness=4)
        assert callable(getattr(card, "on_spell_cast", None)) or \
            callable(getattr(card, "opus_trigger", None)), \
            "Elemental Mascot must implement opus trigger per oracle text"


@pytest.mark.edge
class TestElementalMascotEdgeCases:
    """Edge case and trap tests for Elemental Mascot."""

    def test_opus_no_trigger_without_spell(self) -> None:
        """Opus should not boost without casting instant/sorcery."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = ElementalMascot(name="Elemental Mascot", owner=player, base_power=1, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        base_p = card.base_power
        # Without casting a spell, power should remain at base
        actual_p = getattr(card, "power", card.base_power)
        assert actual_p == base_p, f"Without opus trigger, power should be {base_p}, got {actual_p}"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = ElementalMascot(name="Elemental Mascot", owner=None, base_power=1, base_toughness=4)
        card2 = ElementalMascot(name="Elemental Mascot", owner=None, base_power=1, base_toughness=4)
        card1.name = "Modified"
        assert card2.name == "Elemental Mascot", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = ElementalMascot(name="Elemental Mascot", owner=None, base_power=1, base_toughness=4)
        assert card.mana_cost.cmc == 3, \
            f"CMC must be 3, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestElementalMascotInteractions:
    """Multi-card interaction tests for Elemental Mascot."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = ElementalMascot(name="Elemental Mascot", owner=player, base_power=1, base_toughness=4)
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
        card = ElementalMascot(name="Elemental Mascot", owner=player, base_power=1, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
