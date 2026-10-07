"""Audited tests for FDN 219 — Elvish Archdruid.

"Other Elf creatures you control get +1/+1. {T}: Add {G} for each Elf you
control." The lord bonus shows when a 1/1 Elf survives 1 damage while a
non-Elf 2/2 still dies to 2; the mana ability, which does not use the stack,
pays for a two-mana spell with the Archdruid and one other Elf.
"""

from __future__ import annotations

from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_195.card_impl import FanaticalFirebrand, FanaticalFirebrandAbility2
from cards.fdn.fdn_219.card_impl import ElvishArchdruid
from cards.fdn.fdn_224.card_impl import GnarlidColony
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_250.card_impl import BurnishedHart
from cards.fdn.fdn_278.card_impl import Mountain
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import Phase, Side, Zone, card, create_game

from silverquillm.table import Table, moves, off_stack, on_stack, taps


class TestElvishArchdruidProperties:
    def test_name_and_cost(self) -> None:
        card = ElvishArchdruid(owner=None)
        assert printed_class(card) is ElvishArchdruid
        assert card.mana_cost == ManaCost.parse("{1}{G}{G}")
        assert card.subtypes == {"Elf", "Druid"}


class TestElvishArchdruidLord:
    def test_other_elves_get_plus_one_plus_one(self) -> None:
        druid, elves, hart, brand = card(ElvishArchdruid), card(LlanowarElves), card(BurnishedHart), card(FanaticalFirebrand)
        bolt, mountain = card(BurstLightning), card(Mountain)
        game = create_game(
            Side(battlefield=[druid, elves, hart, brand, mountain], hand=[bolt]),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, FanaticalFirebrandAbility2, choices=[elves],
              then=[moves(brand, Zone.GRAVEYARD), on_stack(FanaticalFirebrandAbility2, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(FanaticalFirebrandAbility2)], note="the 1/1 Elves is 2/2 and survives")
        t.act(0, mountain, then=[taps(mountain)])
        t.act(0, bolt, choices=[hart], then=[moves(bolt, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), moves(hart, Zone.GRAVEYARD)], note="the non-Elf 2/2 is not pumped")
        t.run()

    def test_mana_ability_adds_green_per_elf(self) -> None:
        druid, colony = card(ElvishArchdruid), card(GnarlidColony)
        game = create_game(
            Side(battlefield=[druid, LlanowarElves], hand=[colony]),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, druid, then=[taps(druid)], note="two Elves: {G}{G}")
        t.act(0, colony, then=[moves(colony, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(colony, Zone.BATTLEFIELD)])
        t.run()
