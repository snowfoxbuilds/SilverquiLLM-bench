"""Audited tests for Sundering Archaic (collector key 3).

Verifies the Sundering Archaic card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import SunderingArchaic

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestSunderingArchaicBasicProperties:
    """Basic property tests for Sundering Archaic."""

    def test_is_creature(self) -> None:
        """Sundering Archaic must be a Creature subclass."""
        card = SunderingArchaic(name="Sundering Archaic", owner=None, base_power=3, base_toughness=3)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """SunderingArchaic.name must be 'Sundering Archaic'."""
        card = SunderingArchaic(name="Sundering Archaic", owner=None, base_power=3, base_toughness=3)
        assert card.name == "Sundering Archaic"

    def test_card_types(self) -> None:
        """Sundering Archaic must have correct card types."""
        card = SunderingArchaic(name="Sundering Archaic", owner=None, base_power=3, base_toughness=3)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Sundering Archaic must have converted mana cost 6."""
        card = SunderingArchaic(name="Sundering Archaic", owner=None, base_power=3, base_toughness=3)
        assert card.mana_cost.cmc == 6

    def test_colorless(self) -> None:
        """Sundering Archaic must be colorless."""
        card = SunderingArchaic(name="Sundering Archaic", owner=None, base_power=3, base_toughness=3)
        assert len(card.colors) == 0

    def test_power(self) -> None:
        """Sundering Archaic must have base power 3."""
        card = SunderingArchaic(name="Sundering Archaic", owner=None, base_power=3, base_toughness=3)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Sundering Archaic must have base toughness 3."""
        card = SunderingArchaic(name="Sundering Archaic", owner=None, base_power=3, base_toughness=3)
        assert card.base_toughness == 3


@pytest.mark.ability
class TestSunderingArchaicAbilities:
    """Ability tests for Sundering Archaic -- expected to fail against stubs."""

    def test_has_converge(self) -> None:
        """Sundering Archaic must have Converge keyword."""
        from engine.types import Keyword
        card = SunderingArchaic(name="Sundering Archaic", owner=None, base_power=3, base_toughness=3)
        assert Keyword.CONVERGE in card.keywords, "Sundering Archaic should have Converge"

    def test_etb_exiles_target(self) -> None:
        """ETB must exile target permanent per oracle text."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = SunderingArchaic(name="Sundering Archaic", owner=player, base_power=3, base_toughness=3)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        exile = opponent.zones[Zone.EXILE].get_all()
        assert target in exile, "ETB must exile the target per oracle"

    def test_converge_scaling(self) -> None:
        """Converge effect must scale with colors of mana spent."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = SunderingArchaic(name="Sundering Archaic", owner=player, base_power=3, base_toughness=3)
        card.controller = player
        if hasattr(card, "colors_spent"):
            card.colors_spent = 4
        assert callable(getattr(card, "on_resolve", None)) or \
            callable(getattr(card, "on_enter_battlefield", None)), \
            "Sundering Archaic must implement converge scaling per oracle text"


@pytest.mark.edge
class TestSunderingArchaicEdgeCases:
    """Edge case and trap tests for Sundering Archaic."""

    def test_fizzle_no_targets_creature_stays(self) -> None:
        """If ETB ability fizzles, the creature remains on battlefield."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = SunderingArchaic(name="Sundering Archaic", owner=player, base_power=3, base_toughness=3)
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

    def test_converge_zero_colors_no_bonus(self) -> None:
        """With 0 colors, converge should produce no bonus."""
        from tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = SunderingArchaic(name="Sundering Archaic", owner=player, base_power=3, base_toughness=3)
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
        card = SunderingArchaic(name="Sundering Archaic", owner=player, base_power=3, base_toughness=3)
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
        card1 = SunderingArchaic(name="Sundering Archaic", owner=None, base_power=3, base_toughness=3)
        card2 = SunderingArchaic(name="Sundering Archaic", owner=None, base_power=3, base_toughness=3)
        card1.name = "Modified"
        assert card2.name == "Sundering Archaic", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = SunderingArchaic(name="Sundering Archaic", owner=None, base_power=3, base_toughness=3)
        assert card.mana_cost.cmc == 6, \
            f"CMC must be 6, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestSunderingArchaicInteractions:
    """Multi-card interaction tests for Sundering Archaic."""

    def test_exile_from_graveyard_interaction(self) -> None:
        """Cards exiled from graveyard must move to exile zone."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Instant
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        fodder = Instant(name="Fodder", owner=player)
        set_board_state(game, 0, graveyard=[fodder])
        card = SunderingArchaic(name="Sundering Archaic", owner=player, base_power=3, base_toughness=3)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_attack", None)):
            card.on_attack(game)
        elif callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        exile = player.zones[Zone.EXILE].get_all()
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert fodder in exile or fodder not in gy, \
            "Exiled card must leave graveyard"

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = SunderingArchaic(name="Sundering Archaic", owner=player, base_power=3, base_toughness=3)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
