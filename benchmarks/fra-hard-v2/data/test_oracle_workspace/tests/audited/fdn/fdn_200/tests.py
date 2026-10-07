"""Audited tests for FDN 200 — Goblin Surprise.

"Choose one — • Creatures you control get +2/+0 until end of turn.
• Create two 1/1 red Goblin creature tokens."

The mode is chosen while casting (rule 601.2b, 700.2a), so each test casts the
spell choosing its mode and watches what the chosen mode does in play.
"""

from __future__ import annotations

from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_200.card_impl import (
    GoblinSurprise,
    GoblinSurpriseAbility2,
    GoblinSurpriseAbility3,
)
from cards.fdn.fdn_272.card_impl import Plains
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game, token

from silverquillm.table import Table, appears, ceases, life, moves, taps


def _cast(t, surprise, mode, *, then=()):
    t.act(0, surprise, choices=[mode], then=[moves(surprise, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(surprise, Zone.GRAVEYARD), *then])


def _attack_unblocked(t, seat, attacker, *, then=()):
    """``seat`` attacks with ``attacker`` alone and nobody blocks."""
    t.pass_to(Step.DECLARE_ATTACKERS, seat)
    t.act(seat, attacker, then=[taps(attacker)])
    t.pass_(seat)
    t.pass_(1 - seat)
    t.pass_(1 - seat)
    t.pass_(seat)
    t.pass_(1 - seat, then=list(then))


class TestGoblinSurpriseMint:
    def test_token_mode_mints_two_11_red_goblin_tokens(self) -> None:
        surprise, lions = card(GoblinSurprise), card(SavannahLions)
        game = create_game(
            Side(hand=[surprise], mana={ManaType.RED: 3}),
            Side(battlefield=[lions], library=[Plains]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _cast(t, surprise, GoblinSurpriseAbility3, then=[appears(0), appears(0)])
        # Player 1's 2/1 Lions attacks; a Goblin blocks it and they trade, so
        # the token deals at least 1 damage and has toughness at most 2.
        t.pass_to(Step.DECLARE_ATTACKERS, 1)
        t.act(1, lions, then=[taps(lions)])
        t.pass_(1)
        t.pass_(0)
        t.act(0, token(1), scoped={token(1): lions})
        t.pass_(1)
        t.pass_(0, then=[ceases(token(1)), moves(lions, Zone.GRAVEYARD)])
        t.run()


class TestGoblinSurprisePump:
    def test_pump_mode_gives_creatures_you_control_plus_two_until_end_of_turn(self) -> None:
        surprise, mine, theirs = card(GoblinSurprise), card(SavannahLions), card(SavannahLions)
        game = create_game(
            Side(hand=[surprise], battlefield=[mine], library=[Plains], mana={ManaType.RED: 3}),
            Side(battlefield=[theirs], library=[Plains]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        _cast(t, surprise, GoblinSurpriseAbility2)
        _attack_unblocked(t, 0, mine, then=[life(1, 16)])
        # Their Lions never got +2/+0, and ours loses it at end of turn.
        _attack_unblocked(t, 1, theirs, then=[life(0, 18)])
        _attack_unblocked(t, 0, mine, then=[life(1, 14)])
        t.run()
