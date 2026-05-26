"""Audited tests for Group Project (collector key 17).

Verifies the Group Project card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import GroupProject

from engine.card import Sorcery
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestGroupProjectBasicProperties:
    """Basic property tests for Group Project."""

    def test_is_sorcery(self) -> None:
        """Group Project must be a Sorcery subclass."""
        card = GroupProject(name="Group Project", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """GroupProject.name must be 'Group Project'."""
        card = GroupProject(name="Group Project", owner=None)
        assert card.name == "Group Project"

    def test_card_types(self) -> None:
        """Group Project must have correct card types."""
        card = GroupProject(name="Group Project", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Group Project must have converted mana cost 2."""
        card = GroupProject(name="Group Project", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Group Project must have correct colors."""
        card = GroupProject(name="Group Project", owner=None)
        assert "W" in card_colors(card)

@pytest.mark.ability
class TestGroupProjectAbilities:
    """Ability tests for Group Project — expected to fail against stubs."""

    def test_flashback_cost_attribute(self) -> None:
        """Card must expose a flashback cost distinct from normal mana cost."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = GroupProject(name="Group Project", owner=player)
        card.controller = player
        has_fb = hasattr(card, "flashback_cost") or hasattr(card, "alternate_costs")
        assert has_fb, "Group Project must expose flashback cost"

    def test_flashback_exiles_after_resolution(self) -> None:
        """Card must be exiled after flashback resolution."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = GroupProject(name="Group Project", owner=player)
        card.controller = player
        set_board_state(game, 0, graveyard=[card])
        if hasattr(card, "_cast_via_flashback"):
            card._cast_via_flashback = True
        card.on_resolve(game)
        exile = player.zones[Zone.EXILE].get_all()
        assert card in exile, "Card must be exiled after flashback resolution"

    def test_flashback_removes_from_graveyard(self) -> None:
        """Flashback resolution must remove card from graveyard."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = GroupProject(name="Group Project", owner=player)
        card.controller = player
        set_board_state(game, 0, graveyard=[card])
        assert card in player.zones[Zone.GRAVEYARD].get_all()
        if hasattr(card, "_cast_via_flashback"):
            card._cast_via_flashback = True
        card.on_resolve(game)
        gy_after = player.zones[Zone.GRAVEYARD].get_all()
        assert card not in gy_after, "Card must leave graveyard after flashback"

    def test_creates_token(self) -> None:
        """Resolution should create token(s) on battlefield."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = GroupProject(name="Group Project", owner=player)
        card.controller = player
        bf_before = len(game.get_battlefield(player).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after > bf_before, (
            f"Should create token: bf {bf_before} -> {bf_after}"
        )

@pytest.mark.edge
class TestGroupProjectEdgeCases:
    """Edge case tests for Group Project."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = GroupProject(name="Group Project", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True

@pytest.mark.interaction
class TestGroupProjectInteractions:
    """Interaction tests for Group Project."""

    def test_flashback_not_from_hand(self) -> None:
        """Flashback alternate cost only applies from graveyard."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = GroupProject(name="Group Project", owner=player)
        card.controller = player
        set_board_state(game, 0, hand=[card])
        # From hand, should use normal cost, not flashback
        assert card in player.zones[Zone.HAND].get_all()
        # Flashback should only be relevant from graveyard
        has_zone_check = hasattr(card, "flashback_zone") or hasattr(card, "can_cast_from_zone")
        assert has_zone_check or card.can_cast(game), (
            "Card in hand should use normal cast path"
        )

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = GroupProject(name="Group Project", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
