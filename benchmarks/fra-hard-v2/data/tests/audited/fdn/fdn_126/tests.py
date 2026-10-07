"""Reference test for FDN 126 — Zimone, Paradox Sculptor.

Two targeted mechanisms fixed at stack-placement time, not at resolution:

* ``{G}{U}, {T}``: an activated ability targeting *up to two distinct*
  creatures/artifacts you control — genuinely optional (zero/one/two), chosen at
  activation, revalidated (stint + "you control") at resolution.
* Beginning-of-combat trigger: "up to two target creatures you control" whose
  targets are chosen as the trigger is put on the stack.

Counters show in play: a Savannah Lions (2/1) with one +1/+1 counter attacks
for 3, with two for 4.
"""

from __future__ import annotations

from cards.fdn.fdn_40.card_impl import HighFaeTrickster
from cards.fdn.fdn_126.card_impl import (
    ZimoneParadoxSculptor,
    ZimoneParadoxSculptorAbility1,
    ZimoneParadoxSculptorAbility2,
)
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_203.card_impl import InvoluntaryEmployment
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_278.card_impl import Mountain
from cards.fdn.fdn_280.card_impl import Forest
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from test_interface import Side, card
from test_interface import create_game as table_game

from table import Table, appears, gains_control, life, moves, off_stack, on_stack, taps

TRIGGER, DOUBLE = ZimoneParadoxSculptorAbility1, ZimoneParadoxSculptorAbility2


def _table(p0, p1=None, *, start=(Phase.PRECOMBAT_MAIN, 0)):
    return Table(table_game(p0, p1 or Side(), start=start))


def _combat_trigger(t, *targets, seat=0):
    """From a main phase, the game moves to beginning of combat and Zimone's
    trigger, targeting ``targets``, resolves."""
    t.pass_(seat, choices=list(targets), distinct=True)
    t.pass_(1 - seat, then=[on_stack(TRIGGER, seat)])
    t.pass_(seat, choices=list(targets), distinct=True)
    t.pass_(1 - seat, then=[off_stack(TRIGGER)])


def _double(t, zimone, forest, island, *targets, respond=None):
    """Player 0 taps a Forest and an Island and activates Zimone's ability
    targeting ``targets``; ``respond`` plays out before it resolves."""
    t.act(0, forest, then=[taps(forest)])
    t.act(0, island, then=[taps(island)])
    t.act(0, DOUBLE, choices=list(targets), distinct=True, then=[taps(zimone), on_stack(DOUBLE, 0)])
    if respond:
        respond(t)
    t.pass_(0)
    t.pass_(1, then=[off_stack(DOUBLE)])


def _attack(t, *attackers, damage, seat=0, life_before=20):
    """From beginning of combat, ``attackers`` attack unblocked."""
    t.pass_(seat)
    t.pass_(1 - seat)
    t.act(seat, *attackers, then=[taps(a) for a in attackers])
    t.pass_(seat)
    t.pass_(1 - seat)
    t.pass_(1 - seat)
    t.pass_(seat)
    t.pass_(1 - seat, then=[life(1 - seat, life_before - damage)])


def _stealer():
    """Player 1's side: High Fae Trickster, four Mountains and Involuntary
    Employment in hand, to cast at instant speed; with the Mountains and the
    Employment."""
    mountains, employment = [card(Mountain) for _ in range(4)], card(InvoluntaryEmployment)
    side = Side(hand=[employment], battlefield=[HighFaeTrickster, *mountains], library=[Forest])
    return side, (mountains, employment)


