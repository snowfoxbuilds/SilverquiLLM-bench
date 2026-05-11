"""Audited tests for Grim Tutor (SPG collector number 76, dir 76b)."""
from __future__ import annotations
import pytest
from card_impl import GrimTutor
from engine.card import Sorcery, CardImpl
from engine.types import ManaCost, Zone


@pytest.mark.basic
class TestGrimTutorBasic:
    def test_is_sorcery(self) -> None:
        card = GrimTutor()
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = GrimTutor()
        assert card.name == "Grim Tutor"

    def test_mana_cost(self) -> None:
        card = GrimTutor()
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")


@pytest.mark.ability
class TestGrimTutorResolve:
    def test_on_resolve_loses_3_life(self) -> None:
        from tests.test_utils import create_game
        game = create_game()
        p = game.players[0]
        card = GrimTutor(owner=p)
        card.controller = p
        life_before = p.life
        card.on_resolve(game)
        assert p.life == life_before - 3

    def test_on_resolve_puts_chosen_card_in_hand(self) -> None:
        from tests.test_utils import create_game
        game = create_game()
        p = game.players[0]
        target = CardImpl(name="Target Card")
        target.owner = p
        p.zones[Zone.LIBRARY].add(target)
        card = GrimTutor(owner=p)
        card.controller = p
        card.chosen_targets = [target]
        card.on_resolve(game)
        assert p.zones[Zone.HAND].contains(target)
        assert not p.zones[Zone.LIBRARY].contains(target)

    def test_on_resolve_shuffles_library(self) -> None:
        """After resolving, library should still exist (shuffle doesn't crash)."""
        from tests.test_utils import create_game
        game = create_game()
        p = game.players[0]
        for i in range(5):
            c = CardImpl(name=f"Card{i}")
            c.owner = p
            p.zones[Zone.LIBRARY].add(c)
        card = GrimTutor(owner=p)
        card.controller = p
        card.on_resolve(game)
        # Library should still have 4 cards (5 - 1 searched)
        assert len(p.zones[Zone.LIBRARY]) == 4
