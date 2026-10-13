"""Imprisoned in the Moon, played at the table.

Each test puts Imprisoned in the Moon on a permanent and judges it by what the
players can do with that permanent: which of its abilities they may still
activate, what its "{T}: Add {C}" pays for and for whom, whether it can be
targeted as a creature, and whether Elvish Archdruid counts it among the Elves.
Destroying the Aura with Cathar Commando shows the permanent getting back what
it had.
"""

from __future__ import annotations

from cards.fdn.fdn_139.card_impl import CatharCommando, CatharCommandoAbility2
from cards.fdn.fdn_156.card_impl import ImprisonedInTheMoon, ImprisonedInTheMoonAbility2
from cards.fdn.fdn_175.card_impl import HerosDownfall
from cards.fdn.fdn_219.card_impl import ElvishArchdruid, ElvishArchdruidAbility2
from cards.fdn.fdn_227.card_impl import LlanowarElves, LlanowarElvesAbility1
from cards.fdn.fdn_262.card_impl import EvolvingWilds, EvolvingWildsAbility1
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_276.card_impl import Swamp
from cards.fdn.fdn_280.card_impl import Forest, ForestAbility1
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import Phase, Side, Zone, ability, card, create_game

from table import Table, moves, off_stack, on_stack, taps

MAIN = (Phase.PRECOMBAT_MAIN, 0)
TAP_FOR_C = ImprisonedInTheMoonAbility2


class TestImprisonedInTheMoonProperties:
    def test_static_data(self):
        moon = ImprisonedInTheMoon(owner=None)
        assert printed_class(moon) is ImprisonedInTheMoon
        assert moon.mana_cost == ManaCost.parse("{2}{U}")
        assert "Aura" in moon.subtypes


def _game(battlefield=(), hand=(), opposing=(), opposing_hand=()):
    """Player 0's main phase with Imprisoned in the Moon and three Islands to
    cast it, ``battlefield`` and ``hand`` beside them, against ``opposing``
    and ``opposing_hand``."""
    moon = card(ImprisonedInTheMoon)
    islands = [card(Island) for _ in range(3)]
    game = create_game(
        Side(hand=[moon, *hand], battlefield=[*islands, *battlefield]),
        Side(hand=list(opposing_hand), battlefield=list(opposing)),
        start=MAIN,
    )
    return Table(game), moon, islands