def _steal(t, stealer, creature):
    """Player 0 passes; player 1 taps four Mountains and casts Involuntary
    Employment on ``creature``, which resolves."""
    mountains, employment = stealer
    t.pass_(0)
    for mountain in mountains:
        t.act(1, mountain, then=[taps(mountain)])
    t.act(1, employment, choices=[creature], then=[moves(employment, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(employment, Zone.GRAVEYARD), gains_control(creature, 1), appears(1)])


def _next_turn_attack(t, attacker, *, damage, life_before):
    """Involuntary Employment's control of ``attacker`` ends at cleanup; on
    player 0's next turn Zimone's trigger targets nothing, and ``attacker``
    attacks unblocked."""
    t.pass_to(Step.END, 0)
    t.pass_(0)
    t.pass_(1, then=[gains_control(attacker, 0)], note="Involuntary Employment's control ends at cleanup")
    t.pass_to(Phase.PRECOMBAT_MAIN, 0)
    _combat_trigger(t)
    _attack(t, attacker, damage=damage, life_before=life_before)


def _countered_pair(opponent=None):
    """Zimone's combat trigger puts a counter on each of two Savannah Lions."""
    zimone, a, b, forest, island = card(ZimoneParadoxSculptor), card(SavannahLions), card(SavannahLions), card(Forest), card(Island)
    t = _table(Side(battlefield=[zimone, a, b, forest, island], library=[Forest]), opponent)
    _combat_trigger(t, a, b)
    return t, zimone, a, b, forest, island


class TestZimoneProperties:
    def test_static_data(self):
        z = ZimoneParadoxSculptor(owner=None)
        assert z.mana_cost == ManaCost.parse("{2}{G}{U}")
        assert (z.base_power, z.base_toughness) == (1, 4)


class TestZimoneDoubleAbility:

    def test_two_distinct_targets_doubled(self):
        t, zimone, a, b, forest, island = _countered_pair()
        _double(t, zimone, forest, island, a, b)
        _attack(t, a, b, damage=4 + 4)
        t.run()

    def test_one_target(self):
        t, zimone, a, b, forest, island = _countered_pair()
        _double(t, zimone, forest, island, a)
        _attack(t, a, b, damage=4 + 3)
        t.run()

    def test_zero_targets_still_activates(self):
        """Genuinely optional: with no target chosen the ability is still
        activated, and Zimone taps for its cost."""
        t, zimone, a, b, forest, island = _countered_pair()
        _double(t, zimone, forest, island)
        _attack(t, a, b, damage=3 + 3)
        t.run()

    def test_one_target_illegal_other_legal(self):
        """A target leaves "you control" before resolution and the other still
        doubles (rule 608.2b — each target is checked on its own): player 1,
        whose High Fae Trickster lets them cast Involuntary Employment at
        instant speed, takes Lions A in response. Lions B, doubled to two
        counters, attacks for 4; on player 0's next turn Lions A, back with its
        one counter, attacks for 3."""
        side, stealer = _stealer()
        t, zimone, a, b, forest, island = _countered_pair(side)
        _double(t, zimone, forest, island, a, b, respond=lambda t: _steal(t, stealer, a))
        _attack(t, b, damage=4)
        _next_turn_attack(t, a, damage=3, life_before=16)
        t.run()


class TestZimoneCombatTrigger:

    def test_two_targets_countered_at_trigger_time(self):
        t, _zimone, a, b, _forest, _island = _countered_pair()
        _attack(t, a, b, damage=3 + 3)
        t.run()

    def test_target_control_change_before_resolution(self):
        """Player 1 takes Lions A while Zimone's trigger waits: A is no longer
        a creature its controller controls, so only Lions B gets a counter
        and attacks for 3; on player 0's next turn Lions A, back without a
        counter, attacks for 2."""
        zimone, a, b = card(ZimoneParadoxSculptor), card(SavannahLions), card(SavannahLions)
        side, stealer = _stealer()
        t = _table(Side(battlefield=[zimone, a, b], library=[Forest]), side)
        t.pass_(0, choices=[a, b], distinct=True)
        t.pass_(1, then=[on_stack(TRIGGER, 0)])
        _steal(t, stealer, a)
        t.pass_(0)
        t.pass_(1, then=[off_stack(TRIGGER)])
        _attack(t, b, damage=3)
        _next_turn_attack(t, a, damage=2, life_before=17)
        t.run()

    def test_source_control_change_between_registration_and_fire(self):
        """Zimone changes controller after its trigger is registered but before
        beginning of combat: the trigger's controller is determined at fire
        time (rule 603.3e). Player 1 takes Zimone with Involuntary Employment
        on their turn, so at their beginning of combat the trigger is theirs
        and puts the counter on their own Savannah Lions, which attacks for 3."""
        zimone, ours, theirs, employment = card(ZimoneParadoxSculptor), card(SavannahLions), card(SavannahLions), card(InvoluntaryEmployment)
        t = _table(
            Side(battlefield=[zimone, ours]),
            Side(hand=[employment], battlefield=[theirs], mana={ManaType.RED: 4}),
            start=(Phase.PRECOMBAT_MAIN, 1),
        )
        t.act(1, employment, choices=[zimone], then=[moves(employment, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(employment, Zone.GRAVEYARD), gains_control(zimone, 1), appears(1)])
        _combat_trigger(t, theirs, seat=1)
        _attack(t, theirs, damage=3, seat=1)
        t.run()
