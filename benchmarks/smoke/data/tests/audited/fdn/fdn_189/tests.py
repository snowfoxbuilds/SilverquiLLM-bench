"""Reference test for FDN 189 — Axgard Cavalry.

Demonstrates a **targeted activated ability** (Phase D pattern 2) with a
``{T}`` cost and an until-end-of-turn keyword grant. The target creature is
chosen at activation, captured on the stack, and granted haste until end of
turn. The haste shows when a Savannah Lions cast this turn attacks.
"""

from __future__ import annotations

from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_189.card_impl import AxgardCavalry, AxgardCavalryAbility1
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game

from table import Table, life, moves, off_stack, on_stack, taps


def _table(*, battlefield=(), hand=(), mana=None):
    game = create_game(
        Side(battlefield=list(battlefield), hand=list(hand), mana=mana or {}),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    return Table(game)


def _cast(t, creature):
    t.act(0, creature, then=[moves(creature, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(creature, Zone.BATTLEFIELD)])


def _activate(t, axgard, target):
    # Named by its ability class: Axgard Cavalry is a creature too, and the
    # entry's preferences also answer the target question.
    t.act(0, AxgardCavalryAbility1, choices=[target], then=[taps(axgard), on_stack(AxgardCavalryAbility1, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(AxgardCavalryAbility1)])


def _attack_unblocked(t, attacker, life_after):
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, life_after)])


class TestAxgardCavalryProperties:
    def test_static_data(self):
        card = AxgardCavalry(owner=None)
        assert printed_class(card) is AxgardCavalry
        assert card.mana_cost == ManaCost.parse("{1}{R}")
        assert (card.base_power, card.base_toughness) == (2, 2)
        assert {"Dwarf", "Berserker"} <= card.subtypes


class TestAxgardCavalryAbility:
    def test_target_gains_haste_after_resolution(self):
        """Savannah Lions, cast this turn, attacks for 2."""
        axgard, lions = card(AxgardCavalry), card(SavannahLions)
        t = _table(battlefield=[axgard], hand=[lions], mana={ManaType.WHITE: 1})
        _cast(t, lions)
        _activate(t, axgard, lions)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, lions, then=[taps(lions)])
        _attack_unblocked(t, lions, 18)
        t.run()

    def test_tap_cost_is_paid(self):
        """Axgard Cavalry is tapped as soon as the ability is activated."""
        axgard, lions = card(AxgardCavalry), card(SavannahLions)
        t = _table(battlefield=[axgard], hand=[lions], mana={ManaType.WHITE: 1})
        _cast(t, lions)
        t.act(0, AxgardCavalryAbility1, choices=[lions], then=[taps(axgard), on_stack(AxgardCavalryAbility1, 0)])
        t.run()

    def test_target_captured_on_stack(self):
        """Of two Lions cast this turn, only the one targeted can attack."""
        axgard, first, second = card(AxgardCavalry), card(SavannahLions), card(SavannahLions)
        t = _table(battlefield=[axgard], hand=[first, second], mana={ManaType.WHITE: 2})
        _cast(t, first)
        _cast(t, second)
        _activate(t, axgard, second)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act_illegal(0, first, note="the untargeted Lions is still summoning sick")
        t.act(0, second, then=[taps(second)])
        _attack_unblocked(t, second, 18)
        t.run()

    def test_tapped_source_rejected_before_cost(self):
        """Legality invariant: a ``{T}`` ability cannot be activated when the
        source is already tapped."""
        axgard = card(AxgardCavalry, tapped=True)
        t = _table(battlefield=[axgard])
        t.act_illegal(0, AxgardCavalryAbility1, choices=[axgard])
        t.run()

    def test_summoning_sick_source_rejected_before_cost(self):
        """Legality invariant: a summoning-sick source without haste cannot pay
        the ``{T}`` cost (rule 302.6): Axgard Cavalry cast this turn stays
        untapped."""
        axgard = card(AxgardCavalry)
        t = _table(hand=[axgard], mana={ManaType.RED: 1, ManaType.COLORLESS: 1})
        _cast(t, axgard)
        t.act_illegal(0, AxgardCavalryAbility1, choices=[axgard])
        t.run()
