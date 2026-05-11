"""Audited tests for Expedition Map (FDN collector number 724)."""
from __future__ import annotations
import pytest
from card_impl import ExpeditionMap
from engine.card import Artifact, CardImpl, Land
from engine.types import CardType, Zone
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestExpeditionMapBasic:
    def test_is_artifact(self) -> None:
        card = ExpeditionMap(name="Expedition Map", owner=None)
        assert isinstance(card, Artifact)
        assert CardType.ARTIFACT in card.card_types
    def test_name(self) -> None:
        card = ExpeditionMap(name="Expedition Map", owner=None)
        assert card.name == "Expedition Map"
    def test_has_activated_ability(self) -> None:
        card = ExpeditionMap(name="Expedition Map", owner=None)
        assert len(card.get_activated_abilities()) >= 1

@pytest.mark.ability
class TestExpeditionMapAbility:
    def test_searches_land_into_hand(self) -> None:
        """Activated ability: sacrifice, search library for a land, put into hand."""
        game = create_game()
        emap = ExpeditionMap(name="Expedition Map", owner=game.players[0])
        emap.controller = game.players[0]
        land = Land(name="Forest", owner=game.players[0])
        set_board_state(game, 0, battlefield=[emap])
        game.players[0].zones[Zone.LIBRARY].add(land)
        abilities = emap.get_activated_abilities()
        cost_paid = abilities[0].cost(game, emap)
        assert cost_paid
        abilities[0].effect(game)
        hand_cards = list(game.players[0].zones[Zone.HAND].get_all())
        assert any(c is land for c in hand_cards), "Land should be in hand"

    def test_no_land_in_library_still_shuffles(self) -> None:
        """If no land is found, library is still shuffled (no error)."""
        game = create_game()
        emap = ExpeditionMap(name="Expedition Map", owner=game.players[0])
        emap.controller = game.players[0]
        non_land = CardImpl(name="Spell", owner=game.players[0])
        set_board_state(game, 0, battlefield=[emap])
        game.players[0].zones[Zone.LIBRARY].add(non_land)
        abilities = emap.get_activated_abilities()
        abilities[0].cost(game, emap)
        # Should not raise
        abilities[0].effect(game)
