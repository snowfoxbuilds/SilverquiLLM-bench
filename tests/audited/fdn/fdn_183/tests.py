"""Audited tests for FDN 183 — Rise of the Dark Realms."""

from __future__ import annotations

from card_impl import RiseOfTheDarkRealms
from engine.card import CardImpl, Creature, Sorcery
from engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestRiseOfTheDarkRealmsBasics:
    """Basic card properties."""

    def test_is_sorcery(self) -> None:
        card = RiseOfTheDarkRealms(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = RiseOfTheDarkRealms(owner=None)
        assert card.name == "Rise of the Dark Realms"

    def test_mana_cost(self) -> None:
        card = RiseOfTheDarkRealms(owner=None)
        assert card.mana_cost == ManaCost.parse("{7}{B}{B}")


class TestRiseOfTheDarkRealmsResolve:
    """Put all creature cards from all graveyards onto the battlefield under your control."""

    def test_returns_own_creatures_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(creature)
        spell = RiseOfTheDarkRealms(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert game.get_battlefield(p1).contains(creature)

    def test_returns_opponent_creatures_under_your_control(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        creature = Creature(name="OppBear", base_power=3, base_toughness=3, owner=p2, controller=p2)
        p2.zones[Zone.GRAVEYARD].add(creature)
        spell = RiseOfTheDarkRealms(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert creature.controller is p1

    def test_non_creature_cards_stay_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        noncreature = CardImpl(name="Spell", mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        noncreature.card_types = {CardType.SORCERY}
        p1.zones[Zone.GRAVEYARD].add(noncreature)
        spell = RiseOfTheDarkRealms(owner=p1, controller=p1)
        spell.on_resolve(game)
        # Non-creature should not be on battlefield
        assert not game.get_battlefield(p1).contains(noncreature)
