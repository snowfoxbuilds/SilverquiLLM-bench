"""Audited tests for FDN 167 — Tolarian Terror."""

from __future__ import annotations

from card_impl import TolarianTerror
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game


class TestTolarianTerrorBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = TolarianTerror(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = TolarianTerror(owner=None)
        assert card.name == "Tolarian Terror"

    def test_mana_cost(self) -> None:
        card = TolarianTerror(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}{U}")

    def test_power_toughness(self) -> None:
        card = TolarianTerror(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_ward(self) -> None:
        card = TolarianTerror(owner=None)
        assert Keyword.WARD in card.keywords

    def test_ward_cost_is_2(self) -> None:
        card = TolarianTerror(owner=None)
        assert card.ward_cost == ManaCost(generic=2)

    def test_serpent_subtype(self) -> None:
        card = TolarianTerror(owner=None)
        assert "Serpent" in card.subtypes


class TestTolarianTerrorCostReduction:
    """Costs {1} less for each instant/sorcery in graveyard."""

    def test_no_instants_in_gy_zero_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TolarianTerror(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_instant_in_gy_reduces_by_1(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TolarianTerror(owner=p1, controller=p1)
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"), owner=p1)
        p1.zones[Zone.GRAVEYARD].add(bolt)
        assert card.cost_reduction(game) == 1

    def test_sorcery_also_counts(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TolarianTerror(owner=p1, controller=p1)
        sorc = Sorcery(name="Divination", mana_cost=ManaCost.parse("{2}{U}"), owner=p1)
        p1.zones[Zone.GRAVEYARD].add(sorc)
        assert card.cost_reduction(game) == 1

    def test_multiple_spells_in_gy(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TolarianTerror(owner=p1, controller=p1)
        for i in range(4):
            spell = Instant(name=f"Spell{i}", mana_cost=ManaCost.parse("{U}"), owner=p1)
            p1.zones[Zone.GRAVEYARD].add(spell)
        assert card.cost_reduction(game) == 4

    def test_creature_in_gy_does_not_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TolarianTerror(owner=p1, controller=p1)
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1)
        p1.zones[Zone.GRAVEYARD].add(creature)
        assert card.cost_reduction(game) == 0
