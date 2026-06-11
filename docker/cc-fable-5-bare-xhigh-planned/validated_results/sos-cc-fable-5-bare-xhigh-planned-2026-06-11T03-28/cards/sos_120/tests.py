"""Tests for SOS 120 — Improvisation Capstone (Paradigm)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.basic_lands import Mountain
from engine.card import Creature, Instant, Sorcery
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state, cast_spell


def _fill_library(player, cards) -> None:
    """Put *cards* into the library, first item on top.

    The top of a ZoneContainer is its LAST index, so successive
    bottom-inserts leave the first item on top.
    """
    library = player.zones[Zone.LIBRARY]
    for card in cards:
        card.owner = card.controller = player
        library.add(card, position="bottom")


def _capstone_in_hand(game, p1):
    spell = ImprovisationCapstone(owner=p1)
    set_board_state(game, 0, hand=[spell],
                    mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
    return spell


class TestCapstoneProperties:
    def test_static_data(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery)
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert "Lesson" in card.subtypes


class TestCapstoneExileAndCast:
    def test_exiles_until_total_mv_4(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = _capstone_in_hand(game, p1)
        big = Creature(name="Big", base_power=3, base_toughness=3,
                       mana_cost=ManaCost.parse("{2}{G}"))  # MV 3
        small = Creature(name="Small", base_power=1, base_toughness=1,
                         mana_cost=ManaCost.parse("{1}"))   # MV 1 → total 4
        rest = Creature(name="Rest", base_power=1, base_toughness=1,
                        mana_cost=ManaCost.parse("{5}"))
        _fill_library(p1, [big, small, rest])
        p1._script.extend([False, False])  # decline both free casts
        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_exile(p1).contains(big)
        assert game.get_exile(p1).contains(small)
        assert game.get_library(p1).contains(rest)

    def test_may_cast_exiled_spells_for_free(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = _capstone_in_hand(game, p1)
        giant = Creature(name="Giant", base_power=5, base_toughness=5,
                         mana_cost=ManaCost.parse("{4}{R}"))  # MV 5 alone
        _fill_library(p1, [giant])
        p1._script.extend([True])  # cast the giant for free
        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_battlefield(p1).contains(giant)

    def test_lands_stay_exiled_without_prompt(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = _capstone_in_hand(game, p1)
        mountain = Mountain()
        giant = Creature(name="Giant", base_power=5, base_toughness=5,
                         mana_cost=ManaCost.parse("{4}{R}"))
        _fill_library(p1, [mountain, giant])
        p1._script.extend([False])  # only one prompt: the giant
        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_exile(p1).contains(mountain)
        assert game.get_exile(p1).contains(giant)
        assert p1.remaining_choices == 0

    def test_library_runs_out_before_mv_4(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = _capstone_in_hand(game, p1)
        only = Creature(name="Only", base_power=1, base_toughness=1,
                        mana_cost=ManaCost.parse("{1}"))
        _fill_library(p1, [only])
        p1._script.extend([False])
        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_exile(p1).contains(only)
        assert len(game.get_library(p1)) == 0


class TestCapstoneParadigm:
    def test_exiles_itself_on_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = _capstone_in_hand(game, p1)
        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_exile(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)

    def test_copy_castable_each_of_your_first_main_phases(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = _capstone_in_hand(game, p1)
        boost1 = Creature(name="Boost1", base_power=4, base_toughness=4,
                          mana_cost=ManaCost.parse("{4}"))
        boost2 = Creature(name="Boost2", base_power=4, base_toughness=4,
                          mana_cost=ManaCost.parse("{4}"))
        _fill_library(p1, [boost1, boost2])
        p1._script.extend([False])  # decline boost1 on the original cast
        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_exile(p1).contains(spell)

        # Advance to p1's next precombat main (full turn cycle).
        game.advance_phase()
        while not (
            (game.phase, game.step) == (Phase.PRECOMBAT_MAIN, None)
            and game.active_player is p1
        ):
            game.advance_phase()
        # Paradigm trigger is on the stack: accept the copy, cast boost2.
        p1._script.extend(["pass", True, True, "pass", "pass", "pass"])
        p2._script.extend(["pass", "pass", "pass", "pass"])
        priority_loop(game)
        assert game.get_battlefield(p1).contains(boost2)
        # The original stays exiled; the resolved copy ceases to exist.
        assert game.get_exile(p1).contains(spell)
        capstones_in_exile = [
            c for c in game.get_exile(p1).get_all()
            if getattr(c, "name", "") == "Improvisation Capstone"
        ]
        assert len(capstones_in_exile) == 1
        assert not any(
            getattr(c, "name", "") == "Improvisation Capstone"
            for c in game.get_graveyard(p1).get_all()
        )

    def test_no_trigger_on_opponents_main(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = _capstone_in_hand(game, p1)
        cast_spell(game, 0, "Improvisation Capstone")
        # Advance to p2's precombat main: no Paradigm trigger for p1.
        game.advance_phase()
        while not (
            (game.phase, game.step) == (Phase.PRECOMBAT_MAIN, None)
            and game.active_player is p2
        ):
            game.advance_phase()
        assert game.stack.is_empty()