def _imprison(t, moon, islands, target):
    """Player 0 taps the Islands and casts Imprisoned in the Moon on ``target``."""
    for island in islands:
        t.act(0, island, then=[taps(island)])
    t.act(0, moon, choices=[target], then=[moves(moon, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(moon, Zone.BATTLEFIELD)])


def _flash_in_cathar(t, permanent, plains, cathar):
    """Player 1, holding priority, taps ``permanent`` for {C} and the Plains for
    {W}, and flashes in Cathar Commando ({1}{W}) with them."""
    t.act(1, ability(permanent, TAP_FOR_C), then=[taps(permanent)])
    t.act(1, plains, then=[taps(plains)])
    t.act(1, cathar, then=[moves(cathar, Zone.STACK)])


def _destroy(t, cathar, plains, moon):
    """Player 0 taps the Plains and sacrifices Cathar Commando to destroy the Aura."""
    t.act(0, plains, then=[taps(plains)])
    t.act(0, CatharCommandoAbility2, choices=[moon],
          then=[moves(cathar, Zone.GRAVEYARD), on_stack(CatharCommandoAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(CatharCommandoAbility2), moves(moon, Zone.GRAVEYARD)])


class TestImprisonedLand:
    def test_a_forest_taps_for_colorless_instead_of_green(self):
        """The Forest's own {G} ability is gone; the {C} it taps for instead
        pays the generic part of Cathar Commando's {1}{W}."""
        forest, plains, cathar = card(Forest), card(Plains), card(CatharCommando)
        t, moon, islands = _game(battlefield=[forest, plains], hand=[cathar])
        _imprison(t, moon, islands, forest)
        t.act_illegal(0, ability(forest, ForestAbility1))
        t.act(0, ability(forest, TAP_FOR_C), then=[taps(forest)])
        t.act(0, plains, then=[taps(plains)])
        t.act(0, cathar, then=[moves(cathar, Zone.STACK)])
        t.run()

    def test_its_colorless_mana_cannot_pay_green(self):
        forest, elves = card(Forest), card(LlanowarElves)
        t, moon, islands = _game(battlefield=[forest], hand=[elves])
        _imprison(t, moon, islands, forest)
        t.act(0, ability(forest, TAP_FOR_C), then=[taps(forest)])
        t.act_illegal(0, elves, note="{C} is not {G}")
        t.run()

    def test_a_land_loses_its_other_activated_abilities(self):
        wilds = card(EvolvingWilds)
        t, moon, islands = _game(battlefield=[wilds])
        _imprison(t, moon, islands, wilds)
        t.act_illegal(0, ability(wilds, EvolvingWildsAbility1))
        t.act(0, ability(wilds, TAP_FOR_C), then=[taps(wilds)])
        t.run()

    def test_an_opponents_land_taps_for_colorless_for_its_controller(self):
        """The {C} goes to the Forest's controller, who pays Cathar Commando's
        generic mana with it."""
        forest, plains, cathar = card(Forest), card(Plains), card(CatharCommando)
        t, moon, islands = _game(opposing=[forest, plains], opposing_hand=[cathar])
        _imprison(t, moon, islands, forest)
        t.pass_(0)
        t.act_illegal(1, ability(forest, ForestAbility1))
        _flash_in_cathar(t, forest, plains, cathar)
        t.run()

    def test_destroying_the_aura_gives_the_forest_back_its_green(self):
        """With the Aura gone the Forest taps for {G} again, which casts
        Llanowar Elves, and no longer for {C}."""
        forest, plains, cathar, elves = card(Forest), card(Plains), card(CatharCommando), card(LlanowarElves)
        t, moon, islands = _game(battlefield=[forest, plains, cathar], hand=[elves])
        _imprison(t, moon, islands, forest)
        _destroy(t, cathar, plains, moon)
        t.act_illegal(0, ability(forest, TAP_FOR_C))
        t.act(0, ability(forest, ForestAbility1), then=[taps(forest)])
        t.act(0, elves, then=[moves(elves, Zone.STACK)])
        t.run()


class TestImprisonedCreature:
    def test_a_creature_becomes_a_land_tapping_for_colorless(self):
        """Llanowar Elves loses its {G} ability and taps for {C}; as a land it
        is no creature, so Hero's Downfall cannot target it."""
        elves, downfall = card(LlanowarElves), card(HerosDownfall)
        swamps = [card(Swamp) for _ in range(3)]
        t, moon, islands = _game(battlefield=[elves, *swamps], hand=[downfall])
        _imprison(t, moon, islands, elves)
        t.act_illegal(0, ability(elves, LlanowarElvesAbility1))
        t.act(0, ability(elves, TAP_FOR_C), then=[taps(elves)])
        for swamp in swamps:
            t.act(0, swamp, then=[taps(swamp)])
        t.act_illegal(0, downfall, choices=[elves], note="no longer a creature")
        t.run()

    def test_an_opponents_creature_taps_for_colorless_for_its_controller(self):
        """The {C} goes to the Elves' controller, who pays Cathar Commando's
        generic mana with it."""
        elves, plains, cathar = card(LlanowarElves), card(Plains), card(CatharCommando)
        t, moon, islands = _game(opposing=[elves, plains], opposing_hand=[cathar])
        _imprison(t, moon, islands, elves)
        t.pass_(0)
        t.act_illegal(1, ability(elves, LlanowarElvesAbility1))
        _flash_in_cathar(t, elves, plains, cathar)
        t.run()

    def test_destroying_the_aura_makes_it_a_creature_again(self):
        """With the Aura gone, Llanowar Elves taps for {G} again, which casts
        another Llanowar Elves, and not for {C}; Hero's Downfall destroys it."""
        elves, plains, cathar, downfall = card(LlanowarElves), card(Plains), card(CatharCommando), card(HerosDownfall)
        other = card(LlanowarElves)
        swamps = [card(Swamp) for _ in range(3)]
        t, moon, islands = _game(battlefield=[elves, plains, cathar, *swamps], hand=[downfall, other])
        _imprison(t, moon, islands, elves)
        _destroy(t, cathar, plains, moon)
        t.act_illegal(0, ability(elves, TAP_FOR_C))
        t.act(0, ability(elves, LlanowarElvesAbility1), then=[taps(elves)])
        t.act(0, other, then=[moves(other, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(other, Zone.BATTLEFIELD)])
        for swamp in swamps:
            t.act(0, swamp, then=[taps(swamp)])
        t.act(0, downfall, choices=[elves], then=[moves(downfall, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(downfall, Zone.GRAVEYARD), moves(elves, Zone.GRAVEYARD)])
        t.run()

    def test_archdruid_does_not_count_an_imprisoned_elf(self):
        """Elvish Archdruid adds {G} for each Elf its controller controls; the
        imprisoned Llanowar Elves is not counted, so it adds one {G}: enough for
        one more Llanowar Elves, which resolves, but not a second."""
        elves, archdruid = card(LlanowarElves), card(ElvishArchdruid)
        first, second = card(LlanowarElves), card(LlanowarElves)
        t, moon, islands = _game(battlefield=[elves, archdruid], hand=[first, second])
        _imprison(t, moon, islands, elves)
        t.act(0, ability(archdruid, ElvishArchdruidAbility2), then=[taps(archdruid)])
        t.act(0, first, then=[moves(first, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(first, Zone.BATTLEFIELD)])
        t.act_illegal(0, second, note="Archdruid added only {G}")
        t.run()

    def test_destroying_the_aura_makes_archdruid_count_it_again(self):
        """With the Aura gone, Elvish Archdruid counts Llanowar Elves again and
        adds {G}{G}, enough for two more Llanowar Elves."""
        elves, archdruid, plains, cathar = card(LlanowarElves), card(ElvishArchdruid), card(Plains), card(CatharCommando)
        first, second = card(LlanowarElves), card(LlanowarElves)
        t, moon, islands = _game(battlefield=[elves, archdruid, plains, cathar], hand=[first, second])
        _imprison(t, moon, islands, elves)
        _destroy(t, cathar, plains, moon)
        t.act(0, ability(archdruid, ElvishArchdruidAbility2), then=[taps(archdruid)])
        t.act(0, first, then=[moves(first, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(first, Zone.BATTLEFIELD)])
        t.act(0, second, then=[moves(second, Zone.STACK)])
        t.run()
