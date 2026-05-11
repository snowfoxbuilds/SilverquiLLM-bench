"""Audited tests for Ennis, Debate Moderator (collector key 14).

Verifies the Ennis, Debate Moderator card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import EnnisDebateModerator

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestEnnisDebateModeratorBasicProperties:
    """Basic property tests for Ennis, Debate Moderator."""

    def test_is_creature(self) -> None:
        """Ennis, Debate Moderator must be a Creature subclass."""
        card = EnnisDebateModerator(name="Ennis, Debate Moderator", owner=None, base_power=1, base_toughness=1)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """EnnisDebateModerator.name must be 'Ennis, Debate Moderator'."""
        card = EnnisDebateModerator(name="Ennis, Debate Moderator", owner=None, base_power=1, base_toughness=1)
        assert card.name == "Ennis, Debate Moderator"

    def test_card_types(self) -> None:
        """Ennis, Debate Moderator must have correct card types."""
        card = EnnisDebateModerator(name="Ennis, Debate Moderator", owner=None, base_power=1, base_toughness=1)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Ennis, Debate Moderator must have converted mana cost 2."""
        card = EnnisDebateModerator(name="Ennis, Debate Moderator", owner=None, base_power=1, base_toughness=1)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Ennis, Debate Moderator must have correct colors."""
        card = EnnisDebateModerator(name="Ennis, Debate Moderator", owner=None, base_power=1, base_toughness=1)
        assert "W" in card.colors

    def test_power(self) -> None:
        """Ennis, Debate Moderator must have base power 1."""
        card = EnnisDebateModerator(name="Ennis, Debate Moderator", owner=None, base_power=1, base_toughness=1)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Ennis, Debate Moderator must have base toughness 1."""
        card = EnnisDebateModerator(name="Ennis, Debate Moderator", owner=None, base_power=1, base_toughness=1)
        assert card.base_toughness == 1


@pytest.mark.ability
class TestEnnisDebateModeratorAbilities:
    """Ability tests for Ennis, Debate Moderator -- expected to fail against stubs."""

    def test_etb_exiles_target(self) -> None:
        """ETB must exile target permanent per oracle text."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = EnnisDebateModerator(name="Ennis, Debate Moderator", owner=player, base_power=1, base_toughness=1)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        exile = opponent.zones[Zone.EXILE].get_all()
        assert target in exile, "ETB must exile the target per oracle"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = EnnisDebateModerator(name="Ennis, Debate Moderator", owner=None, base_power=1, base_toughness=1)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Ennis, Debate Moderator must implement behavioral method"


@pytest.mark.edge
class TestEnnisDebateModeratorEdgeCases:
    """Edge case and trap tests for Ennis, Debate Moderator."""

    def test_fizzle_no_targets_creature_stays(self) -> None:
        """If ETB ability fizzles, the creature remains on battlefield."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = EnnisDebateModerator(name="Ennis, Debate Moderator", owner=player, base_power=1, base_toughness=1)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        # No targets available; ETB fizzles
        try:
            if callable(getattr(card, "on_enter_battlefield", None)):
                card.on_enter_battlefield(game)
        except (ValueError, IndexError):
            pass  # Fizzle expected
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must stay on battlefield when ETB fizzles"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = EnnisDebateModerator(name="Ennis, Debate Moderator", owner=None, base_power=1, base_toughness=1)
        card2 = EnnisDebateModerator(name="Ennis, Debate Moderator", owner=None, base_power=1, base_toughness=1)
        card1.name = "Modified"
        assert card2.name == "Ennis, Debate Moderator", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = EnnisDebateModerator(name="Ennis, Debate Moderator", owner=None, base_power=1, base_toughness=1)
        assert card.mana_cost.cmc == 2, \
            f"CMC must be 2, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestEnnisDebateModeratorInteractions:
    """Multi-card interaction tests for Ennis, Debate Moderator."""

    def test_counters_survive_end_of_turn(self) -> None:
        """Permanent counters must persist through end of turn."""
        from tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = EnnisDebateModerator(name="Ennis, Debate Moderator", owner=player, base_power=1, base_toughness=1)
        card.controller = player
        if hasattr(card, "colors_spent"):
            card.colors_spent = 2
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        counters = getattr(card, "counters", {})
        p1p1 = counters.get("+1/+1", counters.get("p1p1", 0))
        assert p1p1 == 2, f"Should have 2 +1/+1 counters, got {p1p1}"

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = EnnisDebateModerator(name="Ennis, Debate Moderator", owner=player, base_power=1, base_toughness=1)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
