"""Slaughter Pact, played at the table.

Each test builds a position, plays it through both players' scripts and judges
Slaughter Pact by what the players can see: which creature goes to the
graveyard, whether the pact comes due at its caster's next upkeep, and whether
not paying it ends the game. Mana in a pool is not visible, so paying shows as
the game going on.
"""

from card_impl import SlaughterPact, SlaughterPactAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_171.card_impl import DiregrafGhoul
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_276.card_impl import Swamp
from test_interface import Decision, ManaType, Phase, Side, Step, Zone, branch, card, create_game

from table import Table, life, moves, off_stack, on_stack, taps, wins

MAIN = (Phase.PRECOMBAT_MAIN, 0)
PACT_COMES_DUE = SlaughterPactAbility2


def _library(n: int = 4) -> list:
    return [Plains for _ in range(n)]


def _pact(t: Table, seat: int, pact, target, *, then=()) -> None:
    """``seat`` casts ``pact`` at ``target``; both pass and it resolves."""
    t.act(seat, pact, choices=[target], then=[moves(pact, Zone.STACK)])
    t.pass_(seat)
    t.pass_(1 - seat, then=[moves(pact, Zone.GRAVEYARD), moves(target, Zone.GRAVEYARD), *then])


def _to_next_upkeep(t: Table, seat: int = 0, *, triggers: int = 1, **options) -> None:
    """Everyone passes until ``seat``'s next upkeep, where ``triggers`` pacts
    come due; ``options`` answer the questions that follow ``seat``'s last pass."""
    t.pass_to(Step.END, 1 - seat)
    t.pass_(1 - seat)
    t.pass_(seat, then=[on_stack(PACT_COMES_DUE, seat) for _ in range(triggers)], **options)


def _pay(t: Table, seat: int, lands) -> None:
    """``seat`` taps ``lands`` for mana and pays the pact on top of the stack."""
    for land in lands:
        t.act(seat, land, then=[taps(land)])
    t.pass_(seat, choices=[Decision.yes()])
    t.pass_(1 - seat, then=[off_stack(PACT_COMES_DUE)])


def test_destroys_a_nonblack_creature_for_no_mana():
    pact, lions = card(SlaughterPact), card(SavannahLions)
    game = create_game(Side(hand=[pact], library=_library()), Side(battlefield=[lions], library=_library()), start=MAIN)
    t = Table(game)
    _pact(t, 0, pact, lions)
    t.run()


def test_may_destroy_its_casters_own_creature():
    pact, lions = card(SlaughterPact), card(SavannahLions)
    game = create_game(Side(hand=[pact], battlefield=[lions], library=_library()), Side(library=_library()), start=MAIN)
    t = Table(game)
    _pact(t, 0, pact, lions)
    t.run()


def test_cannot_target_a_black_creature():
    """With only a black creature on the battlefield the pact has no legal target."""
    pact, ghoul = card(SlaughterPact), card(DiregrafGhoul)
    game = create_game(Side(hand=[pact], library=_library()), Side(battlefield=[ghoul], library=_library()), start=MAIN)
    t = Table(game)
    t.act_illegal(0, pact, choices=[ghoul])
    t.run()


