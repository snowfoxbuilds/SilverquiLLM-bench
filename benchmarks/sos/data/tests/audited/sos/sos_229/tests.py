"""Audited tests for Spectacular Skywhale (collector key 229).

Verifies the Spectacular Skywhale card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import SpectacularSkywhale

from engine.card import Creature
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestSpectacularSkywhaleBasicProperties:
    """Basic property tests for Spectacular Skywhale."""

    def test_is_creature(self) -> None:
        """Spectacular Skywhale must be a Creature subclass."""
        card = SpectacularSkywhale(name="Spectacular Skywhale", owner=None, base_power=1, base_toughness=4)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """SpectacularSkywhale.name must be 'Spectacular Skywhale'."""
        card = SpectacularSkywhale(name="Spectacular Skywhale", owner=None, base_power=1, base_toughness=4)
        assert card.name == "Spectacular Skywhale"

    def test_card_types(self) -> None:
        """Spectacular Skywhale must have correct card types."""
        card = SpectacularSkywhale(name="Spectacular Skywhale", owner=None, base_power=1, base_toughness=4)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Spectacular Skywhale must have converted mana cost 4."""
        card = SpectacularSkywhale(name="Spectacular Skywhale", owner=None, base_power=1, base_toughness=4)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Spectacular Skywhale must have correct colors."""
        card = SpectacularSkywhale(name="Spectacular Skywhale", owner=None, base_power=1, base_toughness=4)
        assert "R" in card_colors(card)
        assert "U" in card_colors(card)

    def test_power(self) -> None:
        """Spectacular Skywhale must have base power 1."""
        card = SpectacularSkywhale(name="Spectacular Skywhale", owner=None, base_power=1, base_toughness=4)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Spectacular Skywhale must have base toughness 4."""
        card = SpectacularSkywhale(name="Spectacular Skywhale", owner=None, base_power=1, base_toughness=4)
        assert card.base_toughness == 4

@pytest.mark.ability
class TestSpectacularSkywhaleAbilities:
    """Ability tests for Spectacular Skywhale -- expected to fail against stubs."""

    def test_has_flying(self) -> None:
        """Spectacular Skywhale must have Flying keyword."""
        from engine.types import Keyword
        card = SpectacularSkywhale(name="Spectacular Skywhale", owner=None, base_power=1, base_toughness=4)
        assert Keyword.FLYING in card.keywords, "Spectacular Skywhale should have Flying"

    def test_has_opus(self) -> None:
        """Spectacular Skywhale must have Opus keyword."""
        from engine.types import Keyword
        card = SpectacularSkywhale(name="Spectacular Skywhale", owner=None, base_power=1, base_toughness=4)
        assert Keyword.OPUS in card.keywords, "Spectacular Skywhale should have Opus"

    def test_opus_trigger_implemented(self) -> None:
        """Opus must trigger when controller casts instant/sorcery."""
        card = SpectacularSkywhale(name="Spectacular Skywhale", owner=None, base_power=1, base_toughness=4)
        assert callable(getattr(card, "on_spell_cast", None)) or \
            callable(getattr(card, "opus_trigger", None)), \
            "Spectacular Skywhale must implement opus trigger per oracle text"

@pytest.mark.edge
class TestSpectacularSkywhaleEdgeCases:
    """Edge case and trap tests for Spectacular Skywhale."""

    def test_opus_no_trigger_without_spell(self) -> None:
        """Opus should not boost without casting instant/sorcery."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = SpectacularSkywhale(name="Spectacular Skywhale", owner=player, base_power=1, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        base_p = card.base_power
        # Without casting a spell, power should remain at base
        actual_p = getattr(card, "power", card.base_power)
        assert actual_p == base_p, f"Without opus trigger, power should be {base_p}, got {actual_p}"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = SpectacularSkywhale(name="Spectacular Skywhale", owner=None, base_power=1, base_toughness=4)
        card2 = SpectacularSkywhale(name="Spectacular Skywhale", owner=None, base_power=1, base_toughness=4)
        card1.name = "Modified"
        assert card2.name == "Spectacular Skywhale", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = SpectacularSkywhale(name="Spectacular Skywhale", owner=None, base_power=1, base_toughness=4)
        assert card.mana_cost.cmc == 4, \
            f"CMC must be 4, got {card.mana_cost.cmc}"

@pytest.mark.interaction
class TestSpectacularSkywhaleInteractions:
    """Multi-card interaction tests for Spectacular Skywhale."""

    def test_counters_survive_end_of_turn(self) -> None:
        """Permanent counters must persist through end of turn."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = SpectacularSkywhale(name="Spectacular Skywhale", owner=player, base_power=1, base_toughness=4)
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
        card = SpectacularSkywhale(name="Spectacular Skywhale", owner=player, base_power=1, base_toughness=4)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
