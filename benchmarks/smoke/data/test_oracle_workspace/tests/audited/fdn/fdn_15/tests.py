"""Hare Apparent counts other friendly Hares through actual cast and entry.

"When this creature enters, create a number of 1/1 white Rabbit creature
tokens equal to the number of other creatures you control named Hare
Apparent." The enters ability is a triggered ability on the stack. Colour is
not visible at the table, so the Rabbits are judged as 1/1s in combat.
"""

from __future__ import annotations

from cards.fdn.fdn_15.card_impl import HareApparent, HareApparentAbility1
from cards.fdn.fdn_164.card_impl import SpectralSailor
from cards.fdn.fdn_280.card_impl import Forest
from engine.card import Creature, printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game, token

from silverquillm.table import Table, appears, ceases, life, moves, off_stack, on_stack, taps


def _hare_enters(mine=(), theirs=(), *, rabbits, mana=None):
    """Player 0 casts Hare Apparent with ``mine`` on the battlefield; its
    trigger makes ``rabbits`` Rabbits."""
    hare = card(HareApparent)
    game = create_game(
        Side(hand=[hare], battlefield=list(mine), library=[Forest], mana=mana or {ManaType.WHITE: 2}),
        Side(battlefield=list(theirs), library=[Forest]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, hare, then=[moves(hare, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(hare, Zone.BATTLEFIELD), on_stack(HareApparentAbility1, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(HareApparentAbility1), *[appears(0) for _ in range(rabbits)]])
    return t


class TestHareApparentProperties:
    """Static card data should match the FDN 15 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(HareApparent(owner=None), Creature)

    def test_name(self) -> None:
        assert printed_class(HareApparent(owner=None)) is HareApparent

    def test_mana_cost(self) -> None:
        assert HareApparent(owner=None).mana_cost == ManaCost.parse("{1}{W}")

    def test_power_toughness(self) -> None:
        card = HareApparent(owner=None)
        assert (card.base_power, card.base_toughness) == (2, 2)

    def test_subtypes(self) -> None:
        assert HareApparent(owner=None).subtypes == {"Rabbit", "Noble"}


class TestHareApparentEtb:
    """ETB: one Rabbit per *other* Hare Apparent you control."""

    def test_lone_hare_makes_no_tokens(self) -> None:
        """The "other" clause: a Hare Apparent that is the only one you
        control mints zero tokens (it never counts itself)."""
        _hare_enters(rabbits=0).run()

    def test_two_other_hares_make_two_rabbits(self) -> None:
        _hare_enters([HareApparent, HareApparent], rabbits=2).run()

    def test_only_your_own_hares_count(self) -> None:
        """Hare Apparents an opponent controls do not feed the count."""
        _hare_enters([HareApparent], [HareApparent, HareApparent], rabbits=1).run()

    def test_tokens_are_one_one_rabbits(self) -> None:
        """On player 0's next turn both Rabbits attack: the one Spectral
        Sailor (1/1) blocks trades with it, and the other deals 1."""
        sailor = card(SpectralSailor)
        t = _hare_enters([HareApparent, HareApparent], [sailor], rabbits=2)
        first, second = token(1), token(2)
        t.pass_to(Phase.PRECOMBAT_MAIN, 1)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, first, second, then=[taps(first), taps(second)])
        t.pass_(0)
        t.pass_(1)
        t.act(1, sailor, scoped={sailor: first})
        t.pass_(0)
        t.pass_(1, then=[ceases(first), moves(sailor, Zone.GRAVEYARD), life(1, 19)])
        t.run()

    def test_etb_fires_through_the_cast_pipeline(self) -> None:
        """End-to-end: casting Hare Apparent from a mixed pool with two others
        already in play makes two Rabbits."""
        _hare_enters([HareApparent, HareApparent], rabbits=2, mana={ManaType.WHITE: 1, ManaType.RED: 1}).run()
