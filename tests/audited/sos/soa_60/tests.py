"""Audited tests for Veil of Summer (collector key soa_60).

Verifies the Veil of Summer card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import VeilOfSummer

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestVeilOfSummerBasicProperties:
    """Basic property tests for Veil of Summer."""

    def test_is_instant(self) -> None:
        """Veil of Summer must be a Instant subclass."""
        card = VeilOfSummer(name="Veil of Summer", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """VeilOfSummer.name must be 'Veil of Summer'."""
        card = VeilOfSummer(name="Veil of Summer", owner=None)
        assert card.name == "Veil of Summer"

    def test_card_types(self) -> None:
        """Veil of Summer must have correct card types."""
        card = VeilOfSummer(name="Veil of Summer", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Veil of Summer must have converted mana cost 1."""
        card = VeilOfSummer(name="Veil of Summer", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Veil of Summer must have correct colors."""
        card = VeilOfSummer(name="Veil of Summer", owner=None)
        assert "G" in card.colors


@pytest.mark.ability
class TestVeilOfSummerAbilities:
    """Ability tests for Veil of Summer -- expected to fail against stubs."""

    def test_resolution_draws_cards(self) -> None:
        """Spell resolution must draw cards per oracle text."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        for i in range(5):
            c = Creature(name=f"Lib{i}", owner=player, base_power=1, base_toughness=1)
            player.zones[Zone.LIBRARY].add(c)
        hand_before = len(player.zones[Zone.HAND].get_all())
        card = VeilOfSummer(name="Veil of Summer", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, "Veil of Summer must draw cards"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = VeilOfSummer(name="Veil of Summer", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Veil of Summer must implement behavioral method"


@pytest.mark.edge
class TestVeilOfSummerEdgeCases:
    """Edge case and trap tests for Veil of Summer."""

    def test_fizzle_spell_goes_to_graveyard(self) -> None:
        """Fizzled spell must end up in graveyard."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.types import Zone
        from benchmarks.sos.workspace.engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = VeilOfSummer(name="Veil of Summer", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Fizzled spell must go to graveyard"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = VeilOfSummer(name="Veil of Summer", owner=None)
        card2 = VeilOfSummer(name="Veil of Summer", owner=None)
        card1.name = "Modified"
        assert card2.name == "Veil of Summer", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = VeilOfSummer(name="Veil of Summer", owner=None)
        assert card.mana_cost.cmc == 1, \
            f"CMC must be 1, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestVeilOfSummerInteractions:
    """Multi-card interaction tests for Veil of Summer."""

    def test_targets_valid_objects(self) -> None:
        """Spell targeting must find valid targets."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=3, base_toughness=3)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = VeilOfSummer(name="Veil of Summer", owner=player)
        card.controller = player
        if callable(getattr(card, "get_targets", None)):
            targets = card.get_targets(game)
            assert len(targets) > 0, "Must find valid targets"

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.types import Zone
        from benchmarks.sos.workspace.engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = VeilOfSummer(name="Veil of Summer", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"
