"""Audited tests for Thornweald Archer (FDN collector number 559) — reach + deathtouch."""

from __future__ import annotations

import pytest

from card_impl import ThornwealdArcher

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestThornwealdArcherProperties:
    def test_is_creature(self) -> None:
        card = ThornwealdArcher(name="Thornweald Archer", owner=None)
        assert isinstance(card, Creature)

    def test_power(self) -> None:
        card = ThornwealdArcher(name="Thornweald Archer", owner=None)
        assert card.power == 2

    def test_toughness(self) -> None:
        card = ThornwealdArcher(name="Thornweald Archer", owner=None)
        assert card.toughness == 1

    def test_has_elf_subtype(self) -> None:
        card = ThornwealdArcher(name="Thornweald Archer", owner=None)
        assert "Elf" in card.subtypes

    def test_has_archer_subtype(self) -> None:
        card = ThornwealdArcher(name="Thornweald Archer", owner=None)
        assert "Archer" in card.subtypes


@pytest.mark.ability
class TestThornwealdArcherKeywords:
    def test_has_reach(self) -> None:
        card = ThornwealdArcher(name="Thornweald Archer", owner=None)
        assert Keyword.REACH in card.keywords

    def test_has_deathtouch(self) -> None:
        card = ThornwealdArcher(name="Thornweald Archer", owner=None)
        assert Keyword.DEATHTOUCH in card.keywords

    def test_exact_keywords(self) -> None:
        card = ThornwealdArcher(name="Thornweald Archer", owner=None)
        expected = Keyword.REACH | Keyword.DEATHTOUCH
        assert card.keywords == expected


@pytest.mark.behavior
class TestThornwealdArcherBehavior:
    """Reach + deathtouch behavior tests."""

    def test_reach_can_block_flyer(self) -> None:
        """Thornweald Archer (reach) can block a creature with flying."""
        from engine.combat import _can_block
        from engine.card import Creature

        archer = ThornwealdArcher(name="Thornweald Archer", owner=None)
        flyer = Creature(name="Flyer", owner=None)
        flyer.keywords = Keyword.FLYING
        assert _can_block(archer, flyer)

    def test_deathtouch_means_1_damage_is_lethal(self) -> None:
        """Deathtouch makes 1 damage lethal for assigning damage purposes."""
        from engine.combat import _get_lethal_damage
        from engine.card import Creature

        archer = ThornwealdArcher(name="Thornweald Archer", owner=None)
        target = Creature(name="Big Target", owner=None, base_toughness=10)
        assert _get_lethal_damage(target, archer) == 1
