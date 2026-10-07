"""Reference test for FDN 99 — Apothecary Stomper.

A **modal ETB creature**: mode one puts two +1/+1 counters on target creature
its controller controls, mode two gains them 4 life. The counters show when
the 2/2 they land on survives Burst Lightning.
"""

from __future__ import annotations

from cards.fdn.fdn_99.card_impl import (
    ApothecaryStomper,
    ApothecaryStomperAbility2,
    ApothecaryStomperAbility3,
    ApothecaryStomperAbility4,
)
from cards.fdn.fdn_171.card_impl import DiregrafGhoul
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_249.card_impl import AdventuringGear
from engine.card import printed_class
from engine.types import Keyword, ManaCost, ManaType, Phase, Zone
from test_interface import Side, card, create_game

from table import Table, life, moves, off_stack, on_stack

_MANA = {ManaType.GREEN: 2, ManaType.COLORLESS: 4}


def _cast_stomper(choices, *, mine=(), theirs=(), branches=None):
    """Player 0 casts Apothecary Stomper, answering its mode and target from
    ``choices`` — or from ``branches``, tried in turn as the engine rejects a
    choice; player 1 holds Burst Lightning."""
    stomper, bolt = card(ApothecaryStomper), card(BurstLightning)
    game = create_game(
        Side(hand=[stomper], battlefield=list(mine), mana=_MANA),
        Side(hand=[bolt], battlefield=list(theirs), mana={ManaType.RED: 1}),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, stomper, then=[moves(stomper, Zone.STACK)])
    if branches:
        t.pass_(0, branches=branches)
    else:
        t.pass_(0, choices=choices)
    t.pass_(1, then=[moves(stomper, Zone.BATTLEFIELD), on_stack(ApothecaryStomperAbility2, 0)], note="its mode and target are chosen now")
    t.pass_(0)
    return t, stomper, bolt


def _bolt_survives(t, bolt, target):
    """Player 0 passes; player 1's Burst Lightning deals 2 to ``target``, a
    2/2 that lives only with two +1/+1 counters."""
    t.pass_(0)
    t.act(1, bolt, choices=[target], then=[moves(bolt, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD)], note="the 4/4 survives 2 damage")


class TestApothecaryStomperProperties:
    def test_static_data(self):
        card = ApothecaryStomper(owner=None)
        assert printed_class(card) is ApothecaryStomper
        assert card.mana_cost == ManaCost.parse("{4}{G}{G}")
        assert (card.base_power, card.base_toughness) == (4, 4)
        assert card.subtypes == {"Elephant"}
        assert Keyword.VIGILANCE & card.keywords


class TestApothecaryStomperModes:
    def test_mode0_puts_two_counters_on_your_creature(self):
        mine = card(DiregrafGhoul)
        t, _stomper, bolt = _cast_stomper([ApothecaryStomperAbility3, mine], mine=[mine])
        t.pass_(1, then=[off_stack(ApothecaryStomperAbility2)])
        _bolt_survives(t, bolt, mine)
        t.run()

    def test_mode1_gains_four_life(self):
        t, _stomper, _bolt = _cast_stomper([ApothecaryStomperAbility4])
        t.pass_(1, then=[off_stack(ApothecaryStomperAbility2), life(0, 24)])
        t.run()

    def test_option_set_mode0_targets_only_creatures_you_control(self):
        """Player 0 prefers the opponent's creature, then their own artifact,
        then their own creature: only the last is a legal target, the others
        either not offered or offered and rejected."""
        mine, theirs, gear = card(DiregrafGhoul), card(DiregrafGhoul), card(AdventuringGear)
        t, _stomper, bolt = _cast_stomper(
            None, mine=[mine, gear], theirs=[theirs],
            branches=[[ApothecaryStomperAbility3, theirs, gear, mine],
                      [ApothecaryStomperAbility3, gear, mine],
                      [ApothecaryStomperAbility3, mine]],
        )
        t.pass_(1, then=[off_stack(ApothecaryStomperAbility2)])
        _bolt_survives(t, bolt, mine)
        t.run()
