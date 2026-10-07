"""Reference test for FDN 177 — Macabre Waltz.

"Return UP TO TWO target creature cards from your graveyard" → two optional
requirements. Castable with one or zero creature cards in the graveyard; the
engine returns distinct cards. The "then discard a card" is answered by the
caster's script as the spell resolves.
"""

from __future__ import annotations

from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_177.card_impl import MacabreWaltz
from cards.fdn.fdn_192.card_impl import BurstLightning
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Zone, card, create_game

from table import Table, moves


def _table(waltz, spare, graveyard=()):
    game = create_game(
        Side(hand=[waltz, spare], graveyard=list(graveyard), mana={ManaType.BLACK: 2}),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    return Table(game)


class TestMacabreWaltzProperties:
    def test_static_data(self):
        mw = MacabreWaltz(owner=None)
        assert printed_class(mw) is MacabreWaltz
        assert mw.mana_cost == ManaCost.parse("{1}{B}")


class TestMacabreWaltz:
    def test_castable_with_empty_graveyard(self):
        """No creature card in the graveyard: the spell still casts (both
        optional targets skipped), and the only card in hand is discarded."""
        waltz, spare = card(MacabreWaltz), card(BurstLightning)
        t = _table(waltz, spare)
        t.act(0, waltz, then=[moves(waltz, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(spare, Zone.GRAVEYARD), moves(waltz, Zone.GRAVEYARD)])
        t.run()

    def test_returns_one_creature_card(self):
        """The one creature card returns to hand, and the spare is discarded."""
        waltz, spare, corpse = card(MacabreWaltz), card(BurstLightning), card(SavannahLions)
        t = _table(waltz, spare, graveyard=[corpse])
        t.act(0, waltz, choices=[corpse], distinct=True, then=[moves(waltz, Zone.STACK)])
        t.pass_(0, choices=[spare])
        t.pass_(1, then=[moves(corpse, Zone.HAND), moves(spare, Zone.GRAVEYARD), moves(waltz, Zone.GRAVEYARD)])
        t.run()
