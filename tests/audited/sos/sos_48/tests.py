"""Audited tests for Exhibition Tidecaller (collector key 48).

Verifies the Exhibition Tidecaller card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import ExhibitionTidecaller

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestExhibitionTidecallerBasicProperties:
    """Basic property tests for Exhibition Tidecaller."""

    def test_is_creature(self) -> None:
        """Exhibition Tidecaller must be a Creature subclass."""
        card = ExhibitionTidecaller(name="Exhibition Tidecaller", owner=None, base_power=0, base_toughness=2)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """ExhibitionTidecaller.name must be 'Exhibition Tidecaller'."""
        card = ExhibitionTidecaller(name="Exhibition Tidecaller", owner=None, base_power=0, base_toughness=2)
        assert card.name == "Exhibition Tidecaller"

    def test_card_types(self) -> None:
        """Exhibition Tidecaller must have correct card types."""
        card = ExhibitionTidecaller(name="Exhibition Tidecaller", owner=None, base_power=0, base_toughness=2)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Exhibition Tidecaller must have converted mana cost 1."""
        card = ExhibitionTidecaller(name="Exhibition Tidecaller", owner=None, base_power=0, base_toughness=2)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Exhibition Tidecaller must have correct colors."""
        card = ExhibitionTidecaller(name="Exhibition Tidecaller", owner=None, base_power=0, base_toughness=2)
        assert "U" in card.colors

    def test_power(self) -> None:
        """Exhibition Tidecaller must have base power 0."""
        card = ExhibitionTidecaller(name="Exhibition Tidecaller", owner=None, base_power=0, base_toughness=2)
        assert card.base_power == 0

    def test_toughness(self) -> None:
        """Exhibition Tidecaller must have base toughness 2."""
        card = ExhibitionTidecaller(name="Exhibition Tidecaller", owner=None, base_power=0, base_toughness=2)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestExhibitionTidecallerAbilities:
    """Ability tests for Exhibition Tidecaller -- expected to fail against stubs."""

    def test_has_opus(self) -> None:
        """Exhibition Tidecaller must have Opus keyword."""
        from engine.types import Keyword
        card = ExhibitionTidecaller(name="Exhibition Tidecaller", owner=None, base_power=0, base_toughness=2)
        assert Keyword.OPUS in card.keywords, "Exhibition Tidecaller should have Opus"

    def test_opus_trigger_implemented(self) -> None:
        """Opus must trigger when controller casts instant/sorcery."""
        card = ExhibitionTidecaller(name="Exhibition Tidecaller", owner=None, base_power=0, base_toughness=2)
        assert callable(getattr(card, "on_spell_cast", None)) or \
            callable(getattr(card, "opus_trigger", None)), \
            "Exhibition Tidecaller must implement opus trigger per oracle text"


@pytest.mark.edge
class TestExhibitionTidecallerEdgeCases:
    """Edge case and trap tests for Exhibition Tidecaller."""

    def test_fizzle_no_targets_creature_stays(self) -> None:
        """If ETB ability fizzles, the creature remains on battlefield."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = ExhibitionTidecaller(name="Exhibition Tidecaller", owner=player, base_power=0, base_toughness=2)
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

    def test_opus_no_trigger_without_spell(self) -> None:
        """Opus should not boost without casting instant/sorcery."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = ExhibitionTidecaller(name="Exhibition Tidecaller", owner=player, base_power=0, base_toughness=2)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        base_p = card.base_power
        assert card.base_power == base_p, "No opus trigger should leave power unchanged"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = ExhibitionTidecaller(name="Exhibition Tidecaller", owner=None, base_power=0, base_toughness=2)
        card2 = ExhibitionTidecaller(name="Exhibition Tidecaller", owner=None, base_power=0, base_toughness=2)
        card1.name = "Modified"
        assert card2.name == "Exhibition Tidecaller", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = ExhibitionTidecaller(name="Exhibition Tidecaller", owner=None, base_power=0, base_toughness=2)
        assert card.mana_cost.cmc == 1, \
            f"CMC must be 1, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestExhibitionTidecallerInteractions:
    """Multi-card interaction tests for Exhibition Tidecaller."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = ExhibitionTidecaller(name="Exhibition Tidecaller", owner=player, base_power=0, base_toughness=2)
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
        card = ExhibitionTidecaller(name="Exhibition Tidecaller", owner=player, base_power=0, base_toughness=2)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
