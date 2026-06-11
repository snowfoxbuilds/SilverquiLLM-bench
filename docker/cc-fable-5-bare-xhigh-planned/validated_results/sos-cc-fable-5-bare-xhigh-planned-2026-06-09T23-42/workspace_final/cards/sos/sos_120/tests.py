"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Land, Sorcery
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state


def _stack_library(game, player_index, cards):
    """Put *cards* into the library, last item = top of library."""
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for card in cards:
        card.owner = card.controller = player
        library.add(card)


def _cast_capstone(game):
    set_board_state(
        game, 0, hand=[ImprovisationCapstone()],
        mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
    )
    cast_spell(game, 0, "Improvisation Capstone")


class TestImprovisationCapstone:
    def test_exiles_until_mv_4_and_self_exiles(self):
        game = create_game(scripts=([False, False], []))
        p1 = game.players[0]
        stay = Instant(name="Stay", mana_cost=ManaCost.parse("{3}"))
        mv2_a = Instant(name="Two A", mana_cost=ManaCost.parse("{2}"))
        mv2_b = Instant(name="Two B", mana_cost=ManaCost.parse("{1}{R}"))
        _stack_library(game, 0, [stay, mv2_a, mv2_b])  # top = Two B
        _cast_capstone(game)
        exile = game.get_exile(p1)
        assert exile.contains(mv2_a) and exile.contains(mv2_b)
        assert p1.zones[Zone.LIBRARY].contains(stay)  # stopped at total 4
        # Paradigm: the Capstone is exiled, not in the graveyard.
        capstone = [c for c in exile.get_all() if c.name == "Improvisation Capstone"]
        assert len(capstone) == 1
        assert game.get_graveyard(p1).get_all() == []

    def test_may_cast_exiled_spells_free(self):
        game = create_game(scripts=([True], []))
        p1 = game.players[0]

        class Surge(Sorcery):
            def __init__(self, **kw):
                kw.setdefault("name", "Surge")
                kw.setdefault("mana_cost", ManaCost.parse("{4}"))
                super().__init__(**kw)

            def on_resolve(self, g):
                self.controller.life += 5

        surge = Surge()
        _stack_library(game, 0, [surge])
        _cast_capstone(game)
        assert p1.life == 25  # cast for free and resolved
        assert game.get_graveyard(p1).contains(surge)

    def test_lands_stay_exiled_not_castable(self):
        # Land (MV 0) then a 4-drop on top of it: both exiled, only the
        # creature is offered (one script entry).
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        land = Land(name="Some Land")
        big = Creature(name="Big", mana_cost=ManaCost.parse("{4}"),
                       base_power=4, base_toughness=4)
        _stack_library(game, 0, [big, land])  # top = land (MV 0), then Big
        _cast_capstone(game)
        exile = game.get_exile(p1)
        assert exile.contains(land) and exile.contains(big)

    def test_empty_library_no_crash(self):
        game = create_game()
        p1 = game.players[0]
        _cast_capstone(game)
        exile_names = [c.name for c in game.get_exile(p1).get_all()]
        assert exile_names == ["Improvisation Capstone"]

    def test_paradigm_copy_each_first_main_phase(self):
        game = create_game(scripts=([False], []))
        p1, p2 = game.players
        big1 = Creature(name="Big One", mana_cost=ManaCost.parse("{4}"),
                        base_power=4, base_toughness=4)
        big2 = Creature(name="Big Two", mana_cost=ManaCost.parse("{4}"),
                        base_power=4, base_toughness=4)
        _stack_library(game, 0, [big2, big1])  # top = big1
        _cast_capstone(game)  # exiles big1, declines casting it, self-exiles
        assert game.get_exile(p1).contains(big1)

        # Advance to p1's next precombat main (full turn cycle).
        advance_to_phase(game, Phase.COMBAT, Step.BEGIN_COMBAT)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        if game.active_player is not p1:
            advance_to_phase(game, Phase.COMBAT, Step.BEGIN_COMBAT)
            advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p1
        assert len(game.stack) == 1  # paradigm trigger waiting

        # Resolve: cast the copy; the copy peels big2 and we decline it.
        p1._script.extend(["pass", True, "pass", False])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)

        exile = game.get_exile(p1)
        assert exile.contains(big2)  # the copy resolved and peeled
        capstones = [c for c in exile.get_all() if c.name == "Improvisation Capstone"]
        assert len(capstones) == 1  # copy vanished; original still exiled
        assert game.get_graveyard(p1).get_all() == []

    def test_paradigm_offer_is_recurring(self):
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        _cast_capstone(game)
        for _ in range(2):
            # Two consecutive turns: offered and declined both times.
            advance_to_phase(game, Phase.COMBAT, Step.BEGIN_COMBAT)
            advance_to_phase(game, Phase.PRECOMBAT_MAIN)
            if game.active_player is not p1:
                advance_to_phase(game, Phase.COMBAT, Step.BEGIN_COMBAT)
                advance_to_phase(game, Phase.PRECOMBAT_MAIN)
            assert len(game.stack) == 1
            p1._script.extend(["pass", False])
            p2._script.extend(["pass"])
            priority_loop(game)
        capstones = [c for c in game.get_exile(p1).get_all()
                     if c.name == "Improvisation Capstone"]
        assert len(capstones) == 1
