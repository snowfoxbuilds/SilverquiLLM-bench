"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Land
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, ManaType, Phase, Step
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state


def _stack_library(game, player_index, cards) -> None:
    """Replace the player's library; the LAST card in *cards* is on top."""
    library = game.get_library(game.players[player_index])
    for obj in library.get_all():
        library.remove(obj)
    for card in cards:
        card.owner = game.players[player_index]
        card.controller = game.players[player_index]
        library.add(card)


_CAPSTONE_MANA = {ManaType.RED: 2, ManaType.COLORLESS: 5}


class TestResolution:
    def test_exiles_until_total_mv_4_and_casts_for_free(self) -> None:
        game = create_game()
        p1 = game.players[0]
        zap = Instant(name="Zap", mana_cost=ManaCost.parse("{1}{R}"))  # MV 2
        bear = Creature(name="Bear", mana_cost=ManaCost.parse("{2}{G}"), base_power=2, base_toughness=2)  # MV 3
        deep = Instant(name="Deep", mana_cost=ManaCost.parse("{1}"))  # below the others
        _stack_library(game, 0, [deep, bear, zap])  # zap on top
        capstone = ImprovisationCapstone()
        set_board_state(game, 0, hand=[capstone], mana=dict(_CAPSTONE_MANA))
        # zap (2) then bear (3) -> total 5 >= 4; cast both for free.
        p1._script.extend([bear, zap])
        cast_spell(game, 0, "Improvisation Capstone")

        assert game.get_battlefield(p1).contains(bear)
        assert game.get_graveyard(p1).contains(zap)
        assert game.get_exile(p1).contains(capstone)  # Paradigm self-exile
        # Deep stays in the library.
        assert game.get_library(p1).contains(deep)

    def test_library_runs_out_short_of_4(self) -> None:
        game = create_game()
        p1 = game.players[0]
        small = Instant(name="Small", mana_cost=ManaCost.parse("{1}"))
        _stack_library(game, 0, [small])
        capstone = ImprovisationCapstone()
        set_board_state(game, 0, hand=[capstone], mana=dict(_CAPSTONE_MANA))
        p1._script.extend([None])  # decline casting Small
        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_exile(p1).contains(small)
        assert len(game.get_library(p1)) == 0

    def test_lands_stay_exiled_and_are_not_offered(self) -> None:
        game = create_game()
        p1 = game.players[0]
        land = Land(name="Some Land")
        big = Instant(name="Big", mana_cost=ManaCost.parse("{4}"))
        _stack_library(game, 0, [big, land])  # land on top: 0 MV, then big: 4
        capstone = ImprovisationCapstone()
        set_board_state(game, 0, hand=[capstone], mana=dict(_CAPSTONE_MANA))
        p1._script.extend([None])  # only Big is offered; decline
        cast_spell(game, 0, "Improvisation Capstone")
        exile = game.get_exile(p1)
        assert exile.contains(land)
        assert exile.contains(big)
        assert p1.remaining_choices == 0


class TestParadigm:
    def _advance_to_next_precombat_main(self, game) -> None:
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

    def test_copy_cast_each_of_your_first_main_phases(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _stack_library(game, 0, [])
        capstone = ImprovisationCapstone()
        set_board_state(game, 0, hand=[capstone], mana=dict(_CAPSTONE_MANA))
        cast_spell(game, 0, "Improvisation Capstone")  # empty library: no prompts
        assert game.get_exile(p1).contains(capstone)

        # Refill the library so the copy has something to exile.
        prize = Instant(name="Prize", mana_cost=ManaCost.parse("{4}"))
        _stack_library(game, 0, [prize])

        self._advance_to_next_precombat_main(game)  # p2's turn: no prompt for p1
        assert game.active_player is p2
        priority_loop(game)  # trigger condition failed -> nothing on stack

        self._advance_to_next_precombat_main(game)  # p1's turn
        assert game.active_player is p1
        p1._script.extend(["pass", True, "pass", None])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)

        assert game.get_exile(p1).contains(prize)  # the copy resolved
        assert game.get_exile(p1).contains(capstone)  # original stays exiled
        assert p1.remaining_choices == 0

    def test_decline_copy(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _stack_library(game, 0, [])
        capstone = ImprovisationCapstone()
        set_board_state(game, 0, hand=[capstone], mana=dict(_CAPSTONE_MANA))
        cast_spell(game, 0, "Improvisation Capstone")

        self._advance_to_next_precombat_main(game)  # p2's turn
        self._advance_to_next_precombat_main(game)  # p1's turn
        p1._script.extend(["pass", False])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert game.stack.is_empty()
        assert p1.remaining_choices == 0

    def test_second_resolution_registers_only_one_trigger(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _stack_library(game, 0, [])
        c1, c2 = ImprovisationCapstone(), ImprovisationCapstone()
        set_board_state(game, 0, hand=[c1, c2], mana=dict(_CAPSTONE_MANA))
        cast_spell(game, 0, "Improvisation Capstone")
        set_board_state(game, 0, mana=dict(_CAPSTONE_MANA))
        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_exile(p1).contains(c1)
        assert game.get_exile(p1).contains(c2)

        self._advance_to_next_precombat_main(game)  # p2's turn
        self._advance_to_next_precombat_main(game)  # p1's turn
        # Exactly ONE yes/no prompt: a second one would exhaust the script.
        p1._script.extend(["pass", False])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert p1.remaining_choices == 0
