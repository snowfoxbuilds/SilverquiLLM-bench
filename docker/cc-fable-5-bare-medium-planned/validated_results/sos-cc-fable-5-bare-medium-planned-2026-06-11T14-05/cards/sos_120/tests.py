"""Tests for Improvisation Capstone (sos_120)."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant
from engine.casting import resolve_top
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from test_utils import advance_to_phase, create_game, set_board_state, cast_spell


def _put_library(game, player_index, cards):
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for card in cards:  # last card added = top of library
        card.owner = player
        card.controller = player
        library.add(card)


def _hand_capstone(game):
    set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                    mana={ManaType.RED: 2, ManaType.COLORLESS: 5})


class TestImprovisationCapstone:
    def test_exiles_until_mv_4_and_casts_free(self):
        game = create_game()
        p0 = game.players[0]
        deep = Instant(name="Deep Card", mana_cost=ManaCost.parse("{1}"))
        trick = Instant(name="Trick", mana_cost=ManaCost.parse("{3}"))
        bear = Creature(name="Top Bear", mana_cost=ManaCost.parse("{2}"),
                        base_power=2, base_toughness=2)
        _put_library(game, 0, [deep, trick, bear])  # bear on top
        _hand_capstone(game)
        p0._script.extend([bear, trick])  # cast both exiled spells
        cast_spell(game, 0, "Improvisation Capstone")
        # bear (2) + trick (3) = 5 >= 4 — deep card never exiled.
        assert p0.zones[Zone.LIBRARY].contains(deep)
        assert game.get_battlefield(p0).contains(bear)
        assert p0.zones[Zone.GRAVEYARD].contains(trick)
        # Paradigm: the Capstone itself is exiled, not in the graveyard.
        capstone = p0.zones[Zone.EXILE].get_all()[-1]
        assert capstone.name == "Improvisation Capstone"

    def test_library_runs_out_before_mv_4(self):
        game = create_game()
        p0 = game.players[0]
        small = [Instant(name=f"One {i}", mana_cost=ManaCost.parse("{1}")) for i in range(2)]
        _put_library(game, 0, small)
        _hand_capstone(game)
        p0._script.append(None)  # decline casting
        cast_spell(game, 0, "Improvisation Capstone")
        assert len(p0.zones[Zone.LIBRARY]) == 0
        for c in small:
            assert p0.zones[Zone.EXILE].contains(c)

    def test_lands_stay_exiled_uncastable(self):
        from engine.card import Land
        game = create_game()
        p0 = game.players[0]
        land = Land(name="Some Land")
        big = Instant(name="Big", mana_cost=ManaCost.parse("{4}"))
        _put_library(game, 0, [big, land])  # land on top
        _hand_capstone(game)
        p0._script.append(None)  # decline casting Big
        cast_spell(game, 0, "Improvisation Capstone")
        assert p0.zones[Zone.EXILE].contains(land)
        assert p0.zones[Zone.EXILE].contains(big)

    def test_paradigm_recasts_copy_each_of_your_first_mains(self):
        game = create_game()
        p0 = game.players[0]
        first = Instant(name="First Pull", mana_cost=ManaCost.parse("{4}"))
        second = Instant(name="Second Pull", mana_cost=ManaCost.parse("{4}"))
        _put_library(game, 0, [second, first])  # 'first' on top
        _hand_capstone(game)
        p0._script.append(first)  # cast it during original resolution
        cast_spell(game, 0, "Improvisation Capstone")
        assert p0.zones[Zone.GRAVEYARD].contains(first)

        # Advance to p1's precombat main (no trigger for p0 there) ...
        advance_to_phase(game, Phase.COMBAT, Step.BEGIN_COMBAT)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.stack.is_empty()
        # ... then to p0's next precombat main.
        advance_to_phase(game, Phase.COMBAT, Step.BEGIN_COMBAT)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert len(game.stack) == 1
        p0._script.extend([True, second])  # cast the copy; cast Second Pull
        while not game.stack.is_empty():
            resolve_top(game)
        assert p0.zones[Zone.GRAVEYARD].contains(second)
        # Exactly one Capstone object exists in exile (the copy vanished).
        capstones = [c for c in p0.zones[Zone.EXILE].get_all()
                     if c.name == "Improvisation Capstone"]
        assert len(capstones) == 1
        # No Capstone ever hits the graveyard.
        assert all(c.name != "Improvisation Capstone"
                   for c in p0.zones[Zone.GRAVEYARD].get_all())

    def test_paradigm_can_decline(self):
        game = create_game()
        p0 = game.players[0]
        pull = Instant(name="Pull", mana_cost=ManaCost.parse("{4}"))
        _put_library(game, 0, [pull])
        _hand_capstone(game)
        p0._script.append(None)  # decline free cast
        cast_spell(game, 0, "Improvisation Capstone")
        advance_to_phase(game, Phase.COMBAT, Step.BEGIN_COMBAT)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        advance_to_phase(game, Phase.COMBAT, Step.BEGIN_COMBAT)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        p0._script.append(False)  # decline the Paradigm copy
        while not game.stack.is_empty():
            resolve_top(game)
        capstones = [c for c in p0.zones[Zone.EXILE].get_all()
                     if c.name == "Improvisation Capstone"]
        assert len(capstones) == 1
