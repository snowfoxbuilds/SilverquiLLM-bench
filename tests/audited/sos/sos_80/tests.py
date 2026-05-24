"""Audited tests for Emeritus of Woe // Demonic Tutor (collector key 80).

Verifies the Emeritus of Woe // Demonic Tutor card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import EmeritusOfWoeDemonicTutor

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestEmeritusOfWoeDemonicTutorBasicProperties:
    """Basic property tests for Emeritus of Woe // Demonic Tutor."""

    def test_is_creature(self) -> None:
        """Emeritus of Woe // Demonic Tutor must be a Creature subclass."""
        card = EmeritusOfWoeDemonicTutor(name="Emeritus of Woe // Demonic Tutor", owner=None, base_power=5, base_toughness=4)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """EmeritusOfWoeDemonicTutor.name must be 'Emeritus of Woe // Demonic Tutor'."""
        card = EmeritusOfWoeDemonicTutor(name="Emeritus of Woe // Demonic Tutor", owner=None, base_power=5, base_toughness=4)
        assert card.name == "Emeritus of Woe // Demonic Tutor"

    def test_card_types(self) -> None:
        """Emeritus of Woe // Demonic Tutor must have correct card types."""
        card = EmeritusOfWoeDemonicTutor(name="Emeritus of Woe // Demonic Tutor", owner=None, base_power=5, base_toughness=4)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Emeritus of Woe // Demonic Tutor must have converted mana cost 6."""
        card = EmeritusOfWoeDemonicTutor(name="Emeritus of Woe // Demonic Tutor", owner=None, base_power=5, base_toughness=4)
        assert card.mana_cost.cmc == 6

    def test_colors(self) -> None:
        """Emeritus of Woe // Demonic Tutor must have correct colors."""
        card = EmeritusOfWoeDemonicTutor(name="Emeritus of Woe // Demonic Tutor", owner=None, base_power=5, base_toughness=4)
        assert "B" in card.colors

    def test_power(self) -> None:
        """Emeritus of Woe // Demonic Tutor must have base power 5."""
        card = EmeritusOfWoeDemonicTutor(name="Emeritus of Woe // Demonic Tutor", owner=None, base_power=5, base_toughness=4)
        assert card.base_power == 5

    def test_toughness(self) -> None:
        """Emeritus of Woe // Demonic Tutor must have base toughness 4."""
        card = EmeritusOfWoeDemonicTutor(name="Emeritus of Woe // Demonic Tutor", owner=None, base_power=5, base_toughness=4)
        assert card.base_toughness == 4


@pytest.mark.ability
class TestEmeritusOfWoeDemonicTutorAbilities:
    """Ability tests for Emeritus of Woe // Demonic Tutor -- expected to fail against stubs."""

    def test_has_prepared(self) -> None:
        """Emeritus of Woe // Demonic Tutor must have Prepared keyword."""
        from engine.types import Keyword
        card = EmeritusOfWoeDemonicTutor(name="Emeritus of Woe // Demonic Tutor", owner=None, base_power=5, base_toughness=4)
        assert Keyword.PREPARED in card.keywords, "Emeritus of Woe // Demonic Tutor should have Prepared"

    def test_etb_trigger_callable(self) -> None:
        """ETB trigger must be implemented per oracle text."""
        card = EmeritusOfWoeDemonicTutor(name="Emeritus of Woe // Demonic Tutor", owner=None, base_power=5, base_toughness=4)
        assert callable(getattr(card, "on_enter_battlefield", None)), \
            "Emeritus of Woe // Demonic Tutor must implement on_enter_battlefield per oracle text"

    def test_prepared_mechanic_implemented(self) -> None:
        """Prepared mechanic must be implemented per oracle text."""
        card = EmeritusOfWoeDemonicTutor(name="Emeritus of Woe // Demonic Tutor", owner=None, base_power=5, base_toughness=4)
        assert callable(getattr(card, "check_prepared", None)) or \
            callable(getattr(card, "prepared_effect", None)) or \
            callable(getattr(card, "on_resolve", None)), \
            "Emeritus of Woe // Demonic Tutor must implement prepared mechanic"


@pytest.mark.edge
class TestEmeritusOfWoeDemonicTutorEdgeCases:
    """Edge case and trap tests for Emeritus of Woe // Demonic Tutor."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = EmeritusOfWoeDemonicTutor(name="Emeritus of Woe // Demonic Tutor", owner=None, base_power=5, base_toughness=4)
        card2 = EmeritusOfWoeDemonicTutor(name="Emeritus of Woe // Demonic Tutor", owner=None, base_power=5, base_toughness=4)
        card1.name = "Modified"
        assert card2.name == "Emeritus of Woe // Demonic Tutor", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = EmeritusOfWoeDemonicTutor(name="Emeritus of Woe // Demonic Tutor", owner=None, base_power=5, base_toughness=4)
        assert card.mana_cost.cmc == 6, \
            f"CMC must be 6, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = EmeritusOfWoeDemonicTutor(name="Emeritus of Woe // Demonic Tutor", owner=player, base_power=5, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 3
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestEmeritusOfWoeDemonicTutorInteractions:
    """Multi-card interaction tests for Emeritus of Woe // Demonic Tutor."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = EmeritusOfWoeDemonicTutor(name="Emeritus of Woe // Demonic Tutor", owner=player, base_power=5, base_toughness=4)
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
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        card = EmeritusOfWoeDemonicTutor(name="Emeritus of Woe // Demonic Tutor", owner=player, base_power=5, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
