"""Audited tests for FDN 221 — Genesis Wave.

"Reveal the top X cards of your library. You may put any number of permanent
cards with mana value X or less from among them onto the battlefield. Then put
all cards revealed this way that weren't put onto the battlefield into your
graveyard." With only {G}{G}{G} to spend, X can only be 0 (rules 107.3a,
601.2b, 601.2f).
"""

from __future__ import annotations

from cards.fdn.fdn_221.card_impl import GenesisWave
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_280.card_impl import Forest
from test_interface import Decision, ManaType, Phase, Side, Zone, card, create_game

from table import Table, moves


class TestGenesisWaveXZero:
    def test_x_zero_reveals_nothing(self) -> None:
        """Cast for {G}{G}{G} with X = 0, it resolves and the library is left
        alone: neither a land nor a creature on top moves."""
        spell = card(GenesisWave)
        game = create_game(
            Side(hand=[spell], mana={ManaType.GREEN: 3}, library=[card(Forest), card(LlanowarElves)]),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, spell, choices=[Decision.number(0)], then=[moves(spell, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(spell, Zone.GRAVEYARD)])
        t.run()
