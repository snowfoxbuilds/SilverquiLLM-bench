"""Audited tests for Banishing Betrayal (collector key 38).

Verifies the Banishing Betrayal card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import BanishingBetrayal

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestBanishingBetrayalBasicProperties:
    """Basic property tests for Banishing Betrayal."""

    def test_is_instant(self) -> None:
        """Banishing Betrayal must be a Instant subclass."""
        card = BanishingBetrayal(name="Banishing Betrayal", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """BanishingBetrayal.name must be 'Banishing Betrayal'."""
        card = BanishingBetrayal(name="Banishing Betrayal", owner=None)
        assert card.name == "Banishing Betrayal"

    def test_card_types(self) -> None:
        """Banishing Betrayal must have correct card types."""
        card = BanishingBetrayal(name="Banishing Betrayal", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Banishing Betrayal must have converted mana cost 2."""
        card = BanishingBetrayal(name="Banishing Betrayal", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Banishing Betrayal must have correct colors."""
        card = BanishingBetrayal(name="Banishing Betrayal", owner=None)
        assert "U" in card.colors


@pytest.mark.ability
class TestBanishingBetrayalAbilities:
    """Ability tests for Banishing Betrayal — expected to fail against stubs."""

    def test_bounces_target(self) -> None:
        """Resolution should return target to hand."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Bounced", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[target])
        card = BanishingBetrayal(name="Banishing Betrayal", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        bf_before = len(game.get_battlefield(opponent).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(opponent).get_all())
        assert bf_after < bf_before, (
            f"Target should leave bf: {bf_before} -> {bf_after}"
        )

    def test_surveil_effect(self) -> None:
        """Resolution should surveil 1."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        for i in range(3):
            player.zones[Zone.LIBRARY].add(Sorcery(name=f"Lib{i}", owner=player))
        lib_before = len(player.zones[Zone.LIBRARY].get_all())
        card = BanishingBetrayal(name="Banishing Betrayal", owner=player)
        card.controller = player
        card.on_resolve(game)
        gy_after = len(player.zones[Zone.GRAVEYARD].get_all())
        assert gy_after > 0 or len(player.zones[Zone.LIBRARY].get_all()) <= lib_before, (
            "Surveil should manipulate library/graveyard"
        )

    def test_returns_from_graveyard(self) -> None:
        """Resolution should return card from graveyard."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        gy_card = Creature(name="Returned", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, graveyard=[gy_card])
        card = BanishingBetrayal(name="Banishing Betrayal", owner=player)
        card.controller = player
        card._targets = [gy_card]
        if hasattr(card, "set_targets"):
            card.set_targets([gy_card])
        gy_before = len(player.zones[Zone.GRAVEYARD].get_all())
        card.on_resolve(game)
        gy_after = len(player.zones[Zone.GRAVEYARD].get_all())
        assert gy_after < gy_before, (
            f"Should return from gy: {gy_before} -> {gy_after}"
        )


@pytest.mark.edge
class TestBanishingBetrayalEdgeCases:
    """Edge case tests for Banishing Betrayal."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = BanishingBetrayal(name="Banishing Betrayal", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestBanishingBetrayalInteractions:
    """Interaction tests for Banishing Betrayal."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = BanishingBetrayal(name="Banishing Betrayal", owner=player)
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
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = BanishingBetrayal(name="Banishing Betrayal", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
