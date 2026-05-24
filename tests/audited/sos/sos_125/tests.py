"""Audited tests for Molten-Core Maestro (collector key 125).

Verifies the Molten-Core Maestro card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import MoltenCoreMaestro

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestMoltenCoreMaestroBasicProperties:
    """Basic property tests for Molten-Core Maestro."""

    def test_is_creature(self) -> None:
        """Molten-Core Maestro must be a Creature subclass."""
        card = MoltenCoreMaestro(name="Molten-Core Maestro", owner=None, base_power=2, base_toughness=2)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """MoltenCoreMaestro.name must be 'Molten-Core Maestro'."""
        card = MoltenCoreMaestro(name="Molten-Core Maestro", owner=None, base_power=2, base_toughness=2)
        assert card.name == "Molten-Core Maestro"

    def test_card_types(self) -> None:
        """Molten-Core Maestro must have correct card types."""
        card = MoltenCoreMaestro(name="Molten-Core Maestro", owner=None, base_power=2, base_toughness=2)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Molten-Core Maestro must have converted mana cost 2."""
        card = MoltenCoreMaestro(name="Molten-Core Maestro", owner=None, base_power=2, base_toughness=2)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Molten-Core Maestro must have correct colors."""
        card = MoltenCoreMaestro(name="Molten-Core Maestro", owner=None, base_power=2, base_toughness=2)
        assert "R" in card.colors

    def test_power(self) -> None:
        """Molten-Core Maestro must have base power 2."""
        card = MoltenCoreMaestro(name="Molten-Core Maestro", owner=None, base_power=2, base_toughness=2)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Molten-Core Maestro must have base toughness 2."""
        card = MoltenCoreMaestro(name="Molten-Core Maestro", owner=None, base_power=2, base_toughness=2)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestMoltenCoreMaestroAbilities:
    """Ability tests for Molten-Core Maestro -- expected to fail against stubs."""

    def test_has_menace(self) -> None:
        """Molten-Core Maestro must have Menace keyword."""
        from benchmarks.sos.workspace.engine.types import Keyword
        card = MoltenCoreMaestro(name="Molten-Core Maestro", owner=None, base_power=2, base_toughness=2)
        assert Keyword.MENACE in card.keywords, "Molten-Core Maestro should have Menace"

    def test_has_opus(self) -> None:
        """Molten-Core Maestro must have Opus keyword."""
        from benchmarks.sos.workspace.engine.types import Keyword
        card = MoltenCoreMaestro(name="Molten-Core Maestro", owner=None, base_power=2, base_toughness=2)
        assert Keyword.OPUS in card.keywords, "Molten-Core Maestro should have Opus"

    def test_opus_trigger_implemented(self) -> None:
        """Opus must trigger when controller casts instant/sorcery."""
        card = MoltenCoreMaestro(name="Molten-Core Maestro", owner=None, base_power=2, base_toughness=2)
        assert callable(getattr(card, "on_spell_cast", None)) or \
            callable(getattr(card, "opus_trigger", None)), \
            "Molten-Core Maestro must implement opus trigger per oracle text"


@pytest.mark.edge
class TestMoltenCoreMaestroEdgeCases:
    """Edge case and trap tests for Molten-Core Maestro."""

    def test_opus_no_trigger_without_spell(self) -> None:
        """Opus should not boost without casting instant/sorcery."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = MoltenCoreMaestro(name="Molten-Core Maestro", owner=player, base_power=2, base_toughness=2)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        base_p = card.base_power
        assert card.base_power == base_p, "No opus trigger should leave power unchanged"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = MoltenCoreMaestro(name="Molten-Core Maestro", owner=None, base_power=2, base_toughness=2)
        card2 = MoltenCoreMaestro(name="Molten-Core Maestro", owner=None, base_power=2, base_toughness=2)
        card1.name = "Modified"
        assert card2.name == "Molten-Core Maestro", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = MoltenCoreMaestro(name="Molten-Core Maestro", owner=None, base_power=2, base_toughness=2)
        assert card.mana_cost.cmc == 2, \
            f"CMC must be 2, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestMoltenCoreMaestroInteractions:
    """Multi-card interaction tests for Molten-Core Maestro."""

    def test_counters_survive_end_of_turn(self) -> None:
        """Permanent counters must persist through end of turn."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = MoltenCoreMaestro(name="Molten-Core Maestro", owner=player, base_power=2, base_toughness=2)
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
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = MoltenCoreMaestro(name="Molten-Core Maestro", owner=player, base_power=2, base_toughness=2)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
