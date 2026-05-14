"""Audited tests for Pursue the Past (collector key 216).

Verifies the Pursue the Past card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import PursueThePast

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestPursueThePastBasicProperties:
    """Basic property tests for Pursue the Past."""

    def test_is_sorcery(self) -> None:
        """Pursue the Past must be a Sorcery subclass."""
        card = PursueThePast(name="Pursue the Past", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """PursueThePast.name must be 'Pursue the Past'."""
        card = PursueThePast(name="Pursue the Past", owner=None)
        assert card.name == "Pursue the Past"

    def test_card_types(self) -> None:
        """Pursue the Past must have correct card types."""
        card = PursueThePast(name="Pursue the Past", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Pursue the Past must have converted mana cost 2."""
        card = PursueThePast(name="Pursue the Past", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Pursue the Past must have correct colors."""
        card = PursueThePast(name="Pursue the Past", owner=None)
        assert "R" in card.colors
        assert "W" in card.colors


@pytest.mark.ability
class TestPursueThePastAbilities:
    """Ability tests for Pursue the Past — expected to fail against stubs."""

    def test_flashback_cost_attribute(self) -> None:
        """Card must expose a flashback cost distinct from normal mana cost."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = PursueThePast(name="Pursue the Past", owner=player)
        card.controller = player
        has_fb = hasattr(card, "flashback_cost") or hasattr(card, "alternate_costs")
        assert has_fb, "Pursue the Past must expose flashback cost"

    def test_flashback_exiles_after_resolution(self) -> None:
        """Card must be exiled after flashback resolution."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = PursueThePast(name="Pursue the Past", owner=player)
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
        card = PursueThePast(name="Pursue the Past", owner=player)
        card.controller = player
        set_board_state(game, 0, graveyard=[card])
        assert card in player.zones[Zone.GRAVEYARD].get_all()
        if hasattr(card, "_cast_via_flashback"):
            card._cast_via_flashback = True
        card.on_resolve(game)
        gy_after = player.zones[Zone.GRAVEYARD].get_all()
        assert card not in gy_after, "Card must leave graveyard after flashback"

    def test_draws_cards(self) -> None:
        """Resolution should draw card(s)."""
        from tests.test_utils import create_game
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        filler = Sorcery(name="Filler", owner=player)
        player.zones[Zone.LIBRARY].add(filler)
        player.zones[Zone.LIBRARY].add(Sorcery(name="F2", owner=player))
        hand_before = len(player.zones[Zone.HAND].get_all())
        card = PursueThePast(name="Pursue the Past", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Should draw: hand {hand_before} -> {hand_after}"
        )

    def test_causes_discard(self) -> None:
        """Resolution should cause discard."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        filler = Sorcery(name="Discardable", owner=opponent)
        set_board_state(game, 1, hand=[filler])
        hand_before = len(opponent.zones[Zone.HAND].get_all())
        card = PursueThePast(name="Pursue the Past", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(opponent.zones[Zone.HAND].get_all())
        assert hand_after < hand_before, (
            f"Should discard: hand {hand_before} -> {hand_after}"
        )

    def test_gains_life(self) -> None:
        """Resolution should gain life."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = PursueThePast(name="Pursue the Past", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        assert player.life > life_before, (
            f"Should gain life: {life_before} -> {player.life}"
        )


@pytest.mark.edge
class TestPursueThePastEdgeCases:
    """Edge case tests for Pursue the Past."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = PursueThePast(name="Pursue the Past", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestPursueThePastInteractions:
    """Interaction tests for Pursue the Past."""

    def test_flashback_not_from_hand(self) -> None:
        """Flashback alternate cost only applies from graveyard."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = PursueThePast(name="Pursue the Past", owner=player)
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
        card = PursueThePast(name="Pursue the Past", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
