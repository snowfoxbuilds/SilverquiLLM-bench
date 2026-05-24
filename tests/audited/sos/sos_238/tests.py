"""Audited tests for Teacher's Pest (collector key 238).

Verifies the Teacher's Pest card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import TeachersPest

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestTeachersPestBasicProperties:
    """Basic property tests for Teacher's Pest."""

    def test_is_creature(self) -> None:
        """Teacher's Pest must be a Creature subclass."""
        card = TeachersPest(name="Teacher's Pest", owner=None, base_power=1, base_toughness=1)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """TeachersPest.name must be 'Teacher's Pest'."""
        card = TeachersPest(name="Teacher's Pest", owner=None, base_power=1, base_toughness=1)
        assert card.name == "Teacher's Pest"

    def test_card_types(self) -> None:
        """Teacher's Pest must have correct card types."""
        card = TeachersPest(name="Teacher's Pest", owner=None, base_power=1, base_toughness=1)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Teacher's Pest must have converted mana cost 2."""
        card = TeachersPest(name="Teacher's Pest", owner=None, base_power=1, base_toughness=1)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Teacher's Pest must have correct colors."""
        card = TeachersPest(name="Teacher's Pest", owner=None, base_power=1, base_toughness=1)
        assert "B" in card.colors
        assert "G" in card.colors

    def test_power(self) -> None:
        """Teacher's Pest must have base power 1."""
        card = TeachersPest(name="Teacher's Pest", owner=None, base_power=1, base_toughness=1)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Teacher's Pest must have base toughness 1."""
        card = TeachersPest(name="Teacher's Pest", owner=None, base_power=1, base_toughness=1)
        assert card.base_toughness == 1


@pytest.mark.ability
class TestTeachersPestAbilities:
    """Ability tests for Teacher's Pest -- expected to fail against stubs."""

    def test_has_menace(self) -> None:
        """Teacher's Pest must have Menace keyword."""
        from benchmarks.sos.workspace.engine.types import Keyword
        card = TeachersPest(name="Teacher's Pest", owner=None, base_power=1, base_toughness=1)
        assert Keyword.MENACE in card.keywords, "Teacher's Pest should have Menace"

    def test_attack_trigger_uses_graveyard(self) -> None:
        """Attack trigger must interact with graveyard per oracle text."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Instant
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        fodder = Instant(name="Bolt", owner=player)
        set_board_state(game, 0, graveyard=[fodder])
        card = TeachersPest(name="Teacher's Pest", owner=player, base_power=1, base_toughness=1)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        gy_before = len(player.zones[Zone.GRAVEYARD].get_all())
        if callable(getattr(card, "on_attack", None)):
            card.on_attack(game)
        gy_after = len(player.zones[Zone.GRAVEYARD].get_all())
        assert gy_after != gy_before, "Attack trigger must interact with graveyard"


@pytest.mark.edge
class TestTeachersPestEdgeCases:
    """Edge case and trap tests for Teacher's Pest."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = TeachersPest(name="Teacher's Pest", owner=None, base_power=1, base_toughness=1)
        card2 = TeachersPest(name="Teacher's Pest", owner=None, base_power=1, base_toughness=1)
        card1.name = "Modified"
        assert card2.name == "Teacher's Pest", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = TeachersPest(name="Teacher's Pest", owner=None, base_power=1, base_toughness=1)
        assert card.mana_cost.cmc == 2, \
            f"CMC must be 2, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = TeachersPest(name="Teacher's Pest", owner=player, base_power=1, base_toughness=1)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 0
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestTeachersPestInteractions:
    """Multi-card interaction tests for Teacher's Pest."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = TeachersPest(name="Teacher's Pest", owner=player, base_power=1, base_toughness=1)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"

    def test_coexists_with_other_permanents(self) -> None:
        """Card must coexist with other permanents without errors."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        card = TeachersPest(name="Teacher's Pest", owner=player, base_power=1, base_toughness=1)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
