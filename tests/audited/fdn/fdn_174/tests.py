"""Audited tests for FDN 174 — Fake Your Own Death."""

from __future__ import annotations

from card_impl import FakeYourOwnDeath
from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.types import CardType, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestFakeYourOwnDeathBasics:
    """Basic card properties."""

    def test_is_instant(self) -> None:
        card = FakeYourOwnDeath(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = FakeYourOwnDeath(owner=None)
        assert card.name == "Fake Your Own Death"

    def test_mana_cost(self) -> None:
        card = FakeYourOwnDeath(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}")

    def test_has_target_requirement(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = FakeYourOwnDeath(owner=p1, controller=p1)
        targets = spell.get_targets(game)
        assert len(targets) >= 1


class TestFakeYourOwnDeathResolve:
    """Until end of turn, target creature gets +2/+0 and gains death trigger."""

    def test_fizzles_if_no_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = FakeYourOwnDeath(owner=p1, controller=p1)
        spell.chosen_targets = [None]
        # Should not raise
        spell.on_resolve(game)

    def test_has_target_requirement(self) -> None:
        """Spell targets a creature."""
        game = create_game()
        p1 = game.players[0]
        spell = FakeYourOwnDeath(owner=p1, controller=p1)
        targets = spell.get_targets(game)
        assert len(targets) >= 1
