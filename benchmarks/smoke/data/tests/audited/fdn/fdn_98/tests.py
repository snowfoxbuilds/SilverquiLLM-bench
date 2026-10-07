"""Reference test for FDN 98 — Ambush Wolf.

Exemplar for an **"up to one target" ETB**: the enters ability exiles up to one
target card from a graveyard. The single optional requirement is declinable —
an empty graveyard set casts the creature with zero targets rather than making
it uncastable.
"""

from __future__ import annotations

from cards.fdn.fdn_98.card_impl import AmbushWolf, AmbushWolfAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_227.card_impl import LlanowarElves
from engine.card import printed_class
from engine.types import Keyword, ManaCost, ManaType
from test_interface import Phase, Side, Zone, card, create_game

from table import Table, moves, off_stack, on_stack

_MANA = {ManaType.GREEN: 1, ManaType.COLORLESS: 2}


def _cast_wolf(choices, *, mine=(), theirs=(), fallback=None):
    """Player 0 casts Ambush Wolf; its enters trigger takes its target from
    ``choices`` — or ``fallback``, once the engine has rejected one."""
    wolf = card(AmbushWolf)
    game = create_game(
        Side(hand=[wolf], battlefield=list(mine), mana=_MANA),
        Side(graveyard=list(theirs)),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, wolf, then=[moves(wolf, Zone.STACK)])
    if fallback is None:
        t.pass_(0, choices=choices)
    else:
        t.pass_(0, branches=[list(choices), list(fallback)])
    t.pass_(1, then=[moves(wolf, Zone.BATTLEFIELD), on_stack(AmbushWolfAbility2, 0)])
    t.pass_(0)
    return t, wolf


class TestAmbushWolfProperties:
    def test_static_data(self):
        card = AmbushWolf(owner=None)
        assert printed_class(card) is AmbushWolf
        assert card.mana_cost == ManaCost.parse("{2}{G}")
        assert (card.base_power, card.base_toughness) == (4, 2)
        assert card.subtypes == {"Wolf"}
        assert Keyword.FLASH & card.keywords


class TestAmbushWolfETB:
    def test_exiles_targeted_graveyard_card(self):
        victim = card(SavannahLions)
        t, _wolf = _cast_wolf([victim], theirs=[victim])
        t.pass_(1, then=[off_stack(AmbushWolfAbility2), moves(victim, Zone.EXILE)],
                note="exiled from the opponent's graveyard to its owner's exile")
        t.run()

    def test_castable_with_zero_targets_when_no_graveyard_card(self):
        """Option-set invariant: 'up to one' declines cleanly with an empty
        candidate set — the Wolf still enters."""
        t, _wolf = _cast_wolf([])
        t.pass_(1, then=[off_stack(AmbushWolfAbility2)])
        t.run()

    def test_only_graveyard_cards_can_be_exiled(self):
        """Player 0 prefers their own creature on the battlefield, which is not
        a legal target — not offered, or offered and rejected — then the card
        in the opponent's graveyard."""
        on_bf, in_gy = card(LlanowarElves), card(SavannahLions)
        t, _wolf = _cast_wolf([on_bf, in_gy], mine=[on_bf], theirs=[in_gy], fallback=[in_gy])
        t.pass_(1, then=[off_stack(AmbushWolfAbility2), moves(in_gy, Zone.EXILE)])
        t.run()
