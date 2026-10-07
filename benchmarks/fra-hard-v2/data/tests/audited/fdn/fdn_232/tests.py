"""Audited tests for FDN 232 — Scavenging Ooze.

"{G}: Exile target card from a graveyard. If it was a creature card, put a
+1/+1 counter on this creature and you gain 1 life." The card is chosen at
activation and revalidated at resolution: a target that leaves the graveyard
is not replaced, and a card that reaches a graveyard later cannot become the
target. The +1/+1 counter shows when the Ooze attacks for 3.
"""

from __future__ import annotations

from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_232.card_impl import ScavengingOoze, ScavengingOozeAbility1
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game

from table import Table, life, moves, off_stack, on_stack, taps


def _table(graveyard, *, mine=(), theirs=(), their_mana=None, their_hand=()):
    ooze = card(ScavengingOoze)
    game = create_game(
        Side(battlefield=[ooze, *mine], mana={ManaType.GREEN: 2}),
        Side(graveyard=list(graveyard), battlefield=list(theirs), hand=list(their_hand), mana=their_mana or {}),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    return Table(game), ooze


def _activate(t, target):
    t.act(0, ScavengingOozeAbility1, choices=[target], then=[on_stack(ScavengingOozeAbility1, 0)])


def _resolve(t, *, then=()):
    t.pass_(0)
    t.pass_(1, then=[off_stack(ScavengingOozeAbility1), *then])


def _attack_unblocked(t, ooze, their_life):
    """The Ooze attacks alone, unblocked, and player 1 goes to ``their_life``."""
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, ooze, then=[taps(ooze)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, their_life)])


class TestScavengingOozeProperties:
    def test_static_data(self):
        ooze = ScavengingOoze(owner=None)
        assert printed_class(ooze) is ScavengingOoze
        assert ooze.mana_cost == ManaCost.parse("{1}{G}")
        assert (ooze.base_power, ooze.base_toughness) == (2, 2)


class TestScavengingOozeAbility:
    def test_target_fixed_at_activation_on_stack(self):
        """Of two creature cards, the one chosen at activation is exiled."""
        target, other = card(SavannahLions), card(SavannahLions)
        t, _ooze = _table([other, target])
        _activate(t, target)
        _resolve(t, then=[moves(target, Zone.EXILE), life(0, 21)])
        t.run()

    def test_no_graveyard_card_rejects_before_cost(self):
        t, _ooze = _table([])
        t.act_illegal(0, ScavengingOozeAbility1, note="no card in any graveyard to target")
        t.pass_(0)
        t.run()

    def test_creature_card_target_gives_reward(self):
        target = card(SavannahLions)
        t, ooze = _table([target])
        _activate(t, target)
        _resolve(t, then=[moves(target, Zone.EXILE), life(0, 21)])
        _attack_unblocked(t, ooze, 17)
        t.run()

    def test_noncreature_card_target_no_reward(self):
        target = card(BurstLightning)
        t, ooze = _table([target])
        _activate(t, target)
        _resolve(t, then=[moves(target, Zone.EXILE)])
        _attack_unblocked(t, ooze, 18)
        t.run()

    def test_target_removed_in_response_not_reselected(self):
        """Player 1's own Scavenging Ooze exiles the targeted card in response;
        player 0's ability does not choose the other card and gives no reward."""
        target, other, their_ooze = card(SavannahLions), card(SavannahLions), card(ScavengingOoze)
        t, ooze = _table([target, other], theirs=[their_ooze], their_mana={ManaType.GREEN: 1})
        _activate(t, target)
        t.pass_(0)
        t.act(1, ScavengingOozeAbility1, choices=[target], then=[on_stack(ScavengingOozeAbility1, 1)])
        t.pass_(1)
        t.pass_(0, then=[off_stack(ScavengingOozeAbility1), moves(target, Zone.EXILE), life(1, 21)])
        _resolve(t)
        _attack_unblocked(t, ooze, 19)
        t.run()

    def test_card_added_after_activation_not_selectable(self):
        """Player 1 kills player 0's Llanowar Elves in response; the Elves
        card reaches the graveyard after the target was fixed and stays there."""
        target, elves, bolt = card(SavannahLions), card(LlanowarElves), card(BurstLightning)
        t, _ooze = _table([target], mine=[elves], their_hand=[bolt], their_mana={ManaType.RED: 1})
        _activate(t, target)
        t.pass_(0)
        t.act(1, bolt, choices=[elves], then=[moves(bolt, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD), moves(elves, Zone.GRAVEYARD)])
        _resolve(t, then=[moves(target, Zone.EXILE), life(0, 21)])
        t.run()
