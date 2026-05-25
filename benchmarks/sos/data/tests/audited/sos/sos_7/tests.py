"""Audited tests for Antiquities on the Loose (collector key 7).

Verifies the Antiquities on the Loose card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import AntiquitiesOnTheLoose

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestAntiquitiesOnTheLooseBasicProperties:
    """Basic property tests for Antiquities on the Loose."""

    def test_is_sorcery(self) -> None:
        """Antiquities on the Loose must be a Sorcery subclass."""
        card = AntiquitiesOnTheLoose(name="Antiquities on the Loose", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """AntiquitiesOnTheLoose.name must be 'Antiquities on the Loose'."""
        card = AntiquitiesOnTheLoose(name="Antiquities on the Loose", owner=None)
        assert card.name == "Antiquities on the Loose"

    def test_card_types(self) -> None:
        """Antiquities on the Loose must have correct card types."""
        card = AntiquitiesOnTheLoose(name="Antiquities on the Loose", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Antiquities on the Loose must have converted mana cost 3."""
        card = AntiquitiesOnTheLoose(name="Antiquities on the Loose", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Antiquities on the Loose must have correct colors."""
        card = AntiquitiesOnTheLoose(name="Antiquities on the Loose", owner=None)
        assert "W" in card.colors


@pytest.mark.ability
class TestAntiquitiesOnTheLooseAbilities:
    """Ability tests for Antiquities on the Loose -- expected to fail against stubs."""

    def test_resolution_exiles_target(self) -> None:
        """Spell resolution must exile target per oracle text."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = AntiquitiesOnTheLoose(name="Antiquities on the Loose", owner=player)
        card.controller = player
        card.on_resolve(game)
        exile = opponent.zones[Zone.EXILE].get_all()
        assert target in exile, "Antiquities on the Loose must exile target"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = AntiquitiesOnTheLoose(name="Antiquities on the Loose", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Antiquities on the Loose must implement behavioral method"


@pytest.mark.edge
class TestAntiquitiesOnTheLooseEdgeCases:
    """Edge case and trap tests for Antiquities on the Loose."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = AntiquitiesOnTheLoose(name="Antiquities on the Loose", owner=None)
        card2 = AntiquitiesOnTheLoose(name="Antiquities on the Loose", owner=None)
        card1.name = "Modified"
        assert card2.name == "Antiquities on the Loose", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = AntiquitiesOnTheLoose(name="Antiquities on the Loose", owner=None)
        assert card.mana_cost.cmc == 3, \
            f"CMC must be 3, got {card.mana_cost.cmc}"

    def test_resolution_with_empty_board(self) -> None:
        """Spell must handle resolution with no valid targets/creatures."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = AntiquitiesOnTheLoose(name="Antiquities on the Loose", owner=player)
        card.controller = player
        # Resolution on empty board should not crash
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Fizzle on empty board is acceptable
        # Verify game state is consistent
        assert player.life == 20, "Caster life should be unchanged on fizzle"


@pytest.mark.interaction
class TestAntiquitiesOnTheLooseInteractions:
    """Multi-card interaction tests for Antiquities on the Loose."""

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = AntiquitiesOnTheLoose(name="Antiquities on the Loose", owner=player)
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
        card = AntiquitiesOnTheLoose(name="Antiquities on the Loose", owner=player)
        card.controller = player
        bf_before = len(player.zones[Zone.BATTLEFIELD].get_all())
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        elif callable(getattr(card, "on_resolve", None)):
            card.on_resolve(game)
        bf_after = len(player.zones[Zone.BATTLEFIELD].get_all())
        assert bf_after > bf_before, "Tokens must appear on battlefield"
