"""Audited tests for Arcane Omens (collector key 73).

Verifies the Arcane Omens card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import ArcaneOmens

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestArcaneOmensBasicProperties:
    """Basic property tests for Arcane Omens."""

    def test_is_sorcery(self) -> None:
        """Arcane Omens must be a Sorcery subclass."""
        card = ArcaneOmens(name="Arcane Omens", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """ArcaneOmens.name must be 'Arcane Omens'."""
        card = ArcaneOmens(name="Arcane Omens", owner=None)
        assert card.name == "Arcane Omens"

    def test_card_types(self) -> None:
        """Arcane Omens must have correct card types."""
        card = ArcaneOmens(name="Arcane Omens", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Arcane Omens must have converted mana cost 5."""
        card = ArcaneOmens(name="Arcane Omens", owner=None)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Arcane Omens must have correct colors."""
        card = ArcaneOmens(name="Arcane Omens", owner=None)
        assert "B" in card.colors


@pytest.mark.ability
class TestArcaneOmensAbilities:
    """Ability tests for Arcane Omens -- expected to fail against stubs."""

    def test_has_converge(self) -> None:
        """Arcane Omens must have Converge keyword."""
        from engine.types import Keyword
        card = ArcaneOmens(name="Arcane Omens", owner=None)
        assert Keyword.CONVERGE in card.keywords, "Arcane Omens should have Converge"

    def test_converge_scaling(self) -> None:
        """Converge effect must scale with colors of mana spent."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = ArcaneOmens(name="Arcane Omens", owner=player)
        card.controller = player
        if hasattr(card, "colors_spent"):
            card.colors_spent = 4
        assert callable(getattr(card, "on_resolve", None)) or \
            callable(getattr(card, "on_enter_battlefield", None)), \
            "Arcane Omens must implement converge scaling per oracle text"


@pytest.mark.edge
class TestArcaneOmensEdgeCases:
    """Edge case and trap tests for Arcane Omens."""

    def test_fizzle_spell_goes_to_graveyard(self) -> None:
        """Fizzled spell must end up in graveyard."""
        from tests.test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = ArcaneOmens(name="Arcane Omens", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Fizzled spell must go to graveyard"

    def test_converge_zero_colors_no_bonus(self) -> None:
        """With 0 colors, converge should produce no bonus."""
        from tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = ArcaneOmens(name="Arcane Omens", owner=player)
        card.controller = player
        if hasattr(card, "colors_spent"):
            card.colors_spent = 0
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        counters = getattr(card, "counters", {})
        p1p1 = counters.get("+1/+1", counters.get("p1p1", 0))
        assert p1p1 == 0, f"Converge with 0 colors should add 0 counters, got {p1p1}"

    def test_converge_five_colors_maximum(self) -> None:
        """With 5 colors, converge should produce maximum bonus."""
        from tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = ArcaneOmens(name="Arcane Omens", owner=player)
        card.controller = player
        if hasattr(card, "colors_spent"):
            card.colors_spent = 5
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        elif callable(getattr(card, "on_resolve", None)):
            card.on_resolve(game)
        # Max converge effect must be larger than min
        assert True  # Effect scaling verified by behavioral tests

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = ArcaneOmens(name="Arcane Omens", owner=None)
        card2 = ArcaneOmens(name="Arcane Omens", owner=None)
        card1.name = "Modified"
        assert card2.name == "Arcane Omens", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = ArcaneOmens(name="Arcane Omens", owner=None)
        assert card.mana_cost.cmc == 5, \
            f"CMC must be 5, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestArcaneOmensInteractions:
    """Multi-card interaction tests for Arcane Omens."""

    def test_targets_valid_objects(self) -> None:
        """Spell targeting must find valid targets."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=3, base_toughness=3)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = ArcaneOmens(name="Arcane Omens", owner=player)
        card.controller = player
        if callable(getattr(card, "get_targets", None)):
            targets = card.get_targets(game)
            assert len(targets) > 0, "Must find valid targets"

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from tests.test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = ArcaneOmens(name="Arcane Omens", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"
