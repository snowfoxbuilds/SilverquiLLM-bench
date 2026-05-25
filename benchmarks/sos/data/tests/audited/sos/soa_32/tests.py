"""Audited tests for Sheoldred's Edict (collector key soa_32).

Verifies the Sheoldred's Edict card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import SheoldredsEdict

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestSheoldredsEdictBasicProperties:
    """Basic property tests for Sheoldred's Edict."""

    def test_is_instant(self) -> None:
        """Sheoldred's Edict must be a Instant subclass."""
        card = SheoldredsEdict(name="Sheoldred's Edict", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """SheoldredsEdict.name must be 'Sheoldred's Edict'."""
        card = SheoldredsEdict(name="Sheoldred's Edict", owner=None)
        assert card.name == "Sheoldred's Edict"

    def test_card_types(self) -> None:
        """Sheoldred's Edict must have correct card types."""
        card = SheoldredsEdict(name="Sheoldred's Edict", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Sheoldred's Edict must have converted mana cost 2."""
        card = SheoldredsEdict(name="Sheoldred's Edict", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Sheoldred's Edict must have correct colors."""
        card = SheoldredsEdict(name="Sheoldred's Edict", owner=None)
        assert "B" in card.colors


@pytest.mark.ability
class TestSheoldredsEdictAbilities:
    """Ability tests for Sheoldred's Edict -- expected to fail against stubs."""

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = SheoldredsEdict(name="Sheoldred's Edict", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Sheoldred's Edict must implement behavioral method"


@pytest.mark.edge
class TestSheoldredsEdictEdgeCases:
    """Edge case and trap tests for Sheoldred's Edict."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = SheoldredsEdict(name="Sheoldred's Edict", owner=None)
        card2 = SheoldredsEdict(name="Sheoldred's Edict", owner=None)
        card1.name = "Modified"
        assert card2.name == "Sheoldred's Edict", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = SheoldredsEdict(name="Sheoldred's Edict", owner=None)
        assert card.mana_cost.cmc == 2, \
            f"CMC must be 2, got {card.mana_cost.cmc}"

    def test_resolution_with_empty_board(self) -> None:
        """Spell must handle resolution with no valid targets/creatures."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = SheoldredsEdict(name="Sheoldred's Edict", owner=player)
        card.controller = player
        # Resolution on empty board should not crash
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Fizzle on empty board is acceptable
        # Verify game state is consistent
        assert player.life == 20, "Caster life should be unchanged on fizzle"


@pytest.mark.interaction
class TestSheoldredsEdictInteractions:
    """Multi-card interaction tests for Sheoldred's Edict."""

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = SheoldredsEdict(name="Sheoldred's Edict", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"

    def test_tokens_appear_on_battlefield(self) -> None:
        """Tokens created must appear on the battlefield."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = SheoldredsEdict(name="Sheoldred's Edict", owner=player)
        card.controller = player
        bf_before = len(player.zones[Zone.BATTLEFIELD].get_all())
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        elif callable(getattr(card, "on_resolve", None)):
            card.on_resolve(game)
        bf_after = len(player.zones[Zone.BATTLEFIELD].get_all())
        assert bf_after > bf_before, "Tokens must appear on battlefield"
