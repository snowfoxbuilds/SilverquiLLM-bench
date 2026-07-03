"""Tests for Improvisation Capstone (sos_120)."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Land
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state

MANA = {ManaType.RED: 2, ManaType.COLORLESS: 5}


def _bear(name: str, cost: str) -> Creature:
    return Creature(name=name, mana_cost=ManaCost.parse(cost),
                    base_power=2, base_toughness=2)


def _stack_library(game, cards):
    """Put cards into p1's library; the last card is the top."""
    library = game.players[0].zones[Zone.LIBRARY]
    for c in cards:
        c.owner = game.players[0]
        c.controller = game.players[0]
        library.add(c)


class TestMainEffect:
    def test_exiles_until_mv_four_and_self_exiles(self):
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone()
        set_board_state(game, 0, hand=[capstone], mana=MANA)
        bottom = _bear("Bottom", "{1}")
        mid = _bear("Mid", "{2}")
        top = _bear("Top", "{3}")
        _stack_library(game, [bottom, mid, top])

        # Decline casting both exiled creatures (top {3} then mid {2} => 5).
        p1._script.extend([False, False])
        cast_spell(game, 0, "Improvisation Capstone")

        assert p1.zones[Zone.EXILE].contains(top)
        assert p1.zones[Zone.EXILE].contains(mid)
        assert p1.zones[Zone.LIBRARY].contains(bottom)
        # Paradigm: the spell itself is exiled, not put into the graveyard.
        assert p1.zones[Zone.EXILE].contains(capstone)
        assert not p1.zones[Zone.GRAVEYARD].contains(capstone)

    def test_may_cast_exiled_cards_for_free(self):
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, hand=[ImprovisationCapstone()], mana=MANA)
        a = _bear("A", "{2}")
        b = _bear("B", "{2}")
        _stack_library(game, [a, b])

        p1._script.extend([True, True])
        cast_spell(game, 0, "Improvisation Capstone")

        assert p1.zones[Zone.BATTLEFIELD].contains(a)
        assert p1.zones[Zone.BATTLEFIELD].contains(b)

    def test_lands_stay_exiled_and_library_can_run_out(self):
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, hand=[ImprovisationCapstone()], mana=MANA)
        plains = Land(name="Plains")
        _stack_library(game, [plains])

        cast_spell(game, 0, "Improvisation Capstone")

        assert p1.zones[Zone.EXILE].contains(plains)
        assert len(p1.zones[Zone.LIBRARY]) == 0


class TestParadigm:
    def _resolve_first(self, game):
        p1 = game.players[0]
        capstone = ImprovisationCapstone()
        set_board_state(game, 0, hand=[capstone], mana=MANA)
        filler = _bear("Filler", "{5}")
        later = _bear("Later", "{4}")
        _stack_library(game, [later, filler])
        p1._script.append(False)  # decline casting Filler
        cast_spell(game, 0, "Improvisation Capstone")
        return capstone, later

    def _to_next_p1_main(self, game):
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p2's main
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p1's main
        assert game.active_player is game.players[0]

    def test_copy_cast_at_next_first_main(self):
        game = create_game()
        p1, p2 = game.players
        capstone, later = self._resolve_first(game)

        self._to_next_p1_main(game)
        # pass/pass -> trigger resolves (yes: cast copy);
        # pass/pass -> copy resolves (decline casting Later).
        p1._script.extend(["pass", True, "pass", False])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)

        # The copy's main effect ran: Later was exiled from the library.
        assert p1.zones[Zone.EXILE].contains(later)
        # The resolved copy ceased to exist: the only Capstone anywhere
        # is the original, still in exile.
        capstones_in_exile = [
            c for c in p1.zones[Zone.EXILE].get_all()
            if getattr(c, "name", None) == "Improvisation Capstone"
        ]
        assert capstones_in_exile == [capstone]
        assert not p1.zones[Zone.GRAVEYARD].contains(capstone)
        for player in game.players:
            for zone in (Zone.GRAVEYARD, Zone.STACK, Zone.BATTLEFIELD):
                assert all(
                    getattr(c, "name", None) != "Improvisation Capstone"
                    for c in player.zones[zone].get_all()
                )

    def test_decline_copy(self):
        game = create_game()
        p1, p2 = game.players
        capstone, later = self._resolve_first(game)

        self._to_next_p1_main(game)
        p1._script.extend(["pass", False])
        p2._script.extend(["pass"])
        priority_loop(game)

        assert p1.zones[Zone.LIBRARY].contains(later)
        capstone_count = sum(
            1 for c in p1.zones[Zone.EXILE].get_all()
            if getattr(c, "name", None) == "Improvisation Capstone"
        )
        assert capstone_count == 1
