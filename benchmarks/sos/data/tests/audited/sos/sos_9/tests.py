"""Audited tests for Daydream (collector key 9).

Verifies the Daydream card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import Daydream

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestDaydreamBasicProperties:
    """Basic property tests for Daydream."""

    def test_is_sorcery(self) -> None:
        """Daydream must be a Sorcery subclass."""
        card = Daydream(name="Daydream", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """Daydream.name must be 'Daydream'."""
        card = Daydream(name="Daydream", owner=None)
        assert card.name == "Daydream"

    def test_card_types(self) -> None:
        """Daydream must have correct card types."""
        card = Daydream(name="Daydream", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Daydream must have converted mana cost 1."""
        card = Daydream(name="Daydream", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Daydream must have correct colors."""
        card = Daydream(name="Daydream", owner=None)
        assert "W" in card.colors


@pytest.mark.ability
class TestDaydreamAbilities:
    """Ability tests for Daydream — expected to fail against stubs."""

    def test_flashback_cost_attribute(self) -> None:
        """Card must expose a flashback cost distinct from normal mana cost."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = Daydream(name="Daydream", owner=player)
        card.controller = player
        has_fb = hasattr(card, "flashback_cost") or hasattr(card, "alternate_costs")
        assert has_fb, "Daydream must expose flashback cost"

    def test_flashback_exiles_after_resolution(self) -> None:
        """Card must be exiled after flashback resolution."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = Daydream(name="Daydream", owner=player)
        card.controller = player
        set_board_state(game, 0, graveyard=[card])
        if hasattr(card, "_cast_via_flashback"):
            card._cast_via_flashback = True
        card.on_resolve(game)
        exile = player.zones[Zone.EXILE].get_all()
        assert card in exile, "Card must be exiled after flashback resolution"

    def test_flashback_removes_from_graveyard(self) -> None:
        """Flashback resolution must remove card from graveyard."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = Daydream(name="Daydream", owner=player)
        card.controller = player
        set_board_state(game, 0, graveyard=[card])
        assert card in player.zones[Zone.GRAVEYARD].get_all()
        if hasattr(card, "_cast_via_flashback"):
            card._cast_via_flashback = True
        card.on_resolve(game)
        gy_after = player.zones[Zone.GRAVEYARD].get_all()
        assert card not in gy_after, "Card must leave graveyard after flashback"

    def test_adds_plus_counter(self) -> None:
        """Resolution should add +1/+1 counter to target."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="Target", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = Daydream(name="Daydream", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        power_before = target.base_power
        card.on_resolve(game)
        power_after = target.power if hasattr(target, "power") else target.base_power
        assert power_after > power_before, (
            f"+1/+1 counter: power {power_before} -> {power_after}"
        )

    def test_exiles_target(self) -> None:
        """Resolution should exile the target."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        target = Creature(name="Exiled", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = Daydream(name="Daydream", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        exile = player.zones[Zone.EXILE].get_all()
        assert target in exile, "Target should be in exile"

    def test_flicker_returns_to_battlefield(self) -> None:
        """Flicker should exile then return to battlefield."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="Flickered", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = Daydream(name="Daydream", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        bf_after = game.get_battlefield(player).get_all()
        assert target in bf_after, "Flickered creature should return to battlefield"


@pytest.mark.edge
class TestDaydreamEdgeCases:
    """Edge case tests for Daydream."""

    def test_targets_only_own_permanents(self) -> None:
        """Should only target permanents you control."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        own = Creature(name="Own", owner=player, base_power=2, base_toughness=2)
        enemy = Creature(name="Enemy", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[own])
        set_board_state(game, 1, battlefield=[enemy])
        card = Daydream(name="Daydream", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        if len(targets) > 0:
            assert own in targets, "Own creature should be valid"
            assert enemy not in targets, "Opponent creature should be invalid"


@pytest.mark.interaction
class TestDaydreamInteractions:
    """Interaction tests for Daydream."""

    def test_get_targets_finds_own_creatures(self) -> None:
        """get_targets should return valid own creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        creature = Creature(name="Mine", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[creature])
        card = Daydream(name="Daydream", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find own creature as target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = Daydream(name="Daydream", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
