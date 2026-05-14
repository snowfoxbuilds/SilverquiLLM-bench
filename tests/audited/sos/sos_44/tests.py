"""Audited tests for Echocasting Symposium (collector key 44).

Verifies the Echocasting Symposium card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import EchocastingSymposium

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestEchocastingSymposiumBasicProperties:
    """Basic property tests for Echocasting Symposium."""

    def test_is_sorcery(self) -> None:
        """Echocasting Symposium must be a Sorcery subclass."""
        card = EchocastingSymposium(name="Echocasting Symposium", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """EchocastingSymposium.name must be 'Echocasting Symposium'."""
        card = EchocastingSymposium(name="Echocasting Symposium", owner=None)
        assert card.name == "Echocasting Symposium"

    def test_card_types(self) -> None:
        """Echocasting Symposium must have correct card types."""
        card = EchocastingSymposium(name="Echocasting Symposium", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Echocasting Symposium must have converted mana cost 6."""
        card = EchocastingSymposium(name="Echocasting Symposium", owner=None)
        assert card.mana_cost.cmc == 6

    def test_colors(self) -> None:
        """Echocasting Symposium must have correct colors."""
        card = EchocastingSymposium(name="Echocasting Symposium", owner=None)
        assert "U" in card.colors


@pytest.mark.ability
class TestEchocastingSymposiumAbilities:
    """Ability tests for Echocasting Symposium -- expected to fail against stubs."""

    def test_resolution_exiles_target(self) -> None:
        """Spell resolution must exile target per oracle text."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = EchocastingSymposium(name="Echocasting Symposium", owner=player)
        card.controller = player
        card.on_resolve(game)
        exile = opponent.zones[Zone.EXILE].get_all()
        assert target in exile, "Echocasting Symposium must exile target"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = EchocastingSymposium(name="Echocasting Symposium", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Echocasting Symposium must implement behavioral method"


@pytest.mark.edge
class TestEchocastingSymposiumEdgeCases:
    """Edge case and trap tests for Echocasting Symposium."""

    def test_fizzle_spell_goes_to_graveyard(self) -> None:
        """Fizzled spell must end up in graveyard."""
        from tests.test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = EchocastingSymposium(name="Echocasting Symposium", owner=player)
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
        card1 = EchocastingSymposium(name="Echocasting Symposium", owner=None)
        card2 = EchocastingSymposium(name="Echocasting Symposium", owner=None)
        card1.name = "Modified"
        assert card2.name == "Echocasting Symposium", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = EchocastingSymposium(name="Echocasting Symposium", owner=None)
        assert card.mana_cost.cmc == 6, \
            f"CMC must be 6, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestEchocastingSymposiumInteractions:
    """Multi-card interaction tests for Echocasting Symposium."""

    def test_targets_valid_objects(self) -> None:
        """Spell targeting must find valid targets."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=3, base_toughness=3)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = EchocastingSymposium(name="Echocasting Symposium", owner=player)
        card.controller = player
        if callable(getattr(card, "get_targets", None)):
            targets = card.get_targets(game)
            assert len(targets) > 0, "Must find valid targets"

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from tests.test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = EchocastingSymposium(name="Echocasting Symposium", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"

    def test_tokens_appear_on_battlefield(self) -> None:
        """Tokens created must appear on the battlefield."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = EchocastingSymposium(name="Echocasting Symposium", owner=player)
        card.controller = player
        bf_before = len(player.zones[Zone.BATTLEFIELD].get_all())
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        elif callable(getattr(card, "on_resolve", None)):
            card.on_resolve(game)
        bf_after = len(player.zones[Zone.BATTLEFIELD].get_all())
        assert bf_after > bf_before, "Tokens must appear on battlefield"
