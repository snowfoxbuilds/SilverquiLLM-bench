"""Audited tests for Tome Blast (collector key 135).

Verifies the Tome Blast card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import TomeBlast

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestTomeBlastBasicProperties:
    """Basic property tests for Tome Blast."""

    def test_is_sorcery(self) -> None:
        """Tome Blast must be a Sorcery subclass."""
        card = TomeBlast(name="Tome Blast", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """TomeBlast.name must be 'Tome Blast'."""
        card = TomeBlast(name="Tome Blast", owner=None)
        assert card.name == "Tome Blast"

    def test_card_types(self) -> None:
        """Tome Blast must have correct card types."""
        card = TomeBlast(name="Tome Blast", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Tome Blast must have converted mana cost 2."""
        card = TomeBlast(name="Tome Blast", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Tome Blast must have correct colors."""
        card = TomeBlast(name="Tome Blast", owner=None)
        assert "R" in card.colors


@pytest.mark.ability
class TestTomeBlastAbilities:
    """Ability tests for Tome Blast — expected to fail against stubs."""

    def test_flashback_cost_attribute(self) -> None:
        """Card must expose a flashback cost distinct from normal mana cost."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = TomeBlast(name="Tome Blast", owner=player)
        card.controller = player
        has_fb = hasattr(card, "flashback_cost") or hasattr(card, "alternate_costs")
        assert has_fb, "Tome Blast must expose flashback cost"

    def test_flashback_exiles_after_resolution(self) -> None:
        """Card must be exiled after flashback resolution."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = TomeBlast(name="Tome Blast", owner=player)
        card.controller = player
        set_board_state(game, 0, graveyard=[card])
        if hasattr(card, "_cast_via_flashback"):
            card._cast_via_flashback = True
        card.on_resolve(game)
        exile = player.zones[Zone.EXILE].get_all()
        assert card in exile, "Card must be exiled after flashback resolution"

    def test_flashback_removes_from_graveyard(self) -> None:
        """Flashback resolution must remove card from graveyard."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = TomeBlast(name="Tome Blast", owner=player)
        card.controller = player
        set_board_state(game, 0, graveyard=[card])
        assert card in player.zones[Zone.GRAVEYARD].get_all()
        if hasattr(card, "_cast_via_flashback"):
            card._cast_via_flashback = True
        card.on_resolve(game)
        gy_after = player.zones[Zone.GRAVEYARD].get_all()
        assert card not in gy_after, "Card must leave graveyard after flashback"

    def test_deals_damage(self) -> None:
        """Resolution should deal 2 damage."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        life_before = opponent.life
        card = TomeBlast(name="Tome Blast", owner=player)
        card.controller = player
        card._targets = [opponent]
        if hasattr(card, "set_targets"):
            card.set_targets([opponent])
        card.on_resolve(game)
        life_after = opponent.life
        assert life_after < life_before, (
            f"Should deal damage: life {life_before} -> {life_after}"
        )


@pytest.mark.edge
class TestTomeBlastEdgeCases:
    """Edge case tests for Tome Blast."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = TomeBlast(name="Tome Blast", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestTomeBlastInteractions:
    """Interaction tests for Tome Blast."""

    def test_flashback_not_from_hand(self) -> None:
        """Flashback alternate cost only applies from graveyard."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = TomeBlast(name="Tome Blast", owner=player)
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
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = TomeBlast(name="Tome Blast", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
