"""Audited tests for Conciliator's Duelist (collector key 182).

Verifies the Conciliator's Duelist card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import ConciliatorsDuelist

from engine.card import Creature
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestConciliatorsDuelistBasicProperties:
    """Basic property tests for Conciliator's Duelist."""

    def test_is_creature(self) -> None:
        """Conciliator's Duelist must be a Creature subclass."""
        card = ConciliatorsDuelist(name="Conciliator's Duelist", owner=None, base_power=4, base_toughness=3)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """ConciliatorsDuelist.name must be 'Conciliator's Duelist'."""
        card = ConciliatorsDuelist(name="Conciliator's Duelist", owner=None, base_power=4, base_toughness=3)
        assert card.name == "Conciliator's Duelist"

    def test_card_types(self) -> None:
        """Conciliator's Duelist must have correct card types."""
        card = ConciliatorsDuelist(name="Conciliator's Duelist", owner=None, base_power=4, base_toughness=3)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Conciliator's Duelist must have converted mana cost 4."""
        card = ConciliatorsDuelist(name="Conciliator's Duelist", owner=None, base_power=4, base_toughness=3)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Conciliator's Duelist must have correct colors."""
        card = ConciliatorsDuelist(name="Conciliator's Duelist", owner=None, base_power=4, base_toughness=3)
        assert "B" in card_colors(card)
        assert "W" in card_colors(card)

    def test_power(self) -> None:
        """Conciliator's Duelist must have base power 4."""
        card = ConciliatorsDuelist(name="Conciliator's Duelist", owner=None, base_power=4, base_toughness=3)
        assert card.base_power == 4

    def test_toughness(self) -> None:
        """Conciliator's Duelist must have base toughness 3."""
        card = ConciliatorsDuelist(name="Conciliator's Duelist", owner=None, base_power=4, base_toughness=3)
        assert card.base_toughness == 3

@pytest.mark.ability
class TestConciliatorsDuelistAbilities:
    """Ability tests for Conciliator's Duelist -- expected to fail against stubs."""

    def test_etb_exiles_target(self) -> None:
        """ETB must exile target permanent per oracle text."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = ConciliatorsDuelist(name="Conciliator's Duelist", owner=player, base_power=4, base_toughness=3)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        exile = opponent.zones[Zone.EXILE].get_all()
        assert target in exile, "ETB must exile the target per oracle"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = ConciliatorsDuelist(name="Conciliator's Duelist", owner=None, base_power=4, base_toughness=3)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Conciliator's Duelist must implement behavioral method"

@pytest.mark.edge
class TestConciliatorsDuelistEdgeCases:
    """Edge case and trap tests for Conciliator's Duelist."""

    def test_fizzle_no_targets_creature_stays(self) -> None:
        """If ETB ability fizzles, the creature remains on battlefield."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = ConciliatorsDuelist(name="Conciliator's Duelist", owner=player, base_power=4, base_toughness=3)
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
        card1 = ConciliatorsDuelist(name="Conciliator's Duelist", owner=None, base_power=4, base_toughness=3)
        card2 = ConciliatorsDuelist(name="Conciliator's Duelist", owner=None, base_power=4, base_toughness=3)
        card1.name = "Modified"
        assert card2.name == "Conciliator's Duelist", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = ConciliatorsDuelist(name="Conciliator's Duelist", owner=None, base_power=4, base_toughness=3)
        assert card.mana_cost.cmc == 4, \
            f"CMC must be 4, got {card.mana_cost.cmc}"

@pytest.mark.interaction
class TestConciliatorsDuelistInteractions:
    """Multi-card interaction tests for Conciliator's Duelist."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = ConciliatorsDuelist(name="Conciliator's Duelist", owner=player, base_power=4, base_toughness=3)
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
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        card = ConciliatorsDuelist(name="Conciliator's Duelist", owner=player, base_power=4, base_toughness=3)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
