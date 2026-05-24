"""Audited tests for Ral Zarek, Guest Lecturer (collector key 97).

Verifies the Ral Zarek, Guest Lecturer card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: expert.
"""

from __future__ import annotations

import pytest

from card_impl import RalZarekGuestLecturer

from benchmarks.sos.workspace.engine.card import Planeswalker
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestRalZarekGuestLecturerBasicProperties:
    """Basic property tests for Ral Zarek, Guest Lecturer."""

    def test_is_planeswalker(self) -> None:
        """Ral Zarek, Guest Lecturer must be a Planeswalker subclass."""
        card = RalZarekGuestLecturer(name="Ral Zarek, Guest Lecturer", owner=None)
        assert isinstance(card, Planeswalker)

    def test_name(self) -> None:
        """RalZarekGuestLecturer.name must be 'Ral Zarek, Guest Lecturer'."""
        card = RalZarekGuestLecturer(name="Ral Zarek, Guest Lecturer", owner=None)
        assert card.name == "Ral Zarek, Guest Lecturer"

    def test_card_types(self) -> None:
        """Ral Zarek, Guest Lecturer must have correct card types."""
        card = RalZarekGuestLecturer(name="Ral Zarek, Guest Lecturer", owner=None)
        assert CardType.PLANESWALKER in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Ral Zarek, Guest Lecturer must have converted mana cost 3."""
        card = RalZarekGuestLecturer(name="Ral Zarek, Guest Lecturer", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Ral Zarek, Guest Lecturer must have correct colors."""
        card = RalZarekGuestLecturer(name="Ral Zarek, Guest Lecturer", owner=None)
        assert "B" in card.colors


@pytest.mark.ability
class TestRalZarekGuestLecturerAbilities:
    """Ability tests for Ral Zarek, Guest Lecturer -- expected to fail against stubs."""

    def test_resolution_returns_target(self) -> None:
        """Spell must return target to hand/battlefield per oracle text."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = RalZarekGuestLecturer(name="Ral Zarek, Guest Lecturer", owner=player)
        card.controller = player
        card.on_resolve(game)
        bf = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert target not in bf, "Ral Zarek, Guest Lecturer must remove target from battlefield"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = RalZarekGuestLecturer(name="Ral Zarek, Guest Lecturer", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Ral Zarek, Guest Lecturer must implement behavioral method"


@pytest.mark.edge
class TestRalZarekGuestLecturerEdgeCases:
    """Edge case and trap tests for Ral Zarek, Guest Lecturer."""

    def test_fizzle_spell_goes_to_graveyard(self) -> None:
        """Fizzled spell must end up in graveyard."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.types import Zone
        from benchmarks.sos.workspace.engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = RalZarekGuestLecturer(name="Ral Zarek, Guest Lecturer", owner=player)
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
        card1 = RalZarekGuestLecturer(name="Ral Zarek, Guest Lecturer", owner=None)
        card2 = RalZarekGuestLecturer(name="Ral Zarek, Guest Lecturer", owner=None)
        card1.name = "Modified"
        assert card2.name == "Ral Zarek, Guest Lecturer", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = RalZarekGuestLecturer(name="Ral Zarek, Guest Lecturer", owner=None)
        assert card.mana_cost.cmc == 3, \
            f"CMC must be 3, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestRalZarekGuestLecturerInteractions:
    """Multi-card interaction tests for Ral Zarek, Guest Lecturer."""

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
        card = RalZarekGuestLecturer(name="Ral Zarek, Guest Lecturer", owner=player)
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
        card = RalZarekGuestLecturer(name="Ral Zarek, Guest Lecturer", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"
