"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Land
from engine.casting import resolve_top
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state


class LifeSip(Instant):
    """Test instant with an observable effect: gain 1 life."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Life Sip")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        super().__init__(**kwargs)

    def on_resolve(self, game) -> None:
        if self.controller is not None:
            self.controller.life += 1


def _set_library(game, player_index, top_to_bottom):
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for card in library.get_all():
        library.remove(card)
    for card in reversed(top_to_bottom):  # last added = top
        card.owner = player
        card.controller = player
        library.add(card)


def _cast_capstone(game, extra_script=None):
    p1 = game.players[0]
    cap = ImprovisationCapstone(owner=p1)
    set_board_state(game, 0, hand=[cap],
                    mana={ManaType.RED: 2, ManaType.COLORLESS: 5})
    for entry in extra_script or []:
        p1._script.append(entry)
    cast_spell(game, 0, "Improvisation Capstone")
    return cap


class TestImprovisationCapstoneResolve:
    def test_exiles_until_total_mv_4(self):
        game = create_game()
        p1 = game.players[0]
        a = LifeSip(name="A")                       # mv 2
        b = Creature(name="B", mana_cost=ManaCost.parse("{3}"),
                     base_power=2, base_toughness=2)  # mv 3
        c = LifeSip(name="C")                       # mv 2 — should stay
        _set_library(game, 0, [a, b, c])
        cap = _cast_capstone(game, extra_script=[None])  # decline all casts
        exile = game.get_exile(p1)
        assert exile.contains(a) and exile.contains(b)
        assert game.get_library(p1).contains(c)
        assert exile.contains(cap)  # Paradigm: the spell exiles itself

    def test_free_casts_from_among_exiled(self):
        game = create_game()
        p1 = game.players[0]
        sip = LifeSip()                              # mv 2
        bear = Creature(name="Bear", mana_cost=ManaCost.parse("{3}"),
                        base_power=2, base_toughness=2)
        _set_library(game, 0, [sip, bear])
        cap = _cast_capstone(game, extra_script=[bear, sip])
        # Both were cast for free: bear hits the battlefield, sip resolves.
        assert game.get_battlefield(p1).contains(bear)
        assert p1.life == 21
        assert game.get_graveyard(p1).contains(sip)
        assert game.get_exile(p1).contains(cap)

    def test_lands_stay_exiled(self):
        game = create_game()
        p1 = game.players[0]
        land = Land(name="Some Land")                # mv 0
        big = Creature(name="Big", mana_cost=ManaCost.parse("{5}"),
                       base_power=5, base_toughness=5)
        _set_library(game, 0, [land, big])
        _cast_capstone(game, extra_script=[None])
        assert game.get_exile(p1).contains(land)
        assert game.get_exile(p1).contains(big)

    def test_small_library_exiles_everything(self):
        game = create_game()
        p1 = game.players[0]
        only = LifeSip(name="Only")  # mv 2 < 4, library then empty
        _set_library(game, 0, [only])
        _cast_capstone(game, extra_script=[None])
        assert game.get_exile(p1).contains(only)
        assert len(game.get_library(p1)) == 0


class TestImprovisationCapstoneParadigm:
    def test_recurring_copy_each_of_your_first_mains(self):
        game = create_game()
        p1 = game.players[0]
        first = LifeSip(name="First")
        later = LifeSip(name="Later")
        bigger = Creature(name="Bigger", mana_cost=ManaCost.parse("{4}"),
                          base_power=4, base_toughness=4)
        _set_library(game, 0, [first, later, bigger])
        cap = _cast_capstone(game, extra_script=[None])  # 'First'+'Later' exiled
        # Advance to p2's main: no trigger for p1's Capstone.
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is game.players[1]
        assert game.stack.is_empty()
        # p1's next main: may cast a copy.
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p1
        assert len(game.stack) == 1
        p1._script.append(True)   # cast the copy
        p1._script.append(None)   # decline the copy's free casts
        resolve_top(game)         # paradigm trigger -> pushes the copy
        resolve_top(game)         # copy resolves: exiles 'Bigger' (mv 4)
        assert game.get_exile(p1).contains(bigger)
        # Original is still exiled and exactly one trigger remains.
        assert game.get_exile(p1).contains(cap)
        assert len(game.trigger_manager.get_triggers_for_source(cap)) == 1

    def test_decline_copy(self):
        game = create_game()
        p1 = game.players[0]
        _set_library(game, 0, [LifeSip(name="X")])
        cap = _cast_capstone(game, extra_script=[None])
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p1
        p1._script.append(False)  # decline
        resolve_top(game)
        assert game.stack.is_empty()
        assert game.get_exile(p1).contains(cap)
