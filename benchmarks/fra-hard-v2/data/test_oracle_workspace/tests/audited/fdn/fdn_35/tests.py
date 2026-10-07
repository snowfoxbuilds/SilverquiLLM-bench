"""Drake Hatcher earns counters through combat and pays them through activation.

Its incubation counters show in what it can activate: three are needed for a
Drake, so after dealing 3 combat damage it makes exactly one, and after dealing
2 it makes none. Adventuring Gear's landfall pump makes it a 3-power attacker
without casting a spell, which would trigger its prowess.
"""

from cards.fdn.fdn_35.card_impl import DrakeHatcher, DrakeHatcherAbility3, DrakeHatcherAbility4
from cards.fdn.fdn_150.card_impl import AegisTurtle
from cards.fdn.fdn_249.card_impl import (
    AdventuringGear,
    AdventuringGearAbility1,
    AdventuringGearAbility2,
)
from cards.fdn.fdn_272.card_impl import Plains
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game, token

from table import Table, appears, life, moves, off_stack, on_stack, taps


def _hatcher_attacks(t, hatcher, damage):
    """The Hatcher attacks unblocked (vigilance: it stays untapped), and its
    combat damage trigger resolves."""
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, hatcher)
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[damage, on_stack(DrakeHatcherAbility3, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(DrakeHatcherAbility3)])


def _hatcher_deals_three(p1_battlefield=()):
    """Turn 1: the Hatcher, equipped with Adventuring Gear and pumped by a
    land's landfall, deals 3 combat damage to player 1."""
    hatcher, gear, plains = card(DrakeHatcher), card(AdventuringGear), card(Plains)
    game = create_game(
        Side(
            battlefield=[hatcher, gear],
            hand=[plains],
            mana={ManaType.COLORLESS: 1},
            library=[card(Plains)],
        ),
        Side(battlefield=list(p1_battlefield), library=[card(Plains)]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(
        0, AdventuringGearAbility2, choices=[hatcher], then=[on_stack(AdventuringGearAbility2, 0)]
    )
    t.pass_(0)
    t.pass_(1, then=[off_stack(AdventuringGearAbility2)])
    t.act(0, plains, then=[moves(plains, Zone.BATTLEFIELD), on_stack(AdventuringGearAbility1, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(AdventuringGearAbility1)])
    _hatcher_attacks(t, hatcher, life(1, 17))
    return t


def _make_drake(t):
    t.act(0, DrakeHatcherAbility4, then=[on_stack(DrakeHatcherAbility4, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(DrakeHatcherAbility4), appears(0)])
    t.act_illegal(0, DrakeHatcherAbility4, note="fewer than three incubation counters are left")


def test_combat_damage_adds_engine_counters():
    t = _hatcher_deals_three()
    _make_drake(t)
    t.run()


def test_ability_pays_three_counters_and_mints_drake():
    """The Drake attacks on the next turn as a 2-power flier the Turtle cannot
    block."""
    turtle = card(AegisTurtle)
    t = _hatcher_deals_three([turtle])
    _make_drake(t)
    t.pass_(0)
    t.pass_(1)
    t.pass_to(Step.UPKEEP, 0)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, token(1), then=[taps(token(1))])
    t.pass_(0)
    t.pass_(1)
    t.act_illegal(1, turtle, scoped={turtle: token(1)})
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, 15)])
    t.run()


def test_ability_unpayable_below_three_counters():
    """Two attacks for 1 leave two incubation counters: not enough."""
    hatcher = card(DrakeHatcher)
    game = create_game(
        Side(battlefield=[hatcher], library=[card(Plains)]),
        Side(library=[card(Plains)]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act_illegal(0, DrakeHatcherAbility4)
    _hatcher_attacks(t, hatcher, life(1, 19))
    t.pass_to(Step.UPKEEP, 0)
    _hatcher_attacks(t, hatcher, life(1, 18))
    t.act_illegal(0, DrakeHatcherAbility4, note="two incubation counters are not enough")
    t.run()
