"""Tests for SOS 120 — Improvisation Capstone (cast-from-exile + Paradigm)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Land, Sorcery
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state, cast_spell


def _resolve_stack(game) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class _ProbeSorcery(Sorcery):
    def __init__(self, name: str, cost: str, gain: int = 0, **kwargs: Any) -> None:
        kwargs.setdefault("name", name)
        kwargs.setdefault("mana_cost", ManaCost.parse(cost))
        super().__init__(**kwargs)
        self._gain = gain

    def on_resolve(self, game) -> None:
        if self.controller is not None and self._gain:
            self.controller.life += self._gain


def _fill_library(game, pidx: int, cards: list) -> None:
    """Add *cards* to the player's library bottom→top (last = top)."""
    p = game.players[pidx]
    lib = p.zones[Zone.LIBRARY]
    for c in cards:
        c.owner = p
        c.controller = p
        lib.add(c)


def _advance_to_next_own_main(game, pidx: int, after_turn: int) -> None:
    for _ in range(60):
        game.advance_phase()
        _resolve_stack(game)
        if (
            game.active_player_index == pidx
            and game.phase == Phase.PRECOMBAT_MAIN
            and game.turn_number > after_turn
        ):
            return
    raise AssertionError("did not reach the player's next precombat main")


class TestProperties:
    def test_static_data(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert isinstance(card, Sorcery)
        assert "Lesson" in card.subtypes


class TestExileUntilMV4:
    def test_exiles_until_total_mv_four(self) -> None:
        game = create_game(scripts=([False, False], []))
        p0 = game.players[0]
        filler = _ProbeSorcery("Filler", "{1}")
        cardX = _ProbeSorcery("CardX", "{2}")
        cardY = _ProbeSorcery("CardY", "{3}")
        _fill_library(game, 0, [filler, cardX, cardY])  # top = cardY
        cap = ImprovisationCapstone(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[cap],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        cast_spell(game, 0, "Improvisation Capstone")
        ex = game.get_exile(p0)
        assert ex.contains(cardY) and ex.contains(cardX)  # MV 3 + 2 = 5 >= 4
        assert game.get_library(p0).contains(filler)  # stop before filler
        assert ex.contains(cap)  # Paradigm exiled the Capstone itself

    def test_library_runs_out(self) -> None:
        game = create_game(scripts=([False], []))
        p0 = game.players[0]
        only = _ProbeSorcery("Only", "{2}")  # MV 2 < 4, library then empty
        _fill_library(game, 0, [only])
        cap = ImprovisationCapstone(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[cap],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_exile(p0).contains(only)
        assert len(game.get_library(p0)) == 0


class TestFreeCast:
    def test_cast_one_for_free_land_stays(self) -> None:
        game = create_game(scripts=([True], []))  # yes, cast the spell
        p0 = game.players[0]
        spellZ = _ProbeSorcery("SpellZ", "{4}", gain=7)
        landL = Land(name="LandL")
        _fill_library(game, 0, [spellZ, landL])  # top = landL
        cap = ImprovisationCapstone(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[cap],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        before = p0.life
        cast_spell(game, 0, "Improvisation Capstone")
        # landL (MV 0) then spellZ (MV 4) exiled.  spellZ cast for free.
        assert p0.life == before + 7
        assert game.get_graveyard(p0).contains(spellZ)
        assert game.get_exile(p0).contains(landL)  # land stays exiled
        assert not game.get_exile(p0).contains(spellZ)


class TestParadigm:
    def test_copy_each_first_main_phase(self) -> None:
        game = create_game(scripts=([False], []))  # don't cast on first resolve
        p0 = game.players[0]
        c1 = _ProbeSorcery("C1", "{4}")
        c2 = _ProbeSorcery("C2", "{4}")
        _fill_library(game, 0, [c1, c2])  # top = c2
        cap = ImprovisationCapstone(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[cap],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        cast_spell(game, 0, "Improvisation Capstone")
        cast_turn = game.turn_number
        ex = game.get_exile(p0)
        assert ex.contains(c2) and ex.contains(cap)
        assert not ex.contains(c1)  # not yet exiled

        # Next main phase: cast a copy (yes), don't cast the freshly-exiled c1.
        p0._script.extend([True, False])
        _advance_to_next_own_main(game, 0, cast_turn)
        assert game.get_exile(p0).contains(c1)  # the copy exiled c1

    def test_decline_copy_does_nothing(self) -> None:
        game = create_game(scripts=([False], []))
        p0 = game.players[0]
        c1 = _ProbeSorcery("C1", "{4}")
        c2 = _ProbeSorcery("C2", "{4}")
        _fill_library(game, 0, [c1, c2])
        cap = ImprovisationCapstone(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[cap],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        cast_spell(game, 0, "Improvisation Capstone")
        cast_turn = game.turn_number
        p0._script.append(False)  # decline the Paradigm copy
        _advance_to_next_own_main(game, 0, cast_turn)
        assert not game.get_exile(p0).contains(c1)  # nothing happened
