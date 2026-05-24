"""Audited tests for Shamanic Revelation (collector key soa_57).

Verifies the Shamanic Revelation card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import ShamanicRevelation

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestShamanicRevelationBasicProperties:
    """Basic property tests for Shamanic Revelation."""

    def test_is_sorcery(self) -> None:
        """Shamanic Revelation must be a Sorcery subclass."""
        card = ShamanicRevelation(name="Shamanic Revelation", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """ShamanicRevelation.name must be 'Shamanic Revelation'."""
        card = ShamanicRevelation(name="Shamanic Revelation", owner=None)
        assert card.name == "Shamanic Revelation"

    def test_card_types(self) -> None:
        """Shamanic Revelation must have correct card types."""
        card = ShamanicRevelation(name="Shamanic Revelation", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Shamanic Revelation must have converted mana cost 5."""
        card = ShamanicRevelation(name="Shamanic Revelation", owner=None)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Shamanic Revelation must have correct colors."""
        card = ShamanicRevelation(name="Shamanic Revelation", owner=None)
        assert "G" in card.colors


@pytest.mark.ability
class TestShamanicRevelationAbilities:
    """Ability tests for Shamanic Revelation — expected to fail against stubs."""

    def test_draws_cards(self) -> None:
        """Resolution should draw card(s)."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.card import Sorcery
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        filler = Sorcery(name="Filler", owner=player)
        player.zones[Zone.LIBRARY].add(filler)
        player.zones[Zone.LIBRARY].add(Sorcery(name="F2", owner=player))
        hand_before = len(player.zones[Zone.HAND].get_all())
        card = ShamanicRevelation(name="Shamanic Revelation", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Should draw: hand {hand_before} -> {hand_after}"
        )

    def test_gains_life(self) -> None:
        """Resolution should gain life."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = ShamanicRevelation(name="Shamanic Revelation", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        assert player.life > life_before, (
            f"Should gain life: {life_before} -> {player.life}"
        )


@pytest.mark.edge
class TestShamanicRevelationEdgeCases:
    """Edge case tests for Shamanic Revelation."""

    def test_power_targeting_restriction(self) -> None:
        """Only targets creatures with power 4 or greater."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        small = Creature(name="Small", owner=opponent, base_power=3, base_toughness=2)
        big = Creature(name="Big", owner=opponent, base_power=4, base_toughness=2)
        set_board_state(game, 1, battlefield=[small, big])
        card = ShamanicRevelation(name="Shamanic Revelation", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert big in targets, "Power >= 4 should be valid"
        assert small not in targets, "Power < 4 should be invalid"


@pytest.mark.interaction
class TestShamanicRevelationInteractions:
    """Interaction tests for Shamanic Revelation."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = ShamanicRevelation(name="Shamanic Revelation", owner=player)
        card.controller = player
        card._targets = [t1]
        if hasattr(card, "set_targets"):
            card.set_targets([t1])
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Non-targeted creature should remain
        bf = game.get_battlefield(opponent).get_all()
        assert t2 in bf, "Non-targeted creature should remain"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = ShamanicRevelation(name="Shamanic Revelation", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
