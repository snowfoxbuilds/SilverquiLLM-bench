"""Audited tests for FDN 205 — Seismic Rupture.

"Seismic Rupture deals 2 damage to each creature without flying." It takes
no targets and hits every creature without flying on both battlefields; 2
damage kills a creature with toughness 2 but not one with toughness 3.
"""

from __future__ import annotations

from cards.fdn.fdn_52.card_impl import StrixLookout
from cards.fdn.fdn_191.card_impl import BrazenScourge
from cards.fdn.fdn_205.card_impl import SeismicRupture
from cards.fdn.fdn_250.card_impl import BurnishedHart
from engine.card import Sorcery, printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Zone, card, create_game

from table import Table, moves


def _rupture(mine=(), theirs=(), *, dies=()):
    """Player 0 casts Seismic Rupture, and both players pass to resolve it;
    the creatures in ``dies`` go to their owners' graveyards."""
    rupture = card(SeismicRupture)
    game = create_game(
        Side(hand=[rupture], battlefield=list(mine), mana={ManaType.RED: 3}),
        Side(battlefield=list(theirs)),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, rupture, then=[moves(rupture, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(rupture, Zone.GRAVEYARD), *(moves(c, Zone.GRAVEYARD) for c in dies)])
    return t


class TestSeismicRuptureProperties:
    """Static card data should match the FDN 205 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(SeismicRupture(owner=None), Sorcery)

    def test_name(self) -> None:
        assert printed_class(SeismicRupture(owner=None)) is SeismicRupture

    def test_mana_cost(self) -> None:
        assert SeismicRupture(owner=None).mana_cost == ManaCost.parse("{2}{R}")


class TestSeismicRuptureDamage:
    """Deals 2 to each creature without flying, on every battlefield."""

    def test_ground_creature_takes_two(self) -> None:
        """The 2/2 dies and the 3/3 survives: exactly 2 damage each."""
        hart, scourge = card(BurnishedHart), card(BrazenScourge)
        _rupture([hart, scourge], dies=[hart]).run()

    def test_flyer_is_untouched(self) -> None:
        _rupture([card(StrixLookout)]).run()

    def test_hits_both_battlefields(self) -> None:
        """Untargeted: the caster's own ground creatures are hit too."""
        mine, theirs = card(BurnishedHart), card(BurnishedHart)
        _rupture([mine], [theirs], dies=[mine, theirs]).run()

    def test_lethal_ground_creature_dies_via_sba(self) -> None:
        """2 damage is lethal to a 2-toughness ground creature; a 2-toughness
        flyer survives untouched."""
        small, bird = card(BurnishedHart), card(StrixLookout)
        _rupture(theirs=[small, bird], dies=[small]).run()

    def test_deals_damage_through_the_cast_pipeline(self) -> None:
        """Cast from hand, the sweep resolves on the board and the spell goes
        to its owner's graveyard."""
        victim = card(BurnishedHart)
        _rupture(theirs=[victim], dies=[victim]).run()