def test_destroys_the_nonblack_creature_beside_a_black_one():
    """Aimed first at the black Ghoul, the pact can only take the Lions."""
    pact, ghoul, lions = card(SlaughterPact), card(DiregrafGhoul), card(SavannahLions)
    game = create_game(Side(hand=[pact], library=_library()), Side(battlefield=[ghoul, lions], library=_library()),
                       start=MAIN)
    t = Table(game)
    t.act(0, branches=[branch(pact, choices=[ghoul]), branch(pact, choices=[lions])],
          then=[moves(pact, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(pact, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD)])
    t.run()


def test_paying_at_the_next_upkeep_keeps_its_caster_in_the_game():
    """The pact comes due at its caster's next upkeep, not the opponent's, and
    {2}{B} pays it."""
    pact, lions = card(SlaughterPact), card(SavannahLions)
    swamps = [card(Swamp) for _ in range(3)]
    game = create_game(Side(hand=[pact], battlefield=swamps, library=_library()),
                       Side(battlefield=[lions], library=_library()), start=MAIN)
    t = Table(game)
    _pact(t, 0, pact, lions)
    _to_next_upkeep(t)
    _pay(t, 0, swamps)
    t.pass_to(Phase.PRECOMBAT_MAIN, 0)
    t.run()


def test_not_paying_loses_the_game():
    pact, lions = card(SlaughterPact), card(SavannahLions)
    game = create_game(Side(hand=[pact], library=_library()), Side(battlefield=[lions], library=_library()), start=MAIN)
    t = Table(game)
    _pact(t, 0, pact, lions)
    _to_next_upkeep(t)
    t.pass_(0, choices=[Decision.no()], note="no mana to pay {2}{B}")
    t.pass_(1, then=[off_stack(PACT_COMES_DUE), wins(1)])
    t.run()


def test_declining_to_pay_loses_even_with_the_mana():
    pact, lions = card(SlaughterPact), card(SavannahLions)
    swamps = [card(Swamp) for _ in range(3)]
    game = create_game(Side(hand=[pact], battlefield=swamps, library=_library()),
                       Side(battlefield=[lions], library=_library()), start=MAIN)
    t = Table(game)
    _pact(t, 0, pact, lions)
    _to_next_upkeep(t)
    for swamp in swamps:
        t.act(0, swamp, then=[taps(swamp)])
    t.pass_(0, choices=[Decision.no()])
    t.pass_(1, then=[off_stack(PACT_COMES_DUE), wins(1)])
    t.run()


def test_two_mana_short_of_the_cost_loses():
    """{B}{B} is not {2}{B}: with two Swamps the pact cannot be paid."""
    pact, lions = card(SlaughterPact), card(SavannahLions)
    swamps = [card(Swamp) for _ in range(2)]
    game = create_game(Side(hand=[pact], battlefield=swamps, library=_library()),
                       Side(battlefield=[lions], library=_library()), start=MAIN)
    t = Table(game)
    _pact(t, 0, pact, lions)
    _to_next_upkeep(t)
    for swamp in swamps:
        t.act(0, swamp, then=[taps(swamp)])
    t.pass_(0, branches=[branch(choices=[Decision.yes()]), branch(choices=[Decision.no()])])
    t.pass_(1, then=[off_stack(PACT_COMES_DUE), wins(1)])
    t.run()


def test_cast_in_its_casters_upkeep_comes_due_the_next_turn():
    """Cast during its caster's own upkeep, the pact waits for the following
    upkeep: nothing is due this turn, though its caster has no mana."""
    pact, lions = card(SlaughterPact), card(SavannahLions)
    game = create_game(Side(hand=[pact], library=_library()), Side(battlefield=[lions], library=_library()),
                       start=(Step.UPKEEP, 0))
    t = Table(game)
    _pact(t, 0, pact, lions)
    _to_next_upkeep(t)
    t.pass_(0, choices=[Decision.no()])
    t.pass_(1, then=[off_stack(PACT_COMES_DUE), wins(1)])
    t.run()


def test_cast_on_the_opponents_turn_kills_an_attacker():
    """An instant on the opponent's turn: the attacking Lions it destroys deals
    no damage, the other attacker does, and the pact comes due at its caster's
    next upkeep."""
    pact, lions, other = card(SlaughterPact), card(SavannahLions), card(SavannahLions)
    swamps = [card(Swamp) for _ in range(3)]
    game = create_game(Side(hand=[pact], battlefield=swamps, library=_library()),
                       Side(battlefield=[lions, other], library=_library()), start=(Phase.PRECOMBAT_MAIN, 1))
    t = Table(game)
    t.pass_to(Step.DECLARE_ATTACKERS, 1)
    t.act(1, lions, other, then=[taps(lions), taps(other)])
    t.pass_(1)
    _pact(t, 0, pact, lions)
    t.pass_(1)
    t.pass_(0)
    t.pass_(0)
    t.pass_(1)
    t.pass_(0, then=[life(0, 18)])
    t.pass_(1)
    t.pass_(0)
    t.pass_to(Step.END, 1)
    t.pass_(1)
    t.pass_(0, then=[on_stack(PACT_COMES_DUE, 0)])
    _pay(t, 0, swamps)
    t.run()


def test_a_pact_whose_target_is_gone_never_comes_due():
    """When its target dies first the pact does not resolve, so nothing comes
    due: its caster, with no mana, is still in the game on their next turn."""
    pact, bolt, lions = card(SlaughterPact), card(BurstLightning), card(SavannahLions)
    game = create_game(Side(hand=[pact, bolt], library=_library(), mana={ManaType.RED: 1}),
                       Side(battlefield=[lions], library=_library()), start=MAIN)
    t = Table(game)
    t.act(0, pact, choices=[lions], then=[moves(pact, Zone.STACK)])
    t.act(0, bolt, choices=[lions], then=[moves(bolt, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD)])
    t.pass_(0)
    t.pass_(1, then=[moves(pact, Zone.GRAVEYARD)])
    t.pass_to(Phase.PRECOMBAT_MAIN, 0)
    t.pass_to(Phase.PRECOMBAT_MAIN, 0)
    t.run()


def test_each_pact_must_be_paid():
    """Two pacts come due together; paying one is not enough."""
    first, second = card(SlaughterPact), card(SlaughterPact)
    lions, other = card(SavannahLions), card(SavannahLions)
    swamps = [card(Swamp) for _ in range(3)]
    game = create_game(Side(hand=[first, second], battlefield=swamps, library=_library()),
                       Side(battlefield=[lions, other], library=_library()), start=MAIN)
    t = Table(game)
    _pact(t, 0, first, lions)
    _pact(t, 0, second, other)
    _to_next_upkeep(t, triggers=2, choices=[PACT_COMES_DUE, PACT_COMES_DUE])
    _pay(t, 0, swamps)
    t.pass_(0, choices=[Decision.no()])
    t.pass_(1, then=[off_stack(PACT_COMES_DUE), wins(1)])
    t.run()


def test_two_pacts_paid_in_full():
    first, second = card(SlaughterPact), card(SlaughterPact)
    lions, other = card(SavannahLions), card(SavannahLions)
    swamps = [card(Swamp) for _ in range(6)]
    game = create_game(Side(hand=[first, second], battlefield=swamps, library=_library()),
                       Side(battlefield=[lions, other], library=_library()), start=MAIN)
    t = Table(game)
    _pact(t, 0, first, lions)
    _pact(t, 0, second, other)
    _to_next_upkeep(t, triggers=2, choices=[PACT_COMES_DUE, PACT_COMES_DUE])
    _pay(t, 0, swamps[:3])
    _pay(t, 0, swamps[3:])
    t.pass_to(Phase.PRECOMBAT_MAIN, 0)
    t.run()
