"""Sylvan Scavenging resolves its controller's end-step token choice.

With a power-4 creature in play, choosing the token mode makes a 3/3 Raccoon,
which shows its size by attacking on the next turn.
"""

from cards.fdn.fdn_113.card_impl import (
    SylvanScavenging,
    SylvanScavengingAbility1,
    SylvanScavengingAbility3,
)
from cards.fdn.fdn_147.card_impl import SerraAngel
from cards.fdn.fdn_280.card_impl import Forest
from test_interface import Decision, Phase, Side, Step, create_game, token

from silverquillm.table import Table, appears, life, off_stack, on_stack, taps

TOKEN_MODE = Decision.mode(printed=SylvanScavengingAbility3)


def test_end_step_token_mode_mints_raccoon():
    game = create_game(
        Side(battlefield=[SerraAngel, SylvanScavenging], library=[Forest]),
        Side(library=[Forest]),
        start=(Phase.POSTCOMBAT_MAIN, 0),
    )
    t = Table(game)
    # The mode may be asked as the trigger goes on the stack or as it resolves.
    t.pass_(0, choices=[TOKEN_MODE])
    t.pass_(1, then=[on_stack(SylvanScavengingAbility1, 0)])
    t.pass_(0, choices=[TOKEN_MODE])
    t.pass_(1, then=[off_stack(SylvanScavengingAbility1), appears(0)], note="a Raccoon token")
    # Player 0's next turn: the Raccoon attacks alone for 3.
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    raccoon = token(1)
    t.act(0, raccoon, then=[taps(raccoon)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, 17)], note="the Raccoon is a 3/3")
    t.run()
