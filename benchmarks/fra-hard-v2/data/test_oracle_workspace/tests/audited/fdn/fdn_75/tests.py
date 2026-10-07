"""Reference test for FDN 75 — Vampire Soulcaller.

The enters ability returns target creature card from its controller's
graveyard to their hand: only their own creature cards are offered, and the
card it targets comes back as the Soulcaller arrives.
"""

from __future__ import annotations

from cards.fdn.fdn_75.card_impl import VampireSoulcaller, VampireSoulcallerAbility3
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_227.card_impl import LlanowarElves
from engine.card import printed_class
from engine.types import Keyword, ManaCost, ManaType, Phase, Zone
from test_interface import Side, card, create_game

from silverquillm.table import Table, moves, off_stack, on_stack

_MANA = {ManaType.BLACK: 1, ManaType.COLORLESS: 4}


def _soulcaller_game(graveyard=(), opponent_graveyard=()):
    soulcaller = card(VampireSoulcaller)
    game = create_game(
        Side(hand=[soulcaller], graveyard=list(graveyard), mana=_MANA),
        Side(graveyard=list(opponent_graveyard)),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    return Table(game), soulcaller


def _cast(t, soulcaller, targets, *, branches=None):
    """Player 0 casts the Soulcaller; as it enters, its trigger goes on the
    stack with its target chosen from ``targets`` (rule 603.3d) — or from
    ``branches``, tried in turn as the engine rejects a choice."""
    t.act(0, soulcaller, then=[moves(soulcaller, Zone.STACK)])
    if branches:
        t.pass_(0, branches=branches)
    else:
        t.pass_(0, choices=targets)
    t.pass_(1, then=[moves(soulcaller, Zone.BATTLEFIELD), on_stack(VampireSoulcallerAbility3, 0)])


def _resolve(t, *then, note=None):
    t.pass_(0)
    t.pass_(1, then=[off_stack(VampireSoulcallerAbility3), *then], note=note)


class TestVampireSoulcallerProperties:
    def test_static_data(self):
        card = VampireSoulcaller(owner=None)
        assert printed_class(card) is VampireSoulcaller
        assert card.mana_cost == ManaCost.parse("{4}{B}")
        assert (card.base_power, card.base_toughness) == (3, 2)
        assert card.subtypes == {"Vampire", "Warlock"}
        assert Keyword.FLYING & card.keywords


class TestVampireSoulcallerETB:
    def test_returns_targeted_creature_card_to_hand(self):
        dead = card(SavannahLions)
        t, soulcaller = _soulcaller_game([dead])
        _cast(t, soulcaller, [dead])
        _resolve(t, moves(dead, Zone.HAND), note="the creature card returns to hand")
        t.run()

    def test_option_set_only_your_creature_cards(self):
        """Player 0 prefers the opponent's creature card, then their own
        instant, then their own creature card: only the last is a legal
        target, the others either not offered or offered and rejected."""
        dead, instant, other = card(SavannahLions), card(BurstLightning), card(LlanowarElves)
        t, soulcaller = _soulcaller_game([dead, instant], [other])
        _cast(t, soulcaller, None, branches=[[other, instant, dead], [instant, dead], [dead]])
        _resolve(t, moves(dead, Zone.HAND))
        t.run()

    def test_no_legal_target_removes_the_trigger(self):
        """With no creature card in its controller's graveyard, the Soulcaller
        still resolves, and its enters trigger, with no legal target, is
        removed from the stack (rule 603.3d)."""
        t, soulcaller = _soulcaller_game()
        t.act(0, soulcaller, then=[moves(soulcaller, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(soulcaller, Zone.BATTLEFIELD)], note="no trigger goes on the stack")
        t.run()
