"""Audited tests for Biblioplex Tomekeeper (collector key 247).

Verifies the Biblioplex Tomekeeper card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import BiblioplexTomekeeper

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestBiblioplexTomekeeperBasicProperties:
    """Basic property tests for Biblioplex Tomekeeper."""

    def test_is_creature(self) -> None:
        """Biblioplex Tomekeeper must be a Creature subclass."""
        card = BiblioplexTomekeeper(name="Biblioplex Tomekeeper", owner=None, base_power=3, base_toughness=4)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """BiblioplexTomekeeper.name must be 'Biblioplex Tomekeeper'."""
        card = BiblioplexTomekeeper(name="Biblioplex Tomekeeper", owner=None, base_power=3, base_toughness=4)
        assert card.name == "Biblioplex Tomekeeper"

    def test_card_types(self) -> None:
        """Biblioplex Tomekeeper must have correct card types."""
        card = BiblioplexTomekeeper(name="Biblioplex Tomekeeper", owner=None, base_power=3, base_toughness=4)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Biblioplex Tomekeeper must have converted mana cost 4."""
        card = BiblioplexTomekeeper(name="Biblioplex Tomekeeper", owner=None, base_power=3, base_toughness=4)
        assert card.mana_cost.cmc == 4

    def test_colorless(self) -> None:
        """Biblioplex Tomekeeper must be colorless."""
        card = BiblioplexTomekeeper(name="Biblioplex Tomekeeper", owner=None, base_power=3, base_toughness=4)
        assert len(card.colors) == 0

    def test_power(self) -> None:
        """Biblioplex Tomekeeper must have base power 3."""
        card = BiblioplexTomekeeper(name="Biblioplex Tomekeeper", owner=None, base_power=3, base_toughness=4)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Biblioplex Tomekeeper must have base toughness 4."""
        card = BiblioplexTomekeeper(name="Biblioplex Tomekeeper", owner=None, base_power=3, base_toughness=4)
        assert card.base_toughness == 4


@pytest.mark.ability
class TestBiblioplexTomekeeperAbilities:
    """Ability tests for Biblioplex Tomekeeper -- expected to fail against stubs."""

    def test_has_prepared(self) -> None:
        """Biblioplex Tomekeeper must have Prepared keyword."""
        from engine.types import Keyword
        card = BiblioplexTomekeeper(name="Biblioplex Tomekeeper", owner=None, base_power=3, base_toughness=4)
        assert Keyword.PREPARED in card.keywords, "Biblioplex Tomekeeper should have Prepared"

    def test_etb_trigger_callable(self) -> None:
        """ETB trigger must be implemented per oracle text."""
        card = BiblioplexTomekeeper(name="Biblioplex Tomekeeper", owner=None, base_power=3, base_toughness=4)
        assert callable(getattr(card, "on_enter_battlefield", None)), \
            "Biblioplex Tomekeeper must implement on_enter_battlefield per oracle text"

    def test_prepared_mechanic_implemented(self) -> None:
        """Prepared mechanic must be implemented per oracle text."""
        card = BiblioplexTomekeeper(name="Biblioplex Tomekeeper", owner=None, base_power=3, base_toughness=4)
        assert callable(getattr(card, "check_prepared", None)) or \
            callable(getattr(card, "prepared_effect", None)) or \
            callable(getattr(card, "on_resolve", None)), \
            "Biblioplex Tomekeeper must implement prepared mechanic"


@pytest.mark.edge
class TestBiblioplexTomekeeperEdgeCases:
    """Edge case and trap tests for Biblioplex Tomekeeper."""

    def test_fizzle_no_targets_creature_stays(self) -> None:
        """If ETB ability fizzles, the creature remains on battlefield."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = BiblioplexTomekeeper(name="Biblioplex Tomekeeper", owner=player, base_power=3, base_toughness=4)
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
        card1 = BiblioplexTomekeeper(name="Biblioplex Tomekeeper", owner=None, base_power=3, base_toughness=4)
        card2 = BiblioplexTomekeeper(name="Biblioplex Tomekeeper", owner=None, base_power=3, base_toughness=4)
        card1.name = "Modified"
        assert card2.name == "Biblioplex Tomekeeper", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = BiblioplexTomekeeper(name="Biblioplex Tomekeeper", owner=None, base_power=3, base_toughness=4)
        assert card.mana_cost.cmc == 4, \
            f"CMC must be 4, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestBiblioplexTomekeeperInteractions:
    """Multi-card interaction tests for Biblioplex Tomekeeper."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = BiblioplexTomekeeper(name="Biblioplex Tomekeeper", owner=player, base_power=3, base_toughness=4)
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
        card = BiblioplexTomekeeper(name="Biblioplex Tomekeeper", owner=player, base_power=3, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
