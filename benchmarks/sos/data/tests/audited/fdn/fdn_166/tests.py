"""Audited tests for FDN 166 — Time Stop."""

from __future__ import annotations

from card_impl import TimeStop
from benchmarks.sos.workspace.engine.card import CardImpl, Instant
from benchmarks.sos.workspace.engine.types import ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestTimeStopBasics:
    """Basic card properties."""

    def test_is_instant(self) -> None:
        card = TimeStop(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = TimeStop(owner=None)
        assert card.name == "Time Stop"

    def test_mana_cost(self) -> None:
        card = TimeStop(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}{U}{U}")

    def test_cmc_is_6(self) -> None:
        card = TimeStop(owner=None)
        assert card.mana_cost.cmc == 6


class TestTimeStopResolve:
    """End the turn — exile all spells on stack."""

    def test_clears_the_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        from benchmarks.sos.workspace.engine.stack import StackObject
        dummy_card = CardImpl(name="Dummy", owner=p1)
        stack_obj = StackObject(source=dummy_card, controller=p1)
        game.stack.push(stack_obj)
        spell = TimeStop(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert game.stack.is_empty()

    def test_exiled_spells_go_to_exile(self) -> None:
        game = create_game()
        p1 = game.players[0]
        from benchmarks.sos.workspace.engine.stack import StackObject
        dummy_card = CardImpl(name="Dummy", owner=p1)
        stack_obj = StackObject(source=dummy_card, controller=p1)
        game.stack.push(stack_obj)
        p1.zones[Zone.STACK].add(dummy_card)
        spell = TimeStop(owner=p1, controller=p1)
        spell.on_resolve(game)
        exile = list(p1.zones[Zone.EXILE].get_all())
        assert any(getattr(c, "name", "") == "Dummy" for c in exile)

    def test_sets_turn_ended_flag(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = TimeStop(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert getattr(game, "_turn_ended", False)

    def test_empty_stack_still_ends_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = TimeStop(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert getattr(game, "_turn_ended", False)
