"""Audited tests for FDN 173 — Exsanguinate.

"Each opponent loses X life. You gain life equal to the life lost this way."
With only {B}{B} to spend, X can only be 0 (rules 107.3a, 601.2b, 601.2f).
"""

from __future__ import annotations

from cards.fdn.fdn_173.card_impl import Exsanguinate
from test_interface import Decision, ManaType, Phase, Side, Zone, card, create_game

from table import Table, moves


class TestExsanguinateXZero:
    def test_x_zero_drains_nothing(self) -> None:
        """Cast for {B}{B} with X = 0, it resolves and no life total changes."""
        spell = card(Exsanguinate)
        game = create_game(Side(hand=[spell], mana={ManaType.BLACK: 2}), Side(), start=(Phase.PRECOMBAT_MAIN, 0))
        t = Table(game)
        t.act(0, spell, choices=[Decision.number(0)], then=[moves(spell, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(spell, Zone.GRAVEYARD)])
        t.run()
