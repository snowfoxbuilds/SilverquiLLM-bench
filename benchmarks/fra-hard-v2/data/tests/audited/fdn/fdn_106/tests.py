"""Reference test for FDN 106 — Loot, Exuberant Explorer.

The ``{4}{G}{G}, {T}`` activated ability taps Loot and spends the mana as its
cost, and cannot be activated while Loot is tapped.
"""

from __future__ import annotations

from cards.fdn.fdn_106.card_impl import LootExuberantExplorer, LootExuberantExplorerAbility2
from cards.fdn.fdn_227.card_impl import LlanowarElves
from engine.card import printed_class
from engine.types import ManaCost, ManaType
from test_interface import Phase, Side, Zone, card, create_game

from silverquillm.table import Table, moves, off_stack, on_stack, taps


def _setup(tapped=False):
    loot, elves = card(LootExuberantExplorer, tapped=tapped), card(LlanowarElves)
    game = create_game(
        Side(battlefield=[loot], hand=[elves], mana={ManaType.GREEN: 6}), Side(), start=(Phase.PRECOMBAT_MAIN, 0)
    )
    return Table(game), loot, elves


class TestLootProperties:
    def test_static_data(self):
        c = LootExuberantExplorer(owner=None)
        assert printed_class(c) is LootExuberantExplorer
        assert c.mana_cost == ManaCost.parse("{2}{G}")
        assert (c.base_power, c.base_toughness) == (1, 4)
        assert {"Beast", "Noble"} <= c.subtypes


class TestLootAbilityCost:
    def test_cost_taps_source_and_pays_mana(self):
        """Loot taps and the six green are spent: once the ability has
        resolved, still in the main phase, Llanowar Elves ({G}) can't be
        cast."""
        t, loot, elves = _setup()
        t.act(0, LootExuberantExplorerAbility2, then=[taps(loot), on_stack(LootExuberantExplorerAbility2, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(LootExuberantExplorerAbility2)])
        t.act_illegal(0, elves, note="no mana is left")
        t.run()

    def test_cost_rejected_when_already_tapped(self):
        """The ability of a tapped Loot is not activated, and no mana is
        spent: the Elves are cast instead."""
        t, _loot, elves = _setup(tapped=True)
        t.act_illegal(0, LootExuberantExplorerAbility2, note="Loot is tapped")
        t.act(0, elves, then=[moves(elves, Zone.STACK)])
        t.run()
