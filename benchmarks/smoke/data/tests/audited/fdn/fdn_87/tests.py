"""Reference tests for FDN 87 — Goblin Boarders.

Raid — "This creature enters with a +1/+1 counter on it if you attacked this
turn." The Raid condition is read from game state as the creature enters (rule
614.1c), so the counter is on it *as* it enters when the controller attacked
this turn — and no counter is added when they did not.

The counter shows in play: a 4/3 Boarders survives Burst Lightning's 2
damage and attacks for 4, where a 3/2 dies to it.
"""

from __future__ import annotations

from cards.fdn.fdn_87.card_impl import GoblinBoarders
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_278.card_impl import Mountain
from engine.card import printed_class
from engine.types import ManaCost, ManaType
from test_interface import Phase, Side, Step, Zone, card, create_game

from silverquillm.table import Table, life, moves, taps


class TestGoblinBoardersProperties:
    def test_name_and_cost(self) -> None:
        card = GoblinBoarders(owner=None)
        assert printed_class(card) is GoblinBoarders
        assert card.mana_cost == ManaCost.parse("{2}{R}")
        assert card.base_power == 3
        assert card.base_toughness == 2


def _attack_then_cast_boarders(**sides):
    """Player 0's Savannah Lions attacks unblocked, then player 0 casts Goblin
    Boarders from three Mountains in their postcombat main phase."""
    boarders, lions = card(GoblinBoarders), card(SavannahLions)
    mountains = [card(Mountain) for _ in range(3)]
    game = create_game(
        Side(hand=[boarders], battlefield=[lions, *mountains], library=sides.get("library", [])),
        sides.get("opponent", Side()),
        start=(Step.BEGIN_COMBAT, 0),
    )
    t = Table(game)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, lions, then=[taps(lions)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, 18)])
    t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
    for mountain in mountains:
        t.act(0, mountain, then=[taps(mountain)])
    t.act(0, boarders, then=[moves(boarders, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(boarders, Zone.BATTLEFIELD)])
    return t, boarders, lions


def _opponent_bolts(t, boarders, bolt, mountain=None, *, dies):
    """Player 0 passes, and player 1 casts Burst Lightning at the Boarders."""
    t.pass_(0)
    if mountain is not None:
        t.act(1, mountain, then=[taps(mountain)])
    t.act(1, bolt, choices=[boarders], then=[moves(bolt, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD), *([moves(boarders, Zone.GRAVEYARD)] if dies else [])])


class TestGoblinBoardersRaid:
    def test_enters_buffed_when_attacked_this_turn(self) -> None:
        bolt, mountain = card(BurstLightning), card(Mountain)
        t, boarders, _lions = _attack_then_cast_boarders(opponent=Side(hand=[bolt], battlefield=[mountain]))
        _opponent_bolts(t, boarders, bolt, mountain, dies=False)
        t.run()

    def test_enters_plain_when_not_attacked(self) -> None:
        boarders, bolt = card(GoblinBoarders), card(BurstLightning)
        game = create_game(
            Side(hand=[boarders], mana={ManaType.RED: 1, ManaType.COLORLESS: 2}),
            Side(hand=[bolt], mana={ManaType.RED: 1}),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, boarders, then=[moves(boarders, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(boarders, Zone.BATTLEFIELD)])
        _opponent_bolts(t, boarders, bolt, dies=True)
        t.run()

    def test_reads_controller_attacked_flag(self) -> None:
        """The Boarders that entered after its controller attacked attacks
        for 4 on their next turn."""
        t, boarders, _lions = _attack_then_cast_boarders(
            library=[card(Mountain)], opponent=Side(library=[card(Mountain)])
        )
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, boarders, then=[taps(boarders)])
        t.pass_(0)
        t.pass_(1)
        t.pass_(1)
        t.pass_(0)
        t.pass_(1, then=[life(1, 14)], note="the Boarders deals 4")
        t.run()
