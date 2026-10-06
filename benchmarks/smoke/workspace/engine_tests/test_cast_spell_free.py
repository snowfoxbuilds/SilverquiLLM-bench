"""Casting a spell without paying its mana cost puts it on the stack like any
other cast (rules 601.2, 118.9): it can be responded to and countered, and on
resolution a permanent spell enters the battlefield and any other goes to its
owner's graveyard (608.3, 608.2n).

Each free cast comes from Etali, Primal Storm: whenever it attacks, the top
card of each player's library is exiled and its controller may cast the
spells among them without paying their mana costs. A land exiled that way is
not cast.
"""

from __future__ import annotations

from cards.fdn.fdn_48.card_impl import Refute
from cards.fdn.fdn_79.card_impl import Boltwave
from cards.fdn.fdn_110.card_impl import QuakestriderCeratops
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_153.card_impl import EssenceScatter
from cards.fdn.fdn_160.card_impl import AnOfferYouCantRefuse
from cards.fdn.fdn_191.card_impl import BrazenScourge
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_194.card_impl import EtaliPrimalStorm, EtaliPrimalStormAbility1
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from test_interface import Decision, Side, Step, Zone, card, create_game, player

from silverquillm.table import Table, appears, life, moves, off_stack, on_stack, taps


def _etali_attacks(p0_top, p1_top, *, choices=(), p1_hand=(), p1_lands=0, p1_library=()):
    """Turn 1: player 0's Etali attacks, its trigger exiles ``p0_top`` and
    ``p1_top``, and player 0 casts every spell among them for free, answering
    the casts' questions with ``choices``.

    Returns the table at player 0's priority with those spells on the stack —
    ``p1_top`` above ``p0_top`` when both are cast — and player 1's Islands.
    """
    etali = card(EtaliPrimalStorm)
    islands = [card(Island) for _ in range(p1_lands)]
    game = create_game(
        Side(battlefield=[etali], library=[p0_top]),
        Side(hand=list(p1_hand), battlefield=islands, library=[p1_top, *p1_library]),
        start=(Step.BEGIN_COMBAT, 0),
    )
    t = Table(game)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, etali, then=[taps(etali), on_stack(EtaliPrimalStormAbility1, 0)])
    t.pass_(0, choices=[Decision.yes(), *choices])
    exiled = [off_stack(EtaliPrimalStormAbility1)]
    for top in (p0_top, p1_top):
        # A spell on the stack is seen on its controller's side.
        exiled.append(moves(top, Zone.EXILE) if top.cls is Plains else moves(top, Zone.STACK, seat=0))
    t.pass_(1, then=exiled, note="each spell exiled is cast without paying its mana cost")
    return t, islands


