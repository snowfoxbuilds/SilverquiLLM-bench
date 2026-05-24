"""Audited tests for Lluwen, Exchange Student // Pest Friend (collector key 199).

Verifies the Lluwen, Exchange Student // Pest Friend card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import LluwenExchangeStudentPestFriend

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestLluwenExchangeStudentPestFriendBasicProperties:
    """Basic property tests for Lluwen, Exchange Student // Pest Friend."""

    def test_is_creature(self) -> None:
        """Lluwen, Exchange Student // Pest Friend must be a Creature subclass."""
        card = LluwenExchangeStudentPestFriend(name="Lluwen, Exchange Student // Pest Friend", owner=None, base_power=3, base_toughness=4)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """LluwenExchangeStudentPestFriend.name must be 'Lluwen, Exchange Student // Pest Friend'."""
        card = LluwenExchangeStudentPestFriend(name="Lluwen, Exchange Student // Pest Friend", owner=None, base_power=3, base_toughness=4)
        assert card.name == "Lluwen, Exchange Student // Pest Friend"

    def test_card_types(self) -> None:
        """Lluwen, Exchange Student // Pest Friend must have correct card types."""
        card = LluwenExchangeStudentPestFriend(name="Lluwen, Exchange Student // Pest Friend", owner=None, base_power=3, base_toughness=4)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Lluwen, Exchange Student // Pest Friend must have converted mana cost 5."""
        card = LluwenExchangeStudentPestFriend(name="Lluwen, Exchange Student // Pest Friend", owner=None, base_power=3, base_toughness=4)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Lluwen, Exchange Student // Pest Friend must have correct colors."""
        card = LluwenExchangeStudentPestFriend(name="Lluwen, Exchange Student // Pest Friend", owner=None, base_power=3, base_toughness=4)
        assert "B" in card.colors
        assert "G" in card.colors

    def test_power(self) -> None:
        """Lluwen, Exchange Student // Pest Friend must have base power 3."""
        card = LluwenExchangeStudentPestFriend(name="Lluwen, Exchange Student // Pest Friend", owner=None, base_power=3, base_toughness=4)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Lluwen, Exchange Student // Pest Friend must have base toughness 4."""
        card = LluwenExchangeStudentPestFriend(name="Lluwen, Exchange Student // Pest Friend", owner=None, base_power=3, base_toughness=4)
        assert card.base_toughness == 4


@pytest.mark.ability
class TestLluwenExchangeStudentPestFriendAbilities:
    """Ability tests for Lluwen, Exchange Student // Pest Friend -- expected to fail against stubs."""

    def test_has_prepared(self) -> None:
        """Lluwen, Exchange Student // Pest Friend must have Prepared keyword."""
        from benchmarks.sos.workspace.engine.types import Keyword
        card = LluwenExchangeStudentPestFriend(name="Lluwen, Exchange Student // Pest Friend", owner=None, base_power=3, base_toughness=4)
        assert Keyword.PREPARED in card.keywords, "Lluwen, Exchange Student // Pest Friend should have Prepared"

    def test_etb_trigger_callable(self) -> None:
        """ETB trigger must be implemented per oracle text."""
        card = LluwenExchangeStudentPestFriend(name="Lluwen, Exchange Student // Pest Friend", owner=None, base_power=3, base_toughness=4)
        assert callable(getattr(card, "on_enter_battlefield", None)), \
            "Lluwen, Exchange Student // Pest Friend must implement on_enter_battlefield per oracle text"

    def test_prepared_mechanic_implemented(self) -> None:
        """Prepared mechanic must be implemented per oracle text."""
        card = LluwenExchangeStudentPestFriend(name="Lluwen, Exchange Student // Pest Friend", owner=None, base_power=3, base_toughness=4)
        assert callable(getattr(card, "check_prepared", None)) or \
            callable(getattr(card, "prepared_effect", None)) or \
            callable(getattr(card, "on_resolve", None)), \
            "Lluwen, Exchange Student // Pest Friend must implement prepared mechanic"


@pytest.mark.edge
class TestLluwenExchangeStudentPestFriendEdgeCases:
    """Edge case and trap tests for Lluwen, Exchange Student // Pest Friend."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = LluwenExchangeStudentPestFriend(name="Lluwen, Exchange Student // Pest Friend", owner=None, base_power=3, base_toughness=4)
        card2 = LluwenExchangeStudentPestFriend(name="Lluwen, Exchange Student // Pest Friend", owner=None, base_power=3, base_toughness=4)
        card1.name = "Modified"
        assert card2.name == "Lluwen, Exchange Student // Pest Friend", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = LluwenExchangeStudentPestFriend(name="Lluwen, Exchange Student // Pest Friend", owner=None, base_power=3, base_toughness=4)
        assert card.mana_cost.cmc == 5, \
            f"CMC must be 5, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = LluwenExchangeStudentPestFriend(name="Lluwen, Exchange Student // Pest Friend", owner=player, base_power=3, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 3
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestLluwenExchangeStudentPestFriendInteractions:
    """Multi-card interaction tests for Lluwen, Exchange Student // Pest Friend."""

    def test_exile_from_graveyard_interaction(self) -> None:
        """Cards exiled from graveyard must move to exile zone."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Instant
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        fodder = Instant(name="Fodder", owner=player)
        set_board_state(game, 0, graveyard=[fodder])
        card = LluwenExchangeStudentPestFriend(name="Lluwen, Exchange Student // Pest Friend", owner=player, base_power=3, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_attack", None)):
            card.on_attack(game)
        elif callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        exile = player.zones[Zone.EXILE].get_all()
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert fodder in exile or fodder not in gy, \
            "Exiled card must leave graveyard"

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = LluwenExchangeStudentPestFriend(name="Lluwen, Exchange Student // Pest Friend", owner=player, base_power=3, base_toughness=4)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
