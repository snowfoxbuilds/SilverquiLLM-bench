"""Reference test for FDN 45 — Kiora, the Rising Tide (token identity).

Threshold — "Whenever Kiora attacks, if there are seven or more cards in your
graveyard, you may create Scion of the Deep, a legendary 8/8 blue Octopus
creature token." Kiora attacks above threshold and player 0 answers the
optional "you may" with yes. Name, colour and supertype are not visible at
the table, so the token is judged by the 8 damage it deals on the next turn.
"""

from __future__ import annotations

from cards.fdn.fdn_45.card_impl import KioraTheRisingTide, KioraTheRisingTideAbility2
from cards.fdn.fdn_280.card_impl import Forest
from test_interface import Decision, Phase, Side, Step, card, create_game, token

from silverquillm.table import Table, appears, life, off_stack, on_stack, taps


def _no_blocks(t, life_after):
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, life_after)])


class TestKioraToken:
    def test_threshold_attack_mints_an_eight_power_token(self) -> None:
        kiora = card(KioraTheRisingTide)
        game = create_game(
            Side(battlefield=[kiora], graveyard=[Forest] * 7, library=[Forest]),
            Side(library=[Forest]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, kiora, then=[taps(kiora), on_stack(KioraTheRisingTideAbility2, 0)])
        t.pass_(0, choices=[Decision.yes()])
        t.pass_(1, then=[off_stack(KioraTheRisingTideAbility2), appears(0)])
        _no_blocks(t, 17)
        t.pass_to(Phase.PRECOMBAT_MAIN, 1)
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        scion = token(1)
        t.act(0, scion, then=[taps(scion)])
        _no_blocks(t, 9)
        t.run()
