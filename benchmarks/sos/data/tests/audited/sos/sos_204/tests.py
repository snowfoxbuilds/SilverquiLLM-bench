"""Audited tests for Molten Note (collector key 204).

Verifies the Molten Note card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import MoltenNote

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestMoltenNoteBasicProperties:
    """Basic property tests for Molten Note."""

    def test_is_sorcery(self) -> None:
        """Molten Note must be a Sorcery subclass."""
        card = MoltenNote(name="Molten Note", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """MoltenNote.name must be 'Molten Note'."""
        card = MoltenNote(name="Molten Note", owner=None)
        assert card.name == "Molten Note"

    def test_card_types(self) -> None:
        """Molten Note must have correct card types."""
        card = MoltenNote(name="Molten Note", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Molten Note must have converted mana cost 2."""
        card = MoltenNote(name="Molten Note", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Molten Note must have correct colors."""
        card = MoltenNote(name="Molten Note", owner=None)
        assert "R" in card.colors
        assert "W" in card.colors


@pytest.mark.ability
class TestMoltenNoteAbilities:
    """Ability tests for Molten Note — expected to fail against stubs."""

    def test_flashback_cost_attribute(self) -> None:
        """Card must expose a flashback cost distinct from normal mana cost."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = MoltenNote(name="Molten Note", owner=player)
        card.controller = player
        has_fb = hasattr(card, "flashback_cost") or hasattr(card, "alternate_costs")
        assert has_fb, "Molten Note must expose flashback cost"

    def test_flashback_exiles_after_resolution(self) -> None:
        """Card must be exiled after flashback resolution."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = MoltenNote(name="Molten Note", owner=player)
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
        card = MoltenNote(name="Molten Note", owner=player)
        card.controller = player
        set_board_state(game, 0, graveyard=[card])
        assert card in player.zones[Zone.GRAVEYARD].get_all()
        if hasattr(card, "_cast_via_flashback"):
            card._cast_via_flashback = True
        card.on_resolve(game)
        gy_after = player.zones[Zone.GRAVEYARD].get_all()
        assert card not in gy_after, "Card must leave graveyard after flashback"


@pytest.mark.edge
class TestMoltenNoteEdgeCases:
    """Edge case tests for Molten Note."""

    def test_targets_only_own_permanents(self) -> None:
        """Should only target permanents you control."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        own = Creature(name="Own", owner=player, base_power=2, base_toughness=2)
        enemy = Creature(name="Enemy", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[own])
        set_board_state(game, 1, battlefield=[enemy])
        card = MoltenNote(name="Molten Note", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        if len(targets) > 0:
            assert own in targets, "Own creature should be valid"
            assert enemy not in targets, "Opponent creature should be invalid"


@pytest.mark.interaction
class TestMoltenNoteInteractions:
    """Interaction tests for Molten Note."""

    def test_get_targets_finds_own_creatures(self) -> None:
        """get_targets should return valid own creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        creature = Creature(name="Mine", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[creature])
        card = MoltenNote(name="Molten Note", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find own creature as target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = MoltenNote(name="Molten Note", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
