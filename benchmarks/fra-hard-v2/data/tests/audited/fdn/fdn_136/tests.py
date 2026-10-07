"""Reference test for FDN 136 — Angel of Finality.

"When this creature enters, exile target player's graveyard." The enters
ability is a triggered ability whose target player is chosen as it goes on
the stack (rule 603.3d).
"""

from __future__ import annotations

from cards.fdn.fdn_136.card_impl import AngelOfFinality, AngelOfFinalityAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_280.card_impl import Forest
from engine.card import printed_class
from engine.types import Keyword, ManaCost
from test_interface import ManaType, Phase, Side, Zone, card, create_game, player

from silverquillm.table import Table, moves, off_stack, on_stack


def _angel_exiles(targets, exiled, *, mine=None, theirs=None, branches=None):
    """Player 0 casts Angel of Finality; its trigger targets one of
    ``targets`` — or answers from ``branches``, tried in turn as the engine
    rejects a choice — and exiles ``exiled``."""
    angel = card(AngelOfFinality)
    mine = mine or Side()
    game = create_game(
        Side(hand=[angel], graveyard=mine.graveyard, mana={ManaType.WHITE: 4}),
        theirs or Side(),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, angel, then=[moves(angel, Zone.STACK)])
    if branches:
        t.pass_(0, branches=branches)
    else:
        t.pass_(0, choices=list(targets))
    t.pass_(1, then=[moves(angel, Zone.BATTLEFIELD), on_stack(AngelOfFinalityAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(AngelOfFinalityAbility2), *[moves(c, Zone.EXILE) for c in exiled]])
    t.run()


class TestAngelOfFinalityProperties:
    def test_static_data(self):
        angel = AngelOfFinality(owner=None)
        assert printed_class(angel) is AngelOfFinality
        assert angel.mana_cost == ManaCost.parse("{3}{W}")
        assert (angel.base_power, angel.base_toughness) == (3, 4)
        assert "Angel" in angel.subtypes
        assert Keyword.FLYING in angel.keywords


class TestAngelOfFinalityETB:
    def test_exiles_target_players_graveyard(self):
        gy = [card(SavannahLions), card(Forest), card(Forest)]
        _angel_exiles([player(1)], gy, theirs=Side(graveyard=gy))

    def test_can_target_own_graveyard(self):
        mine = [card(SavannahLions), card(Forest)]
        _angel_exiles([player(0)], mine, mine=Side(graveyard=mine))

    def test_target_query_offers_only_players(self):
        """Player 0 would rather target the opponent's Savannah Lions, or a card
        in their graveyard, but only a player is a legal target: each is either
        not offered or offered and rejected, and the trigger targets player 1."""
        lions, dead = card(SavannahLions), card(Forest)
        _angel_exiles(None, [dead], theirs=Side(battlefield=[lions], graveyard=[dead]),
                      branches=[[lions, dead, player(1)], [dead, player(1)], [player(1)]])
