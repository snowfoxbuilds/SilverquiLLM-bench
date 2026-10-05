"""Audited tests for FDN 88 — Goblin Negotiation.

"Goblin Negotiation deals X damage to target creature. Create a number of 1/1
red Goblin creature tokens equal to the amount of excess damage dealt to that
creature this way." X is chosen and paid while casting (rules 107.3a, 601.2b,
601.2f).
"""

from __future__ import annotations

from cards.fdn.fdn_82.card_impl import CourageousGoblin
from cards.fdn.fdn_88.card_impl import GoblinNegotiation
from engine.decisions import Decision
from engine.types import ManaType
from test_interface import Phase, Side, Zone, card, create_game

from silverquillm.table import Table, appears, moves


class TestGoblinNegotiationMint:
    def test_excess_damage_mints_11_red_goblin_tokens(self) -> None:
        """X = 4 dealt to a 2/2: 2 lethal, 2 excess, so two Goblin tokens; the
        six mana in the pool pays exactly {4}{R}{R}, so a fifth X is not
        affordable."""
        spell, target = card(GoblinNegotiation), card(CourageousGoblin)
        game = create_game(
            Side(hand=[spell], mana={ManaType.RED: 2, ManaType.COLORLESS: 4}),
            Side(battlefield=[target]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, spell, choices=[Decision.number(4), target], then=[moves(spell, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(spell, Zone.GRAVEYARD), moves(target, Zone.GRAVEYARD), appears(0), appears(0)])
        t.run()
