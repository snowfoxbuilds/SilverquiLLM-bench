"""Reference test for FDN 67 — Revenge of the Rats.

The sorcery makes a tapped 1/1 Rat token for each creature card in its
caster's graveyard: the tokens show tapped on the battlefield, one per
creature card, and none when the graveyard holds no creature card.
"""

from __future__ import annotations

from cards.fdn.fdn_67.card_impl import RevengeOfTheRats
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_191.card_impl import BrazenScourge
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_227.card_impl import LlanowarElves
from engine.card import printed_class
from engine.types import CardType, ManaCost, ManaType
from test_interface import Phase, Side, Zone, card, create_game, token

from silverquillm.table import Table, appears, ceases, moves, taps


def _cast_revenge(graveyard, hand=()):
    """Player 0 casts Revenge of the Rats with ``graveyard`` in their graveyard;
    both players pass, so it resolves."""
    revenge = card(RevengeOfTheRats)
    game = create_game(
        Side(hand=[revenge, *hand], graveyard=graveyard, mana={ManaType.BLACK: 4, ManaType.RED: 1}),
        Side(),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, revenge, then=[moves(revenge, Zone.STACK)])
    t.pass_(0)
    return t, revenge


class TestRevengeOfTheRatsProperties:
    def test_static_data(self):
        c = RevengeOfTheRats(owner=None)
        assert printed_class(c) is RevengeOfTheRats
        assert c.mana_cost == ManaCost.parse("{2}{B}{B}")
        assert CardType.SORCERY in c.card_types


class TestRevengeOfTheRatsResolve:
    def test_creates_one_tapped_rat_per_creature_in_graveyard(self):
        t, revenge = _cast_revenge([card(SavannahLions), card(LlanowarElves), card(BrazenScourge)])
        t.pass_(
            1,
            then=[
                moves(revenge, Zone.GRAVEYARD),
                appears(0), appears(0), appears(0),
                taps(token(1)), taps(token(2)), taps(token(3)),
            ],
            note="three creature cards make three tapped Rats",
        )
        t.run()

    def test_minted_rat_has_spec_characteristics(self):
        """A Rat is a tapped creature token: it is on the battlefield tapped,
        and as a creature it dies to Burst Lightning's 2 damage."""
        bolt = card(BurstLightning)
        t, revenge = _cast_revenge([card(SavannahLions)], hand=[bolt])
        t.pass_(1, then=[moves(revenge, Zone.GRAVEYARD), appears(0), taps(token(1))])
        t.act(0, bolt, choices=[token(1)], then=[moves(bolt, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), ceases(token(1))],
                note="the token dies")
        t.run()

    def test_no_creatures_in_graveyard_makes_no_rats(self):
        t, revenge = _cast_revenge([card(BurstLightning)])
        t.pass_(1, then=[moves(revenge, Zone.GRAVEYARD)], note="a noncreature card makes no Rat")
        t.run()
