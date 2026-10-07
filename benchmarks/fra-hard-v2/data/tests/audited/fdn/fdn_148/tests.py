"""Reference test for FDN 148 — Stroke of Midnight (Phase H token minter).

"Destroy target nonland permanent. Its controller creates a 1/1 white Human
creature token." The mint fires from the instant's ``on_resolve``, so casting
it at a legal target drives the real path. Player 0 destroys player 1's
creature, player 1 gets the token, and on player 1's turn the token attacks
for 1.
"""
from __future__ import annotations

from cards.fdn.fdn_148.card_impl import StrokeOfMidnight
from cards.fdn.fdn_191.card_impl import BrazenScourge
from cards.fdn.fdn_272.card_impl import Plains
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game, token

from table import Table, appears, life, moves, taps


class TestStrokeOfMidnightMint:
    def test_on_resolve_mints_11_white_human_token(self) -> None:
        stroke, victim = card(StrokeOfMidnight), card(BrazenScourge)
        game = create_game(
            Side(hand=[stroke], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 2}),
            Side(battlefield=[victim], library=[card(Plains)]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, stroke, choices=[victim], then=[moves(stroke, Zone.STACK)])
        t.pass_(0)
        t.pass_(
            1,
            then=[moves(stroke, Zone.GRAVEYARD), moves(victim, Zone.GRAVEYARD), appears(1)],
            note="the destroyed creature's controller gets the token",
        )
        t.pass_to(Step.DECLARE_ATTACKERS, 1)
        human = token(1)
        t.act(1, human, then=[taps(human)])
        t.pass_(1)
        t.pass_(0)
        t.pass_(0, note="no block")
        t.pass_(1)
        t.pass_(0, then=[life(0, 19)], note="the token has 1 power")
        t.run()
