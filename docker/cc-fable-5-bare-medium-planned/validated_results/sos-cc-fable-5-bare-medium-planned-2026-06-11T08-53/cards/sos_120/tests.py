"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Land
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state


def _stack_library(game, player_index, cards) -> None:
    """Put *cards* into the player's library, last item = top."""
    player = game.players[player_index]
    library = game.get_library(player)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


def _cast_capstone(game) -> ImprovisationCapstone:
    capstone = ImprovisationCapstone()
    set_board_state(game, 0, hand=[capstone],
                    mana={ManaType.RED: 2, ManaType.COLORLESS: 5})
    cast_spell(game, 0, "Improvisation Capstone")
    return capstone


def _advance_to_main_of(game, player_index) -> None:
    """Advance to *player_index*'s next precombat main phase."""
    for _ in range(3):
        game.advance_phase()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        if game.active_player_index == player_index:
            return
    raise AssertionError("could not reach the player's main phase")


class TestCapstoneExileAndCast:
    def test_exiles_until_mv_four_and_casts_chosen(self) -> None:
        # Library top-down: 2-cmc instant, 3-cmc creature, land.
        land = Land(name="Wastes")
        big = Creature(name="Big", base_power=3, base_toughness=3,
                       mana_cost=ManaCost(generic=3))
        trick = Instant(name="Trick", mana_cost=ManaCost(generic=2))
        # Cast the instant for free, decline the creature.
        game = create_game(scripts=([True, False], []))
        p1 = game.players[0]
        _stack_library(game, 0, [land, big, trick])  # trick on top

        capstone = _cast_capstone(game)

        # 2 + 3 = 5 >= 4 → exactly two cards exiled; the land stays put.
        assert game.get_library(p1).contains(land)
        assert game.get_exile(p1).contains(big)  # declined → stays exiled
        assert game.get_graveyard(p1).contains(trick)  # cast and resolved
        assert game.get_exile(p1).contains(capstone)  # Paradigm exile

    def test_library_runs_out_before_mv_four(self) -> None:
        small = Instant(name="Small", mana_cost=ManaCost(generic=1))
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        _stack_library(game, 0, [small])

        _cast_capstone(game)
        assert game.get_exile(p1).contains(small)
        assert len(game.get_library(p1)) == 0

    def test_lands_are_not_castable(self) -> None:
        # A land alone (mv 0) then a 4-cmc card; the land is exiled but
        # never prompts a cast.
        land = Land(name="Wastes")
        big = Creature(name="Big", base_power=4, base_toughness=4,
                       mana_cost=ManaCost(generic=4))
        game = create_game(scripts=([False], []))  # one prompt: Big only
        p1 = game.players[0]
        _stack_library(game, 0, [big, land])  # land on top

        _cast_capstone(game)
        assert game.get_exile(p1).contains(land)
        assert game.get_exile(p1).contains(big)
        assert game.players[0].remaining_choices == 0  # exactly one prompt


class TestCapstoneParadigm:
    def test_copy_castable_each_of_your_first_mains(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        _cast_capstone(game)  # empty library: no exiles, no cast prompts

        # P2's main: no trigger for P1's Paradigm.
        _advance_to_main_of(game, 1)
        assert game.stack.is_empty()

        # P1's next first main: copy created in exile, cast it.
        p1._script.extend(["pass", True, "pass"])  # pass; cast copy; pass
        game.players[1]._script.extend(["pass", "pass"])
        _advance_to_main_of(game, 0)
        priority_loop(game)
        capstones_in_exile = [
            c for c in game.get_exile(p1).get_all()
            if c.name == "Improvisation Capstone"
        ]
        # Original + resolved copy (the copy re-exiles itself via Paradigm).
        assert len(capstones_in_exile) == 2

        # Recurring: it happens again on P1's following turn (declined
        # this time — the copy stays in exile uncast).
        p1._script.extend(["pass", False])
        game.players[1]._script.append("pass")
        _advance_to_main_of(game, 1)
        _advance_to_main_of(game, 0)
        priority_loop(game)
        capstones_in_exile = [
            c for c in game.get_exile(p1).get_all()
            if c.name == "Improvisation Capstone"
        ]
        assert len(capstones_in_exile) == 3

    def test_second_resolution_does_not_duplicate_trigger(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        _cast_capstone(game)
        # Cast a second Capstone from hand — same name already resolved.
        capstone2 = ImprovisationCapstone()
        set_board_state(game, 0, hand=[capstone2],
                        mana={ManaType.RED: 2, ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Improvisation Capstone")

        # Only ONE recurring Paradigm trigger exists.
        triggers = [
            t for t in game.trigger_manager.get_triggers()
            if getattr(t.source, "name", "") == "Improvisation Capstone"
        ]
        assert len(triggers) == 1
