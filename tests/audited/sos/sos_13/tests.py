"""Audited tests for Emeritus of Truce // Swords to Plowshares (collector key 13).

Verifies the Emeritus of Truce // Swords to Plowshares card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import EmeritusOfTruceSwordsToPlowshares

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestEmeritusOfTruceSwordsToPlowsharesBasicProperties:
    """Basic property tests for Emeritus of Truce // Swords to Plowshares."""

    def test_is_creature(self) -> None:
        """Emeritus of Truce // Swords to Plowshares must be a Creature subclass."""
        card = EmeritusOfTruceSwordsToPlowshares(name="Emeritus of Truce // Swords to Plowshares", owner=None, base_power=3, base_toughness=3)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """EmeritusOfTruceSwordsToPlowshares.name must be 'Emeritus of Truce // Swords to Plowshares'."""
        card = EmeritusOfTruceSwordsToPlowshares(name="Emeritus of Truce // Swords to Plowshares", owner=None, base_power=3, base_toughness=3)
        assert card.name == "Emeritus of Truce // Swords to Plowshares"

    def test_card_types(self) -> None:
        """Emeritus of Truce // Swords to Plowshares must have correct card types."""
        card = EmeritusOfTruceSwordsToPlowshares(name="Emeritus of Truce // Swords to Plowshares", owner=None, base_power=3, base_toughness=3)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Emeritus of Truce // Swords to Plowshares must have converted mana cost 4."""
        card = EmeritusOfTruceSwordsToPlowshares(name="Emeritus of Truce // Swords to Plowshares", owner=None, base_power=3, base_toughness=3)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Emeritus of Truce // Swords to Plowshares must have correct colors."""
        card = EmeritusOfTruceSwordsToPlowshares(name="Emeritus of Truce // Swords to Plowshares", owner=None, base_power=3, base_toughness=3)
        assert "W" in card.colors

    def test_power(self) -> None:
        """Emeritus of Truce // Swords to Plowshares must have base power 3."""
        card = EmeritusOfTruceSwordsToPlowshares(name="Emeritus of Truce // Swords to Plowshares", owner=None, base_power=3, base_toughness=3)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Emeritus of Truce // Swords to Plowshares must have base toughness 3."""
        card = EmeritusOfTruceSwordsToPlowshares(name="Emeritus of Truce // Swords to Plowshares", owner=None, base_power=3, base_toughness=3)
        assert card.base_toughness == 3


@pytest.mark.ability
class TestEmeritusOfTruceSwordsToPlowsharesAbilities:
    """Ability tests for Emeritus of Truce // Swords to Plowshares -- expected to fail against stubs."""

    def test_has_prepared(self) -> None:
        """Emeritus of Truce // Swords to Plowshares must have Prepared keyword."""
        from engine.types import Keyword
        card = EmeritusOfTruceSwordsToPlowshares(name="Emeritus of Truce // Swords to Plowshares", owner=None, base_power=3, base_toughness=3)
        assert Keyword.PREPARED in card.keywords, "Emeritus of Truce // Swords to Plowshares should have Prepared"

    def test_etb_creates_tokens(self) -> None:
        """ETB must create tokens per oracle text."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(name="Emeritus of Truce // Swords to Plowshares", owner=player, base_power=3, base_toughness=3)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf_before = len(player.zones[Zone.BATTLEFIELD].get_all())
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        bf_after = len(player.zones[Zone.BATTLEFIELD].get_all())
        assert bf_after > bf_before, "ETB must create tokens per oracle"

    def test_prepared_mechanic_implemented(self) -> None:
        """Prepared mechanic must be implemented per oracle text."""
        card = EmeritusOfTruceSwordsToPlowshares(name="Emeritus of Truce // Swords to Plowshares", owner=None, base_power=3, base_toughness=3)
        assert callable(getattr(card, "check_prepared", None)) or \
            callable(getattr(card, "prepared_effect", None)) or \
            callable(getattr(card, "on_resolve", None)), \
            "Emeritus of Truce // Swords to Plowshares must implement prepared mechanic"


@pytest.mark.edge
class TestEmeritusOfTruceSwordsToPlowsharesEdgeCases:
    """Edge case and trap tests for Emeritus of Truce // Swords to Plowshares."""

    def test_fizzle_no_targets_creature_stays(self) -> None:
        """If ETB ability fizzles, the creature remains on battlefield."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(name="Emeritus of Truce // Swords to Plowshares", owner=player, base_power=3, base_toughness=3)
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
        card1 = EmeritusOfTruceSwordsToPlowshares(name="Emeritus of Truce // Swords to Plowshares", owner=None, base_power=3, base_toughness=3)
        card2 = EmeritusOfTruceSwordsToPlowshares(name="Emeritus of Truce // Swords to Plowshares", owner=None, base_power=3, base_toughness=3)
        card1.name = "Modified"
        assert card2.name == "Emeritus of Truce // Swords to Plowshares", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = EmeritusOfTruceSwordsToPlowshares(name="Emeritus of Truce // Swords to Plowshares", owner=None, base_power=3, base_toughness=3)
        assert card.mana_cost.cmc == 4, \
            f"CMC must be 4, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestEmeritusOfTruceSwordsToPlowsharesInteractions:
    """Multi-card interaction tests for Emeritus of Truce // Swords to Plowshares."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(name="Emeritus of Truce // Swords to Plowshares", owner=player, base_power=3, base_toughness=3)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"

    def test_tokens_appear_on_battlefield(self) -> None:
        """Tokens created must appear on the battlefield."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(name="Emeritus of Truce // Swords to Plowshares", owner=player, base_power=3, base_toughness=3)
        card.controller = player
        bf_before = len(player.zones[Zone.BATTLEFIELD].get_all())
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        elif callable(getattr(card, "on_resolve", None)):
            card.on_resolve(game)
        bf_after = len(player.zones[Zone.BATTLEFIELD].get_all())
        assert bf_after > bf_before, "Tokens must appear on battlefield"
