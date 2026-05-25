"""Audited tests for FDN 190 — Brass's Bounty."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from benchmarks.sos.workspace.engine.card import CardImpl, Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game

# The conftest name derivation produces "BrassSBounty" but the impl uses
# "BrasssBounty".  Import the real class directly.
_impl_path = Path(__file__).resolve().parent.parent.parent.parent.parent / "cards" / "fdn" / "fdn_190" / "card_impl.py"
_spec = importlib.util.spec_from_file_location("_fdn190_direct", _impl_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
BrasssBounty = _mod.BrasssBounty


class TestBrasssBountyBasics:
    """Basic card properties."""

    def test_is_sorcery(self) -> None:
        card = BrasssBounty(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = BrasssBounty(owner=None)
        assert card.name == "Brass's Bounty"

    def test_mana_cost(self) -> None:
        card = BrasssBounty(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}{R}")


class TestBrasssBountyResolve:
    """For each land you control, create a Treasure token."""

    def test_creates_treasures_equal_to_lands(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # Add 3 lands
        for i in range(3):
            land = CardImpl(name=f"Land{i}", mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
            land.card_types = {CardType.LAND}
            game.get_battlefield(p1).add(land)
        bf_before = len(game.get_battlefield(p1).get_all())
        spell = BrasssBounty(owner=p1, controller=p1)
        spell.on_resolve(game)
        bf_after = len(game.get_battlefield(p1).get_all())
        # Should have 3 more permanents (treasure tokens)
        assert bf_after == bf_before + 3

    def test_no_lands_no_treasures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bf_before = len(game.get_battlefield(p1).get_all())
        spell = BrasssBounty(owner=p1, controller=p1)
        spell.on_resolve(game)
        bf_after = len(game.get_battlefield(p1).get_all())
        assert bf_after == bf_before

    def test_treasures_are_artifacts(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = CardImpl(name="Land", mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        land.card_types = {CardType.LAND}
        game.get_battlefield(p1).add(land)
        spell = BrasssBounty(owner=p1, controller=p1)
        spell.on_resolve(game)
        bf = game.get_battlefield(p1).get_all()
        treasures = [p for p in bf if getattr(p, "name", "") == "Treasure"]
        assert len(treasures) == 1
        assert CardType.ARTIFACT in treasures[0].card_types
