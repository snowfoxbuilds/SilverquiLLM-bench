"""Audited tests for Eager Glyphmage (collector number 11).

Verifies the Eager Glyphmage card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""
from __future__ import annotations
import pytest
from card_impl import EagerGlyphmage
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent

@pytest.mark.basic
class TestEagerGlyphmageBasicProperties:
    """Eager Glyphmage basic property tests."""

    def test_is_creature(self) -> None:
        """Eager Glyphmage must be a Creature subclass."""
        card = EagerGlyphmage(name='Eager Glyphmage', owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """EagerGlyphmage.name must be 'Eager Glyphmage'."""
        card = EagerGlyphmage(name='Eager Glyphmage', owner=None)
        assert card.name == 'Eager Glyphmage'

    def test_card_type(self) -> None:
        """Eager Glyphmage must have CardType.CREATURE."""
        card = EagerGlyphmage(name='Eager Glyphmage', owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Eager Glyphmage must have converted mana cost 4."""
        card = EagerGlyphmage(name='Eager Glyphmage', owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Eager Glyphmage must have colors ['W']."""
        card = EagerGlyphmage(name='Eager Glyphmage', owner=None)
        for c in ['W']:
            assert c in card.colors, f'Expected color {c} in {card.colors}'

    def test_power(self) -> None:
        """Eager Glyphmage must have power 3."""
        card = EagerGlyphmage(name='Eager Glyphmage', owner=None)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Eager Glyphmage must have toughness 3."""
        card = EagerGlyphmage(name='Eager Glyphmage', owner=None)
        assert card.base_toughness == 3

@pytest.mark.ability
class TestEagerGlyphmageAbilities:
    """Eager Glyphmage ability tests — expected to fail against stubs."""

    def test_etb_creates_token(self) -> None:
        """Eager Glyphmage ETB should create token(s).

        Oracle: When this creature enters, create a 1/1 white and black Inkling creature token with flying.
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = EagerGlyphmage(name='Eager Glyphmage', owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(card=card))
        bf = game.get_battlefield(player).get_all()
        tokens = [c for c in bf if getattr(c, 'is_token', False)]
        assert len(tokens) >= 1, f"Expected at least 1 token on battlefield after ETB. Found: {[getattr(c, 'name', repr(c)) for c in bf]}"
