"""Tests for sos_120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestImprovisationCapstoneProperties:
    def test_name(self) -> None:
        assert ImprovisationCapstone(owner=None).name == "Improvisation Capstone"

    def test_mana_cost(self) -> None:
        assert ImprovisationCapstone(owner=None).mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_is_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert CardType.SORCERY in card.card_types

    def test_subtype_lesson(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert "Lesson" in card.subtypes


class TestImprovisationCapstoneExileEffect:
    """Core effect: exile cards from top of library until total MV ≥ 4."""

    def _make_card_mv(self, n: int, name: str = "Card", owner=None) -> Instant:
        c = Instant(name=name, owner=owner)
        from engine.types import ManaCost as MC
        c.mana_cost = MC(generic=n)
        return c

    def test_exiles_cards_until_mv_threshold_met(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # Put cards with MV 2, 2 in library (total = 4 → should stop after 2).
        c1 = self._make_card_mv(2, "C1", p1)
        c2 = self._make_card_mv(2, "C2", p1)
        c3 = self._make_card_mv(2, "C3", p1)
        p1.zones[Zone.LIBRARY].add(c3)
        p1.zones[Zone.LIBRARY].add(c2)
        p1.zones[Zone.LIBRARY].add(c1)  # top
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        cap.on_resolve(game)
        exile = game.get_exile(p1)
        # c1 (MV=2) + c2 (MV=2) → total MV=4, stop.
        # c3 should still be in library.
        assert p1.zones[Zone.LIBRARY].contains(c3)

    def test_exiles_at_least_one_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        c1 = self._make_card_mv(10, "BigCard", p1)
        p1.zones[Zone.LIBRARY].add(c1)
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        cap.on_resolve(game)
        assert game.get_exile(p1).contains(c1)

    def test_empty_library_does_not_raise(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # Library is empty.
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        cap.on_resolve(game)  # must not raise


class TestImprovisationCapstoneParadigm:
    """Paradigm: this spell is exiled on resolution, not sent to graveyard."""

    def test_on_cast_sets_exile_on_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        cap.on_cast(game)
        assert getattr(cap, "_exile_on_resolution", False) is True

    def test_paradigm_flag_set_after_first_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        # Add a card to library so resolution doesn't fail.
        c1 = Instant(name="C1", owner=p1)
        from engine.types import ManaCost as MC
        c1.mana_cost = MC(generic=4)
        p1.zones[Zone.LIBRARY].add(c1)
        cap.on_resolve(game)
        assert getattr(game, "_paradigm_capstone_active", False) is True
