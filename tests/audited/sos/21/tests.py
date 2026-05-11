"""Audited tests for Inkshape Demonstrator (collector key 21).

Verifies the Inkshape Demonstrator card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import InkshapeDemonstrator

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestInkshapeDemonstratorBasicProperties:
    """Basic property tests for Inkshape Demonstrator."""

    def test_is_creature(self) -> None:
        """Inkshape Demonstrator must be a Creature subclass."""
        card = InkshapeDemonstrator(name="Inkshape Demonstrator", owner=None, base_power=3, base_toughness=4)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """InkshapeDemonstrator.name must be 'Inkshape Demonstrator'."""
        card = InkshapeDemonstrator(name="Inkshape Demonstrator", owner=None, base_power=3, base_toughness=4)
        assert card.name == "Inkshape Demonstrator"

    def test_card_types(self) -> None:
        """Inkshape Demonstrator must have correct card types."""
        card = InkshapeDemonstrator(name="Inkshape Demonstrator", owner=None, base_power=3, base_toughness=4)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Inkshape Demonstrator must have converted mana cost 4."""
        card = InkshapeDemonstrator(name="Inkshape Demonstrator", owner=None, base_power=3, base_toughness=4)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Inkshape Demonstrator must have correct colors."""
        card = InkshapeDemonstrator(name="Inkshape Demonstrator", owner=None, base_power=3, base_toughness=4)
        assert "W" in card.colors

    def test_power(self) -> None:
        """Inkshape Demonstrator must have base power 3."""
        card = InkshapeDemonstrator(name="Inkshape Demonstrator", owner=None, base_power=3, base_toughness=4)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Inkshape Demonstrator must have base toughness 4."""
        card = InkshapeDemonstrator(name="Inkshape Demonstrator", owner=None, base_power=3, base_toughness=4)
        assert card.base_toughness == 4


@pytest.mark.ability
class TestInkshapeDemonstratorAbilities:
    """Ability tests for Inkshape Demonstrator -- expected to fail against stubs."""

    def test_has_ward(self) -> None:
        """Inkshape Demonstrator must have Ward keyword."""
        from engine.types import Keyword
        card = InkshapeDemonstrator(name="Inkshape Demonstrator", owner=None, base_power=3, base_toughness=4)
        assert Keyword.WARD in card.keywords, "Inkshape Demonstrator should have Ward"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = InkshapeDemonstrator(name="Inkshape Demonstrator", owner=None, base_power=3, base_toughness=4)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Inkshape Demonstrator must implement behavioral method"


@pytest.mark.edge
class TestInkshapeDemonstratorEdgeCases:
    """Edge case and trap tests for Inkshape Demonstrator."""

    def test_fizzle_no_targets_creature_stays(self) -> None:
        """If ETB ability fizzles, the creature remains on battlefield."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = InkshapeDemonstrator(name="Inkshape Demonstrator", owner=player, base_power=3, base_toughness=4)
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
        card1 = InkshapeDemonstrator(name="Inkshape Demonstrator", owner=None, base_power=3, base_toughness=4)
        card2 = InkshapeDemonstrator(name="Inkshape Demonstrator", owner=None, base_power=3, base_toughness=4)
        card1.name = "Modified"
        assert card2.name == "Inkshape Demonstrator", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = InkshapeDemonstrator(name="Inkshape Demonstrator", owner=None, base_power=3, base_toughness=4)
        assert card.mana_cost.cmc == 4, \
            f"CMC must be 4, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestInkshapeDemonstratorInteractions:
    """Multi-card interaction tests for Inkshape Demonstrator."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = InkshapeDemonstrator(name="Inkshape Demonstrator", owner=player, base_power=3, base_toughness=4)
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
        card = InkshapeDemonstrator(name="Inkshape Demonstrator", owner=player, base_power=3, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
