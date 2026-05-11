"""Audited tests for Ravenous Amulet (FDN collector number 131)."""
from __future__ import annotations
import pytest
from card_impl import RavenousAmulet
from engine.card import Artifact, Creature
from engine.types import CardType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestRavenousAmuletBasic:
    def test_is_artifact(self) -> None:
        card = RavenousAmulet(name="Ravenous Amulet", owner=None)
        assert isinstance(card, Artifact)
        assert CardType.ARTIFACT in card.card_types
    def test_name(self) -> None:
        card = RavenousAmulet(name="Ravenous Amulet", owner=None)
        assert card.name == "Ravenous Amulet"
    def test_starts_with_zero_soul_counters(self) -> None:
        card = RavenousAmulet(name="Ravenous Amulet", owner=None)
        assert card.soul_counters == 0

@pytest.mark.ability
class TestRavenousAmuletAbilities:
    def test_has_two_activated_abilities(self) -> None:
        card = RavenousAmulet(name="Ravenous Amulet", owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) == 2

    def test_sac_creature_ability_draws_and_adds_counter(self) -> None:
        """First ability: sac a creature, draw a card, add a soul counter."""
        game = create_game()
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[0])
        amulet = RavenousAmulet(name="Ravenous Amulet", owner=game.players[0])
        amulet.controller = game.players[0]
        set_board_state(game, 0, battlefield=[creature, amulet])
        # Put a card in library so draw succeeds
        from engine.card import CardImpl
        lib_card = CardImpl(name="LibCard", owner=game.players[0])
        from engine.types import Zone
        game.players[0].zones[Zone.LIBRARY].add(lib_card)

        abilities = amulet.get_activated_abilities()
        cost_paid = abilities[0].cost(game, amulet)
        assert cost_paid
        abilities[0].effect(game)
        assert amulet.soul_counters == 1

    def test_drain_ability_costs_opponent_life(self) -> None:
        """Second ability: sac self, opponent loses life equal to soul counters."""
        game = create_game()
        amulet = RavenousAmulet(name="Ravenous Amulet", owner=game.players[0])
        amulet.controller = game.players[0]
        amulet.soul_counters = 3
        set_board_state(game, 0, battlefield=[amulet])
        initial_opp_life = game.players[1].life
        abilities = amulet.get_activated_abilities()
        cost_paid = abilities[1].cost(game, amulet)
        assert cost_paid
        abilities[1].effect(game)
        assert game.players[1].life == initial_opp_life - 3

    def test_ability_fails_when_tapped(self) -> None:
        """Cannot activate if already tapped."""
        amulet = RavenousAmulet(name="Ravenous Amulet", owner=None)
        amulet.is_tapped = True
        abilities = amulet.get_activated_abilities()
        game = create_game()
        cost_paid = abilities[0].cost(game, amulet)
        assert not cost_paid
