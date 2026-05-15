"""Audited tests for FDN 158 — Micromancer."""

from __future__ import annotations

from card_impl import Micromancer
from engine.card import CardImpl, Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, Zone
from tests.test_utils import create_game


class TestMicromancerBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = Micromancer(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = Micromancer(owner=None)
        assert card.name == "Micromancer"

    def test_mana_cost(self) -> None:
        card = Micromancer(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{U}")

    def test_power_toughness(self) -> None:
        card = Micromancer(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_subtypes(self) -> None:
        card = Micromancer(owner=None)
        assert "Human" in card.subtypes
        assert "Wizard" in card.subtypes


class TestMicromancerETB:
    """Search library for instant/sorcery with mana value 1."""

    def test_finds_mv1_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        micro = Micromancer(owner=p1, controller=p1)
        micro.controller = p1
        target_spell = Instant(name="Shock", mana_cost=ManaCost.parse("{R}"), owner=p1)
        p1.zones[Zone.LIBRARY].add(target_spell)
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.append(True)  # yes, search
            p1._script.append(target_spell)  # choose this card
        micro.on_resolve(game)
        hand_names = [getattr(c, "name", "") for c in p1.zones[Zone.HAND].get_all()]
        assert "Shock" in hand_names

    def test_skips_mv2_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        micro = Micromancer(owner=p1, controller=p1)
        micro.controller = p1
        big_spell = Instant(name="Big Spell", mana_cost=ManaCost.parse("{1}{U}"), owner=p1)
        p1.zones[Zone.LIBRARY].add(big_spell)
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.append(True)  # yes, search
        micro.on_resolve(game)
        hand_names = [getattr(c, "name", "") for c in p1.zones[Zone.HAND].get_all()]
        assert "Big Spell" not in hand_names

    def test_can_decline_to_search(self) -> None:
        game = create_game()
        p1 = game.players[0]
        micro = Micromancer(owner=p1, controller=p1)
        micro.controller = p1
        target_spell = Instant(name="Shock", mana_cost=ManaCost.parse("{R}"), owner=p1)
        p1.zones[Zone.LIBRARY].add(target_spell)
        from engine.player import DeterministicPlayer
        if isinstance(p1, DeterministicPlayer):
            p1._script.append(False)  # decline to search
        micro.on_resolve(game)
        hand_names = [getattr(c, "name", "") for c in p1.zones[Zone.HAND].get_all()]
        assert "Shock" not in hand_names
