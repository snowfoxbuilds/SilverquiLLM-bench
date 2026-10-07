"""Reference test for FDN 21 — Prideful Parent (Phase F self-ETB probe).

Prideful Parent's "When this creature enters, create a 1/1 white Cat creature
token" is its own enters-trigger (rule 603.3a): casting it makes exactly one
token. That the token is a 1/1 shows on the next turn: it hits for 1, and it
trades with a 1/1 blocker.
"""

from __future__ import annotations

from cards.fdn.fdn_21.card_impl import PridefulParent, PridefulParentAbility2
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_272.card_impl import Plains
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game, token

from table import Table, appears, ceases, life, moves, off_stack, on_stack, taps


def _cast_parent(p1_battlefield=()):
    parent = card(PridefulParent)
    game = create_game(
        Side(
            hand=[parent], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 2}, library=[card(Plains)]
        ),
        Side(battlefield=list(p1_battlefield), library=[card(Plains)]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, parent, then=[moves(parent, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(parent, Zone.BATTLEFIELD), on_stack(PridefulParentAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(PridefulParentAbility2), appears(0)])
    return t


def _cat_attacks(t, *, block=None, then=()):
    t.pass_to(Step.UPKEEP, 0)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, token(1), then=[taps(token(1))])
    t.pass_(0)
    t.pass_(1)
    if block is None:
        t.pass_(1)
    else:
        t.act(1, block, scoped={block: token(1)})
    t.pass_(0)
    t.pass_(1, then=list(then))


class TestPridefulParentSelfETB:
    def test_own_entry_mints_exactly_one_cat(self) -> None:
        t = _cast_parent()
        _cat_attacks(t, then=[life(1, 19)])
        t.run()

    def test_minted_cat_has_spec_characteristics(self) -> None:
        elves = card(LlanowarElves)
        t = _cast_parent([elves])
        _cat_attacks(t, block=elves, then=[ceases(token(1)), moves(elves, Zone.GRAVEYARD)])
        t.run()
