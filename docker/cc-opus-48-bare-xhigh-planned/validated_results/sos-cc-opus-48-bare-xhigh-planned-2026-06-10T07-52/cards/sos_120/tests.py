"""Tests for SOS 120 — Improvisation Capstone (Paradigm)."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Land, Sorcery
from engine.casting import cast_spell as engine_cast
from engine.state_based_actions import resolve_state_based_actions
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


def _resolve_all(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _advance_to_active0_precombat(game):
    for _ in range(60):
        game.advance_phase()
        if game.phase == Phase.PRECOMBAT_MAIN and game.active_player_index == 0:
            return
    raise AssertionError("did not reach player 0's precombat main")


def _bear(name, mv):
    return Creature(name=name, base_power=2, base_toughness=2,
                    mana_cost=ManaCost.parse(f"{{{mv}}}"))


def _fill_lib(game, idx, cards_bottom_to_top):
    lib = game.players[idx].zones[Zone.LIBRARY]
    for c in cards_bottom_to_top:
        c.owner = game.players[idx]
        c.controller = game.players[idx]
        lib.add(c)


class TestProperties:
    def test_static(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"
        assert isinstance(card, Sorcery)
        assert "Lesson" in card.subtypes
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")


class TestExileAndCast:
    def test_exile_until_mv4_and_cast(self) -> None:
        game = create_game()
        p0 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        a = _bear("A", 2)
        b = _bear("B", 3)
        land = Land(name="Wastes")
        # bottom → top: land, B, A  (A peeled first)
        _fill_lib(game, 0, [land, b, a])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        p0._script.extend([True, True])  # cast A, cast B
        cap = game.get_hand(p0).get_all()[0]
        engine_cast(game, p0, cap)
        _resolve_all(game)

        bf = {c.name for c in game.get_battlefield(p0).get_all()}
        assert {"A", "B"} <= bf  # both cast for free
        assert game.get_library(p0).contains(land)  # land not exiled
        # Paradigm: the Capstone exiles itself.
        assert game.get_exile(p0).contains(cap)

    def test_library_runs_out(self) -> None:
        game = create_game()
        p0 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        a = _bear("Solo", 2)  # MV 2 < 4, then library empty
        _fill_lib(game, 0, [a])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        p0._script.extend([True])  # cast Solo
        cap = game.get_hand(p0).get_all()[0]
        engine_cast(game, p0, cap)
        _resolve_all(game)
        assert any(c.name == "Solo" for c in game.get_battlefield(p0).get_all())
        assert len(game.get_library(p0)) == 0

    def test_decline_keeps_exiled(self) -> None:
        game = create_game()
        p0 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        a = _bear("A", 4)  # MV 4 reaches threshold in one card
        _fill_lib(game, 0, [a])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        p0._script.extend([False])  # decline casting A
        cap = game.get_hand(p0).get_all()[0]
        engine_cast(game, p0, cap)
        _resolve_all(game)
        assert game.get_exile(p0).contains(a)  # stays exiled
        assert not any(c.name == "A" for c in game.get_battlefield(p0).get_all())


class TestParadigm:
    def test_recurring_copy_from_exile(self) -> None:
        game = create_game()
        p0 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        a = _bear("A", 2)
        b = _bear("B", 3)
        later = _bear("Later", 4)  # left in library for the paradigm copy
        # bottom → top: later, B, A
        _fill_lib(game, 0, [later, b, a])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        p0._script.extend([True, True])  # cast A, B
        cap = game.get_hand(p0).get_all()[0]
        engine_cast(game, p0, cap)
        _resolve_all(game)
        assert game.get_exile(p0).contains(cap)

        # Next of your first main phases: may cast a copy from exile.
        _advance_to_active0_precombat(game)
        p0._script.extend([True, True])  # yes-cast copy, then cast "Later"
        _resolve_all(game)
        assert any(c.name == "Later" for c in game.get_battlefield(p0).get_all())
        # Original Capstone still exiled (only a copy was cast).
        assert game.get_exile(p0).contains(cap)
