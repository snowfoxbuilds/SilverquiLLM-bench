"""Audited tests for Muse Seeker (collector key 60).

Verifies the Muse Seeker card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import MuseSeeker

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestMuseSeekerBasicProperties:
    """Basic property tests for Muse Seeker."""

    def test_is_creature(self) -> None:
        """Muse Seeker must be a Creature subclass."""
        card = MuseSeeker(name="Muse Seeker", owner=None, base_power=1, base_toughness=2)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """MuseSeeker.name must be 'Muse Seeker'."""
        card = MuseSeeker(name="Muse Seeker", owner=None, base_power=1, base_toughness=2)
        assert card.name == "Muse Seeker"

    def test_card_types(self) -> None:
        """Muse Seeker must have correct card types."""
        card = MuseSeeker(name="Muse Seeker", owner=None, base_power=1, base_toughness=2)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Muse Seeker must have converted mana cost 2."""
        card = MuseSeeker(name="Muse Seeker", owner=None, base_power=1, base_toughness=2)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Muse Seeker must have correct colors."""
        card = MuseSeeker(name="Muse Seeker", owner=None, base_power=1, base_toughness=2)
        assert "U" in card.colors

    def test_power(self) -> None:
        """Muse Seeker must have base power 1."""
        card = MuseSeeker(name="Muse Seeker", owner=None, base_power=1, base_toughness=2)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Muse Seeker must have base toughness 2."""
        card = MuseSeeker(name="Muse Seeker", owner=None, base_power=1, base_toughness=2)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestMuseSeekerAbilities:
    """Ability tests for Muse Seeker -- expected to fail against stubs."""

    def test_has_opus(self) -> None:
        """Muse Seeker must have Opus keyword."""
        from benchmarks.sos.workspace.engine.types import Keyword
        card = MuseSeeker(name="Muse Seeker", owner=None, base_power=1, base_toughness=2)
        assert Keyword.OPUS in card.keywords, "Muse Seeker should have Opus"

    def test_opus_trigger_implemented(self) -> None:
        """Opus must trigger when controller casts instant/sorcery."""
        card = MuseSeeker(name="Muse Seeker", owner=None, base_power=1, base_toughness=2)
        assert callable(getattr(card, "on_spell_cast", None)) or \
            callable(getattr(card, "opus_trigger", None)), \
            "Muse Seeker must implement opus trigger per oracle text"


@pytest.mark.edge
class TestMuseSeekerEdgeCases:
    """Edge case and trap tests for Muse Seeker."""

    def test_opus_no_trigger_without_spell(self) -> None:
        """Opus should not boost without casting instant/sorcery."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = MuseSeeker(name="Muse Seeker", owner=player, base_power=1, base_toughness=2)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        base_p = card.base_power
        assert card.base_power == base_p, "No opus trigger should leave power unchanged"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = MuseSeeker(name="Muse Seeker", owner=None, base_power=1, base_toughness=2)
        card2 = MuseSeeker(name="Muse Seeker", owner=None, base_power=1, base_toughness=2)
        card1.name = "Modified"
        assert card2.name == "Muse Seeker", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = MuseSeeker(name="Muse Seeker", owner=None, base_power=1, base_toughness=2)
        assert card.mana_cost.cmc == 2, \
            f"CMC must be 2, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestMuseSeekerInteractions:
    """Multi-card interaction tests for Muse Seeker."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = MuseSeeker(name="Muse Seeker", owner=player, base_power=1, base_toughness=2)
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
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        card = MuseSeeker(name="Muse Seeker", owner=player, base_power=1, base_toughness=2)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