def _counter(t, islands, counterspell, target, *, then=()):
    """Player 0 passes, and player 1 taps ``islands`` and casts
    ``counterspell`` at ``target``, which both players let resolve."""
    t.pass_(0)
    for island in islands:
        t.act(1, island, then=[taps(island)])
    t.act(1, counterspell, choices=[target], then=[moves(counterspell, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(counterspell, Zone.GRAVEYARD), *then])


class TestCastSpellFreePutsOnStack:
    """A spell cast for free goes on the stack rather than resolving at once."""

    def test_creature_goes_on_stack(self):
        lions = card(SavannahLions)
        t, _ = _etali_attacks(lions, card(Plains))
        final = t.run()
        assert [s.handle for s in final.stack] == [lions]

    def test_sorcery_goes_on_stack(self):
        boltwave = card(Boltwave)
        t, _ = _etali_attacks(boltwave, card(Plains))
        final = t.run()
        assert [s.handle for s in final.stack] == [boltwave]

    def test_instant_goes_on_stack(self):
        bolt = card(BurstLightning)
        t, _ = _etali_attacks(bolt, card(Plains), choices=[player(1)])
        final = t.run()
        assert [s.handle for s in final.stack] == [bolt]


class TestCastSpellFreeNoManaRequired:
    """A free cast needs no mana: its controller has none to pay with."""

    def test_expensive_creature_cast_with_empty_mana_pool(self):
        ceratops = card(QuakestriderCeratops)
        t, _ = _etali_attacks(ceratops, card(Plains))
        t.pass_(0)
        t.pass_(1, then=[moves(ceratops, Zone.BATTLEFIELD)], note="the six-mana Dinosaur cost nothing")
        t.run()


class TestCastSpellFreeResolution:
    """A spell cast for free resolves like any other spell."""

    def test_creature_resolves_to_battlefield(self):
        lions = card(SavannahLions)
        t, _ = _etali_attacks(lions, card(Plains))
        t.pass_(0)
        t.pass_(1, then=[moves(lions, Zone.BATTLEFIELD)])
        t.run()

    def test_sorcery_resolves_to_graveyard(self):
        boltwave = card(Boltwave)
        t, _ = _etali_attacks(boltwave, card(Plains))
        t.pass_(0)
        t.pass_(1, then=[life(1, 17), moves(boltwave, Zone.GRAVEYARD)])
        t.run()

    def test_on_resolve_hook_called(self):
        """The spell's effect happens when it resolves, not when it is cast."""
        bolt = card(BurstLightning)
        t, _ = _etali_attacks(bolt, card(Plains), choices=[player(1)])
        t.pass_(0, note="player 1 is still at 20 life while Burst Lightning is on the stack")
        t.pass_(1, then=[life(1, 18), moves(bolt, Zone.GRAVEYARD)])
        t.run()


class TestCastSpellFreeCounterable:
    """A spell cast for free can be responded to while it is on the stack."""

    def test_spell_is_on_stack_and_can_be_removed_before_resolving(self):
        boltwave, offer = card(Boltwave), card(AnOfferYouCantRefuse)
        t, islands = _etali_attacks(
            boltwave, card(Plains), p1_hand=[offer], p1_lands=1
        )
        _counter(t, islands, offer, boltwave, then=[moves(boltwave, Zone.GRAVEYARD), appears(0), appears(0)])
        final = t.run()
        assert final.players[1].life == 20

    def test_multiple_free_casts_all_go_on_stack(self):
        """Both players' exiled spells are cast, and each resolves in turn."""
        lions, scourge = card(SavannahLions), card(BrazenScourge)
        t, _ = _etali_attacks(lions, scourge)
        t.pass_(0, note="both spells are on the stack, player 1's on top")
        t.pass_(1, then=[moves(scourge, Zone.BATTLEFIELD, seat=0)])
        t.pass_(0)
        t.pass_(1, then=[moves(lions, Zone.BATTLEFIELD)])
        t.run()

    def test_countered_spell_does_not_resolve(self):
        lions, scatter = card(SavannahLions), card(EssenceScatter)
        t, islands = _etali_attacks(lions, card(Plains), p1_hand=[scatter], p1_lands=2)
        _counter(t, islands, scatter, lions, then=[moves(lions, Zone.GRAVEYARD)])
        t.run()


class TestCastSpellFreeCounteredByRealCounter:
    """Counterspells counter a spell cast for free, which goes to its owner's
    graveyard without resolving."""

    def test_counter_spell_removes_free_cast_from_stack_to_graveyard(self):
        """Player 0 casts player 1's Boltwave; Refute counters it into player
        1's graveyard, and player 1 then draws and discards."""
        boltwave, refute, drawn = card(Boltwave), card(Refute), card(Plains)
        t, islands = _etali_attacks(
            card(Plains), boltwave, p1_hand=[refute], p1_lands=3,
            p1_library=[drawn],
        )
        t.pass_(0)
        for island in islands:
            t.act(1, island, then=[taps(island)])
        t.act(1, refute, choices=[boltwave, drawn], then=[moves(refute, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[
            moves(boltwave, Zone.GRAVEYARD, seat=1),
            moves(drawn, Zone.HAND),
            moves(drawn, Zone.GRAVEYARD),
            moves(refute, Zone.GRAVEYARD),
        ])
        final = t.run()
        assert final.where(boltwave) is Zone.GRAVEYARD
        assert boltwave in [s.handle for s in final.players[1].graveyard]

    def test_counter_spell_prevents_on_resolve_from_firing(self):
        bolt, offer = card(BurstLightning), card(AnOfferYouCantRefuse)
        t, islands = _etali_attacks(bolt, card(Plains), choices=[player(1)], p1_hand=[offer], p1_lands=1)
        _counter(t, islands, offer, bolt, then=[moves(bolt, Zone.GRAVEYARD), appears(0), appears(0)])
        final = t.run()
        assert final.players[1].life == 20

    def test_counter_creature_free_cast_prevents_battlefield_entry(self):
        """Player 0 casts player 1's Quakestrider Ceratops, and Essence
        Scatter counters it into player 1's graveyard."""
        ceratops, scatter = card(QuakestriderCeratops), card(EssenceScatter)
        t, islands = _etali_attacks(card(Plains), ceratops, p1_hand=[scatter], p1_lands=2)
        _counter(t, islands, scatter, ceratops, then=[moves(ceratops, Zone.GRAVEYARD, seat=1)])
        final = t.run()
        assert [s.card for s in final.players[0].battlefield] == [EtaliPrimalStorm]

    def test_counter_targets_specific_spell_among_multiple_on_stack(self):
        """Essence Scatter counters the bottom of two creature spells; the
        other still resolves."""
        lions, scourge, scatter = card(SavannahLions), card(BrazenScourge), card(EssenceScatter)
        t, islands = _etali_attacks(lions, scourge, p1_hand=[scatter], p1_lands=2)
        _counter(t, islands, scatter, lions, then=[moves(lions, Zone.GRAVEYARD)])
        t.pass_(0)
        t.pass_(1, then=[moves(scourge, Zone.BATTLEFIELD, seat=0)])
        t.run()
