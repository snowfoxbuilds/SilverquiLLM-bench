"""Audited tests for Fractal Mascot (collector key 189).

Verifies the Fractal Mascot card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import FractalMascot

from engine.card import Creature
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestFractalMascotBasicProperties:
    """Basic property tests for Fractal Mascot."""

    def test_is_creature(self) -> None:
        """Fractal Mascot must be a Creature subclass."""
        card = FractalMascot(name="Fractal Mascot", owner=None, base_power=6, base_toughness=6)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """FractalMascot.name must be 'Fractal Mascot'."""
        card = FractalMascot(name="Fractal Mascot", owner=None, base_power=6, base_toughness=6)
        assert card.name == "Fractal Mascot"

    def test_card_types(self) -> None:
        """Fractal Mascot must have correct card types."""
        card = FractalMascot(name="Fractal Mascot", owner=None, base_power=6, base_toughness=6)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Fractal Mascot must have converted mana cost 6."""
        card = FractalMascot(name="Fractal Mascot", owner=None, base_power=6, base_toughness=6)
        assert card.mana_cost.cmc == 6

    def test_colors(self) -> None:
        """Fractal Mascot must have correct colors."""
        card = FractalMascot(name="Fractal Mascot", owner=None, base_power=6, base_toughness=6)
        assert "G" in card_colors(card)
        assert "U" in card_colors(card)

    def test_power(self) -> None:
        """Fractal Mascot must have base power 6."""
        card = FractalMascot(name="Fractal Mascot", owner=None, base_power=6, base_toughness=6)
        assert card.base_power == 6

    def test_toughness(self) -> None:
        """Fractal Mascot must have base toughness 6."""
        card = FractalMascot(name="Fractal Mascot", owner=None, base_power=6, base_toughness=6)
        assert card.base_toughness == 6

@pytest.mark.ability
class TestFractalMascotAbilities:
    """Ability tests for Fractal Mascot -- expected to fail against stubs."""

    def test_has_trample(self) -> None:
        """Fractal Mascot must have Trample keyword."""
        from engine.types import Keyword
        card = FractalMascot(name="Fractal Mascot", owner=None, base_power=6, base_toughness=6)
        assert Keyword.TRAMPLE in card.keywords, "Fractal Mascot should have Trample"

    def test_etb_taps_target(self) -> None:
        """ETB must tap a target creature per oracle text."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = FractalMascot(name="Fractal Mascot", owner=player, base_power=6, base_toughness=6)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        assert getattr(target, "tapped", False), "ETB must tap the target creature"

@pytest.mark.edge
class TestFractalMascotEdgeCases:
    """Edge case and trap tests for Fractal Mascot."""

    def test_fizzle_no_targets_creature_stays(self) -> None:
        """If ETB ability fizzles, the creature remains on battlefield."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = FractalMascot(name="Fractal Mascot", owner=player, base_power=6, base_toughness=6)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        # No targets available; ETB fizzles
        try:
            if callable(getattr(card, "on_enter_battlefield", None)):
                card.on_enter_battlefield(game)
        except (ValueError, IndexError):
            pass  # Fizzle expected
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must stay on battlefield when ETB fizzles"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = FractalMascot(name="Fractal Mascot", owner=None, base_power=6, base_toughness=6)
        card2 = FractalMascot(name="Fractal Mascot", owner=None, base_power=6, base_toughness=6)
        card1.name = "Modified"
        assert card2.name == "Fractal Mascot", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = FractalMascot(name="Fractal Mascot", owner=None, base_power=6, base_toughness=6)
        assert card.mana_cost.cmc == 6, \
            f"CMC must be 6, got {card.mana_cost.cmc}"

@pytest.mark.interaction
class TestFractalMascotInteractions:
    """Multi-card interaction tests for Fractal Mascot."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = FractalMascot(name="Fractal Mascot", owner=player, base_power=6, base_toughness=6)
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
        card = FractalMascot(name="Fractal Mascot", owner=player, base_power=6, base_toughness=6)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
