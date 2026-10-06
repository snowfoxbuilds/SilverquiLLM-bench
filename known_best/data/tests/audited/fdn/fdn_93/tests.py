"""Audited tests for FDN 93 — Searslicer Goblin.

"Raid — At the beginning of your end step, if you attacked this turn, create a
1/1 red Goblin creature token." Each test plays the turn: a real attack
declaration, or none, then the end step (rules 508.1, 207.2c); the token's
power shows when it attacks the next turn.
"""

from __future__ import annotations

from cards.fdn.fdn_93.card_impl import SearslicerGoblin, SearslicerGoblinAbility1
from cards.fdn.fdn_272.card_impl import Plains
from test_interface import Phase, Side, Step, card, create_game, token

from silverquillm.table import Table, appears, life, off_stack, on_stack, taps


def _searslicer_in_play():
    goblin = card(SearslicerGoblin)
    game = create_game(
        Side(battlefield=[goblin], library=[card(Plains)]),
        Side(library=[card(Plains)]),
        start=(Step.BEGIN_COMBAT, 0),
    )
    return Table(game), goblin


class TestSearslicerGoblinMint:
    def test_raid_end_step_mints_11_red_goblin_token(self) -> None:
        t, goblin = _searslicer_in_play()
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, goblin, then=[taps(goblin)])
        t.pass_(0)
        t.pass_(1)
        t.pass_(1)
        t.pass_(0)
        t.pass_(1, then=[life(1, 18)])
        t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
        t.pass_(0)
        t.pass_(1, then=[on_stack(SearslicerGoblinAbility1, 0)], note="player 0 attacked this turn")
        t.pass_(0)
        t.pass_(1, then=[off_stack(SearslicerGoblinAbility1), appears(0)], note="a Goblin token")
        # Next turn the token attacks alone, unblocked: a 1-power creature.
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, token(1), then=[taps(token(1))])
        t.pass_(0)
        t.pass_(1)
        t.pass_(1)
        t.pass_(0)
        t.pass_(1, then=[life(1, 17)], note="the Goblin token deals 1")
        t.run()

    def test_no_attack_means_no_goblin(self) -> None:
        t, _goblin = _searslicer_in_play()
        t.pass_to(Step.END, 0)
        t.pass_(0)
        t.pass_(1, note="no Goblin: the end step ends with nothing on the stack")
        t.run()
