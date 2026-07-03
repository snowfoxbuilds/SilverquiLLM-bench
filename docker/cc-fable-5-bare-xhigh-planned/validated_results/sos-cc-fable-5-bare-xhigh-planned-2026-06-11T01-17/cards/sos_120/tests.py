"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.basic_lands import Mountain
from engine.card import Creature
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, ManaType, Phase, Step, Zone
from test_utils import advance_to_phase, create_game, set_board_state, cast_spell


def _bear(name: str, cost: str = "{2}") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2,
                    mana_cost=ManaCost.parse(cost))


def _capstone_mana():
    return {ManaType.COLORLESS: 5, ManaType.RED: 2}


def _advance_to_next_precombat_main(game) -> None:
    advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)


class TestImprovisationCapstoneProperties:
    def test_static_data(self) -> None:
        card = ImprovisationCapstone()
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert CardType.SORCERY in card.card_types
        assert "Lesson" in card.subtypes


class TestImprovisationCapstoneResolve:
    def test_exiles_until_mv_4_and_casts_chosen(self) -> None:
        """Top-down: bolt(3) + bear(2) reach MV 4; the land below stays."""
        game = create_game()
        p1 = game.players[0]
        land = Mountain()
        bear = _bear("Library Bear", "{2}")
        bolt = _bear("Library Bolt", "{3}")
        lib = game.get_library(p1)
        for c in (land, bear, bolt):  # bolt ends on top
            c.owner = p1
            lib.add(c)
        cap = ImprovisationCapstone()
        set_board_state(game, 0, hand=[cap], mana=_capstone_mana())
        # Prompts in exile order: bolt (decline), bear (cast).
        p1._script.extend([False, True])
        cast_spell(game, 0, "Improvisation Capstone")
        exile = game.get_exile(p1)
        assert exile.contains(bolt)  # declined — stays exiled
        assert game.get_battlefield(p1).contains(bear)  # cast for free
        assert lib.contains(land)  # never exiled
        assert exile.contains(cap)  # Paradigm: spell exiled, not graveyard
        assert not game.get_graveyard(p1).contains(cap)

    def test_library_runs_out_before_mv_4(self) -> None:
        """Two lands (MV 0) — whole library exiled, no prompts, no crash."""
        game = create_game()
        p1 = game.players[0]
        lands = [Mountain(), Mountain()]
        lib = game.get_library(p1)
        for c in lands:
            c.owner = p1
            lib.add(c)
        cap = ImprovisationCapstone()
        set_board_state(game, 0, hand=[cap], mana=_capstone_mana())
        cast_spell(game, 0, "Improvisation Capstone")
        exile = game.get_exile(p1)
        assert all(exile.contains(land) for land in lands)
        assert len(lib) == 0
        assert exile.contains(cap)

    def test_empty_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        cap = ImprovisationCapstone()
        set_board_state(game, 0, hand=[cap], mana=_capstone_mana())
        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_exile(p1).contains(cap)


class TestImprovisationCapstoneParadigm:
    def test_copy_castable_each_of_your_first_main_phases(self) -> None:
        game = create_game()
        p1, p2 = game.players
        cap = ImprovisationCapstone()
        set_board_state(game, 0, hand=[cap], mana=_capstone_mana())
        cast_spell(game, 0, "Improvisation Capstone")  # empty library — just exiles itself
        assert game.get_exile(p1).contains(cap)

        # Stock the library for the copy's resolution next turn.
        bears = [_bear("Bear A", "{2}"), _bear("Bear B", "{2}")]
        lib = game.get_library(p1)
        for b in bears:
            b.owner = p1
            lib.add(b)

        # p2's precombat main fires E2 but the condition (your main) is false.
        _advance_to_next_precombat_main(game)
        assert game.active_player is p2
        assert game.stack.is_empty()

        # p1's next first main phase: trigger → yes → copy resolves,
        # exiling Bear A+B (MV 4) and casting both for free.
        _advance_to_next_precombat_main(game)
        assert game.active_player is p1
        p1._script.extend(["pass", True, "pass", True, True, "pass", "pass"])
        p2._script.extend(["pass", "pass", "pass", "pass"])
        priority_loop(game)
        assert game.get_battlefield(p1).contains(bears[0])
        assert game.get_battlefield(p1).contains(bears[1])
        # The original stays in exile for future turns.
        assert game.get_exile(p1).contains(cap)

    def test_copy_may_be_declined(self) -> None:
        game = create_game()
        p1, p2 = game.players
        cap = ImprovisationCapstone()
        set_board_state(game, 0, hand=[cap], mana=_capstone_mana())
        cast_spell(game, 0, "Improvisation Capstone")
        _advance_to_next_precombat_main(game)  # p2's main
        _advance_to_next_precombat_main(game)  # p1's main — trigger fires
        p1._script.extend(["pass", False])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert game.get_exile(p1).contains(cap)
        assert game.stack.is_empty()
