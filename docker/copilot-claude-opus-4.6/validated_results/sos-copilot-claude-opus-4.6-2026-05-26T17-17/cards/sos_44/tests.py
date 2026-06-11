"""Tests for SOS 44 — Echocasting Symposium.

Echocasting Symposium is a {4}{U}{U} Sorcery — Lesson.
Target player creates a token copy of target creature you control.
Has Paradigm (exile after resolution; after first resolution, get free
copy at beginning of each first main phase).
"""

from __future__ import annotations

import pytest
from cards.sos.sos_44.card_impl import EchocastingSymposium
from engine.card import Creature, Sorcery
from engine.types import (
    CardType,
    ManaCost,
    ManaType,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class TestEchocastingSymposiumProperties:
    """Static card data should match the SOS 44 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(EchocastingSymposium(owner=None), Sorcery)

    def test_name(self) -> None:
        assert EchocastingSymposium(owner=None).name == "Echocasting Symposium"

    def test_mana_cost(self) -> None:
        assert EchocastingSymposium(owner=None).mana_cost == ManaCost.parse("{4}{U}{U}")

    def test_has_lesson_subtype(self) -> None:
        card = EchocastingSymposium(owner=None)
        assert "Lesson" in card.subtypes


class TestEchocastingSymposiumTargeting:
    """Requires two targets: a player and a creature you control."""

    def test_has_target_requirements(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EchocastingSymposium(owner=p1, controller=p1)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) >= 1


class TestEchocastingSymposiumResolution:
    """Creates a token copy of a creature you control."""

    def test_creates_token_copy(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = EchocastingSymposium(owner=p1, controller=p1)
        spell.chosen_targets = [p1, bear]
        spell.on_resolve(game)

        # Should have 2 bears on battlefield now (original + token)
        bf_names = [c.name for c in game.get_battlefield(p1) if c.name == "Grizzly Bears"]
        assert len(bf_names) >= 2

    def test_exiles_after_resolution(self) -> None:
        """Paradigm keyword means the spell exiles itself after resolving."""
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = EchocastingSymposium(owner=p1, controller=p1)
        spell.chosen_targets = [p1, bear]
        spell.on_resolve(game)

        exile_names = [c.name for c in game.get_exile(p1)]
        assert "Echocasting Symposium" in exile_names
