"""Per-turn history the engine keeps for abilities to read: whether a player
attacked this turn (raid, rule 508.1) and whether a creature died this turn
(morbid, 700.4), plus permanents that don't untap during the untap step
(502.3).

Each is seen through a card that reads it: Searslicer Goblin's raid makes a
Goblin at its controller's end step, and Slumbering Cerberus doesn't untap in
the untap step but its morbid untaps it at an end step after a creature died.
"""

from __future__ import annotations

from cards.fdn.fdn_93.card_impl import SearslicerGoblin, SearslicerGoblinAbility1
from cards.fdn.fdn_94.card_impl import SlumberingCerberus, SlumberingCerberusAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_278.card_impl import Mountain
from test_interface import Phase, Side, Step, Zone, card, create_game

from silverquillm.table import (
    Table,
    appears,
    life,
    moves,
    off_stack,
    on_stack,
    stays_tapped,
    taps,
    untaps,
)


def test_declaring_an_attacker_records_attacked_this_turn():
    goblin = card(SearslicerGoblin)
    game = create_game(
        Side(battlefield=[goblin], library=[card(Plains)]),
        Side(library=[card(Plains)]),
        start=(Step.BEGIN_COMBAT, 0),
    )
    t = Table(game)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, goblin, then=[taps(goblin)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)  # declares no blockers
    t.pass_(0)
    t.pass_(1, then=[life(1, 18)])
    t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
    t.pass_(0)
    t.pass_(1, then=[on_stack(SearslicerGoblinAbility1, 0)], note="player 0 attacked this turn")
    t.pass_(0)
    t.pass_(1, then=[off_stack(SearslicerGoblinAbility1), appears(0)])
    # Player 0's next turn has no attack, so its end step makes no Goblin.
    t.pass_to(Step.END, 0)
    final = t.run()
    assert final.players[1].life == 18


def test_creature_dying_records_creature_died_this_turn():
    cerberus, bolt, mountain, lions = card(SlumberingCerberus, tapped=True), card(BurstLightning), card(Mountain), card(SavannahLions)
    game = create_game(
        Side(hand=[bolt], battlefield=[cerberus, mountain], library=[card(Plains)]),
        Side(battlefield=[lions], library=[card(Plains)]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, mountain, then=[taps(mountain)])
    t.act(0, bolt, choices=[lions], then=[moves(bolt, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD)])
    t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
    t.pass_(0)
    t.pass_(1, then=[on_stack(SlumberingCerberusAbility2, 0)], note="a creature died this turn")
    t.pass_(0)
    t.pass_(1, then=[off_stack(SlumberingCerberusAbility2), untaps(cerberus)])
    # Player 0's next turn: Cerberus attacks, and with nothing dying its end
    # step leaves it tapped.
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, cerberus, then=[taps(cerberus)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)  # declares no blockers
    t.pass_(0)
    t.pass_(1, then=[life(1, 16)])
    t.pass_to(Step.END, 0)
    t.run()


def test_permanent_that_does_not_untap_stays_tapped():
    stays, untaps_ = card(SlumberingCerberus, tapped=True), card(SavannahLions, tapped=True)
    game = create_game(
        Side(battlefield=[stays, untaps_], library=[card(Plains)]),
        Side(),
        start=(Step.END, 1),
    )
    t = Table(game)
    t.pass_(1)
    t.pass_(0, then=[stays_tapped(stays)], note="Cerberus doesn't untap; the Lions does")
    final = t.run()
    assert final.step is Step.UPKEEP and final.active == 0
