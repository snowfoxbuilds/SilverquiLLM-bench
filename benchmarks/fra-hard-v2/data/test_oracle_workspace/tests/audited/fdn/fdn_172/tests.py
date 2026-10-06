"""Audited tests for FDN 172 — Eaten Alive.

"As an additional cost to cast this spell, sacrifice a creature or pay
{3}{B}. Exile target creature or planeswalker." The sacrifice shows as the
creature going to its owner's graveyard while the spell is cast; the mana
alternative shows in what the caster can and cannot afford; with neither
alternative payable the spell cannot be cast.
"""

from __future__ import annotations

from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_172.card_impl import EatenAlive
from cards.fdn.fdn_272.card_impl import Plains
from engine.card import Sorcery, printed_class
from engine.types import ManaCost, ManaType
from test_interface import Phase, Side, Zone, card, create_game

from silverquillm.table import Table, moves

MAIN = (Phase.PRECOMBAT_MAIN, 0)


class TestEatenAliveProperties:
    def test_static_data(self):
        eaten = EatenAlive(owner=None)
        assert printed_class(eaten) is EatenAlive
        assert eaten.mana_cost == ManaCost.parse("{B}")
        assert isinstance(eaten, Sorcery)


def _resolve(t, eaten, target):
    t.pass_(0)
    t.pass_(1, then=[moves(eaten, Zone.GRAVEYARD), moves(target, Zone.EXILE)])


class TestEatenAliveAdditionalCost:
    def test_sacrificing_a_creature_pays_the_additional_cost(self):
        """With only {B} in the pool, the caster sacrifices their creature and
        the target is exiled."""
        eaten, mine, theirs = card(EatenAlive), card(SavannahLions), card(SavannahLions)
        t = Table(create_game(
            Side(hand=[eaten], battlefield=[mine], library=[card(Plains)], mana={ManaType.BLACK: 1}),
            Side(battlefield=[theirs], library=[card(Plains)]),
            start=MAIN,
        ))
        t.act(0, eaten, choices=[theirs], then=[moves(eaten, Zone.STACK), moves(mine, Zone.GRAVEYARD)])
        _resolve(t, eaten, theirs)
        t.run()

    def test_paying_three_and_black_pays_the_additional_cost(self):
        """With no creature to sacrifice, {3}{B} on top of {B} casts it."""
        eaten, theirs = card(EatenAlive), card(SavannahLions)
        t = Table(create_game(
            Side(hand=[eaten], library=[card(Plains)], mana={ManaType.BLACK: 2, ManaType.COLORLESS: 3}),
            Side(battlefield=[theirs], library=[card(Plains)]),
            start=MAIN,
        ))
        t.act(0, eaten, choices=[theirs], then=[moves(eaten, Zone.STACK)])
        _resolve(t, eaten, theirs)
        t.run()

    def test_neither_alternative_payable_cannot_cast(self):
        """No creature to sacrifice and one mana short of {3}{B}{B}: the spell
        cannot be cast, though {B} alone pays its mana cost."""
        eaten, theirs = card(EatenAlive), card(SavannahLions)
        t = Table(create_game(
            Side(hand=[eaten], library=[card(Plains)], mana={ManaType.BLACK: 2, ManaType.COLORLESS: 2}),
            Side(battlefield=[theirs], library=[card(Plains)]),
            start=MAIN,
        ))
        t.act_illegal(0, eaten, choices=[theirs])
        t.run()

    def test_the_sacrificed_creature_may_be_the_target(self):
        """Sacrificing the creature it targets is legal; with its target gone
        the spell does nothing and goes to the graveyard (rule 608.2b)."""
        eaten, mine = card(EatenAlive), card(SavannahLions)
        t = Table(create_game(
            Side(hand=[eaten], battlefield=[mine], library=[card(Plains)], mana={ManaType.BLACK: 1}),
            Side(library=[card(Plains)]),
            start=MAIN,
        ))
        t.act(0, eaten, choices=[mine], then=[moves(eaten, Zone.STACK), moves(mine, Zone.GRAVEYARD)])
        t.pass_(0)
        t.pass_(1, then=[moves(eaten, Zone.GRAVEYARD)])
        t.run()
