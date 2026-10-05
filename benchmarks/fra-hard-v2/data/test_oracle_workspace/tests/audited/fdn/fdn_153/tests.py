"""Regression tests for FDN 153 — Essence Scatter.

"Counter target creature spell." Player 1 casts spells on their turn and
player 0 answers with Essence Scatter. Only creature spells are targets — a
triggered ability whose source is a creature is not a creature spell — and a
countered card goes to its owner's graveyard. A target that already left the
stack makes the spell do nothing (rule 608.2b), which is guarded by the
Known-Best platform checks: recasting a creature card from the graveyard
takes Zul Ashur, whose {T} cost Known-Best does not pay (#169).
"""

from __future__ import annotations

from cards.fdn.fdn_9.card_impl import DazzlingAngel, DazzlingAngelAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_153.card_impl import EssenceScatter
from cards.fdn.fdn_192.card_impl import BurstLightning
from engine.card import Instant
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Zone, card, create_game, player

from silverquillm.table import Table, life, moves, off_stack, on_stack


def _table(p0: Side, p1: Side) -> Table:
    """Player 1's main phase; player 0 holds Essence Scatter."""
    return Table(create_game(p0, p1, start=(Phase.PRECOMBAT_MAIN, 1)))


class TestEssenceScatterProperties:
    def test_is_instant(self) -> None:
        assert isinstance(EssenceScatter(owner=None), Instant)

    def test_mana_cost(self) -> None:
        assert EssenceScatter(owner=None).mana_cost == ManaCost.parse("{1}{U}")



class TestEssenceScatterCounters:
    def test_countered_creature_spell_to_owner_graveyard(self) -> None:
        scatter, lions = card(EssenceScatter), card(SavannahLions)
        t = _table(Side(hand=[scatter], mana={ManaType.BLUE: 2}), Side(hand=[lions], mana={ManaType.WHITE: 1}))
        t.act(1, lions, then=[moves(lions, Zone.STACK)])
        t.pass_(1)
        t.act(0, scatter, choices=[lions], then=[moves(scatter, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(lions, Zone.GRAVEYARD), moves(scatter, Zone.GRAVEYARD)])
        t.run()

    def test_noncreature_spell_is_not_targetable(self) -> None:
        """With only an instant on the stack, Essence Scatter has no legal
        target and cannot be cast."""
        scatter, bolt = card(EssenceScatter), card(BurstLightning)
        t = _table(Side(hand=[scatter], mana={ManaType.BLUE: 2}), Side(hand=[bolt], mana={ManaType.RED: 1}))
        t.act(1, bolt, choices=[player(0)], then=[moves(bolt, Zone.STACK)])
        t.pass_(1)
        t.act_illegal(0, scatter, note="an instant is not a creature spell")
        t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD), life(0, 18)])
        t.run()

    def test_trigger_sourced_by_creature_is_not_a_creature_spell(self) -> None:
        """Dazzling Angel's trigger has a creature as its source, but it is
        not a creature spell: Essence Scatter cannot target it."""
        scatter, lions = card(EssenceScatter), card(SavannahLions)
        t = _table(
            Side(hand=[scatter], mana={ManaType.BLUE: 2}),
            Side(hand=[lions], battlefield=[DazzlingAngel], mana={ManaType.WHITE: 1}),
        )
        t.act(1, lions, then=[moves(lions, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(lions, Zone.BATTLEFIELD), on_stack(DazzlingAngelAbility2, 1)])
        t.pass_(1)
        t.act_illegal(0, scatter, note="a triggered ability is not a creature spell")
        t.pass_(0, then=[off_stack(DazzlingAngelAbility2), life(1, 21)])
        t.run()
