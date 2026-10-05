"""Bloodline Recollector // Ancestral Craving, played at the table.

Each test builds a position, plays it through both players' scripts and judges
the card by what the players can see. Whether the Recollector is prepared
shows only through whether its controller may cast a copy of Ancestral
Craving: a prepared Recollector shows nothing else on the table.
"""

from card_impl import AncestralCraving, BloodlineRecollector, BloodlineRecollectorAbility1
from cards.fdn.fdn_48.card_impl import Refute
from cards.fdn.fdn_134.card_impl import AjaniCallerOfThePride
from cards.fdn.fdn_145.card_impl import ResoluteReinforcements, ResoluteReinforcementsAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_175.card_impl import HerosDownfall
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_203.card_impl import InvoluntaryEmployment
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_276.card_impl import Swamp
from cards.fdn.fdn_278.card_impl import Mountain
from test_interface import ManaType, Phase, Side, Step, Zone, branch, card, create_game, player, spell_copy, token

from silverquillm.table import Table, appears, ceases, copied, gains_control, life, moves, off_stack, on_stack, taps

MAIN = (Phase.PRECOMBAT_MAIN, 0)
PREPARE = BloodlineRecollectorAbility1


def _library(n: int = 4) -> list:
    return [card(Plains) for _ in range(n)]


def _bolt(t: Table, seat: int, bolt, target, *, then=()) -> None:
    """``seat`` casts Burst Lightning at ``target``; it resolves."""
    t.act(seat, bolt, choices=[target], then=[moves(bolt, Zone.STACK)])
    t.pass_(seat)
    t.pass_(1 - seat, then=[moves(bolt, Zone.GRAVEYARD), *then])


def _kill(t: Table, seat: int, bolts, victims) -> None:
    for bolt, victim in zip(bolts, victims):
        _bolt(t, seat, bolt, victim, then=[moves(victim, Zone.GRAVEYARD)])


def _into_end_step(t: Table, seat: int = 0, *, triggers: int = 1) -> None:
    """Every player passes into ``seat``'s end step, where ``triggers``
    Recollector triggers go on the stack and resolve."""
    t.pass_to(Phase.POSTCOMBAT_MAIN, seat)
    t.pass_(seat)
    t.pass_(1 - seat, then=[on_stack(PREPARE, seat) for _ in range(triggers)])
    for _ in range(triggers):
        t.pass_(seat)
        t.pass_(1 - seat, then=[off_stack(PREPARE)])


def offers_craving(query) -> bool:
    """A question that offers Ancestral Craving among its options."""
    return any(dict(getattr(option, "attrs", ())).get("printed") is AncestralCraving for option in query.options)


def craving(target: int, *recollectors) -> list:
    """Branches that cast a copy of Ancestral Craving at player ``target``,
    whether the engine offers the spell itself or a prepared Recollector
    followed by which of the two to cast."""
    return [branch(AncestralCraving, choices=[player(target)]),
            *[branch(source, choices=[player(target)], per_query={offers_craving: [AncestralCraving]})
              for source in recollectors]]


def _cast_craving(t: Table, seat: int, swamp, target: int, *recollectors) -> None:
    """``seat`` taps ``swamp`` and casts a copy of Ancestral Craving at player ``target``."""
    t.act(seat, swamp, then=[taps(swamp)])
    t.act(seat, branches=craving(target, *recollectors), then=[copied(AncestralCraving, seat)],
          note="the prepared Recollector lets its controller cast a copy of its spell")


def _resolve_craving(t: Table, seat: int, target: int, drawn, life_after: int) -> None:
    t.pass_(seat)
    t.pass_(1 - seat, then=[off_stack(AncestralCraving), *[moves(c, Zone.HAND) for c in drawn], life(target, life_after)])


def _three_deaths(recollector=None, *, extra_hand=(), lands=(), seat1: Side | None = None):
    """Player 0, with a Recollector, three Savannah Lions and three Burst Lightnings."""
    lions = [card(SavannahLions) for _ in range(3)]
    bolts = [card(BurstLightning) for _ in range(3)]
    recollector = recollector or card(BloodlineRecollector)
    game = create_game(
        Side(hand=[*bolts, *extra_hand], battlefield=[recollector, *lions, *lands], library=_library(),
             mana={ManaType.RED: 3}),
        seat1 or Side(library=_library()),
        start=MAIN,
    )
    return game, recollector, lions, bolts


def test_three_deaths_prepare_and_the_copy_draws_three_and_loses_three():
    swamp = card(Swamp)
    library = _library()
    game, recollector, lions, bolts = _three_deaths(lands=[swamp], seat1=Side(library=library))
    t = Table(game)
    _kill(t, 0, bolts, lions)
    _into_end_step(t)
    _cast_craving(t, 0, swamp, 1, recollector)
    _resolve_craving(t, 0, 1, library[:3], 17)
    t.run()


def test_the_copy_can_target_its_caster():
    swamp, library, recollector = card(Swamp), _library(6), card(BloodlineRecollector)
    lions = [card(SavannahLions) for _ in range(3)]
    bolts = [card(BurstLightning) for _ in range(3)]
    game = create_game(
        Side(hand=bolts, battlefield=[recollector, swamp, *lions], library=library, mana={ManaType.RED: 3}),
        Side(library=_library()),
        start=MAIN,
    )
    t = Table(game)
    _kill(t, 0, bolts, lions)
    _into_end_step(t)
    _cast_craving(t, 0, swamp, 0, recollector)
    _resolve_craving(t, 0, 0, library[:3], 17)
    t.run()


def test_casting_the_copy_unprepares_the_recollector():
    """Once its copy is cast — even while it is still on the stack — the
    Recollector is no longer prepared."""
    first, second = card(Swamp), card(Swamp)
    library = _library()
    game, recollector, lions, bolts = _three_deaths(lands=[first, second], seat1=Side(library=library))
    t = Table(game)
    _kill(t, 0, bolts, lions)
    _into_end_step(t)
    _cast_craving(t, 0, first, 1, recollector)
    t.act(0, second, then=[taps(second)])
    t.act_illegal(0, branches=craving(1, recollector), note="the copy already cast unprepared it")
    _resolve_craving(t, 0, 1, library[:3], 17)
    t.act_illegal(0, branches=craving(1, recollector))
    t.run()


def test_two_deaths_do_not_prepare():
    swamp = card(Swamp)
    game, recollector, lions, bolts = _three_deaths(lands=[swamp])
    t = Table(game)
    _kill(t, 0, bolts[:2], lions[:2])
    t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
    t.pass_(0)
    t.pass_(1, note="no Recollector trigger: fewer than three creatures died")
    t.act(0, swamp, then=[taps(swamp)])
    t.act_illegal(0, branches=craving(1, recollector))
    t.run()


def test_the_opponents_creatures_count():
    swamp = card(Swamp)
    lions = [card(SavannahLions) for _ in range(3)]
    bolts = [card(BurstLightning) for _ in range(3)]
    library, recollector = _library(), card(BloodlineRecollector)
    game = create_game(
        Side(hand=bolts, battlefield=[recollector, swamp], library=_library(), mana={ManaType.RED: 3}),
        Side(battlefield=lions, library=library),
        start=MAIN,
    )
    t = Table(game)
    _kill(t, 0, bolts, lions)
    _into_end_step(t)
    _cast_craving(t, 0, swamp, 1, recollector)
    _resolve_craving(t, 0, 1, library[:3], 17)
    t.run()


def test_token_creatures_dying_count():
    """Two Lions and the Soldier token Resolute Reinforcements makes die."""
    swamp, reinforcements, recollector = card(Swamp), card(ResoluteReinforcements), card(BloodlineRecollector)
    lions = [card(SavannahLions) for _ in range(2)]
    bolts = [card(BurstLightning) for _ in range(3)]
    game = create_game(
        Side(hand=[*bolts, reinforcements], battlefield=[recollector, swamp, *lions], library=_library(),
             mana={ManaType.RED: 3, ManaType.WHITE: 2}),
        Side(library=_library()),
        start=MAIN,
    )
    t = Table(game)
    t.act(0, reinforcements, then=[moves(reinforcements, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(reinforcements, Zone.BATTLEFIELD), on_stack(ResoluteReinforcementsAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(ResoluteReinforcementsAbility2), appears(0)])
    _kill(t, 0, bolts[:2], lions)
    _bolt(t, 0, bolts[2], token(1), then=[ceases(token(1))])
    _into_end_step(t)
    t.act(0, swamp, then=[taps(swamp)])
    t.act(0, branches=craving(1, recollector), then=[copied(AncestralCraving, 0)])
    t.run()


def test_noncreature_deaths_do_not_count():
    """Two Lions and a planeswalker dying is not three creatures."""
    swamp, ajani, downfall = card(Swamp), card(AjaniCallerOfThePride), card(HerosDownfall)
    recollector = card(BloodlineRecollector)
    lions = [card(SavannahLions) for _ in range(2)]
    bolts = [card(BurstLightning) for _ in range(2)]
    game = create_game(
        Side(hand=[*bolts, downfall], battlefield=[recollector, swamp, *lions, ajani], library=_library(),
             mana={ManaType.RED: 2, ManaType.BLACK: 3}),
        Side(library=_library()),
        start=MAIN,
    )
    t = Table(game)
    _kill(t, 0, bolts, lions)
    t.act(0, downfall, choices=[ajani], then=[moves(downfall, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(downfall, Zone.GRAVEYARD), moves(ajani, Zone.GRAVEYARD)])
    t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
    t.pass_(0)
    t.pass_(1, note="no Recollector trigger")
    t.act(0, swamp, then=[taps(swamp)])
    t.act_illegal(0, branches=craving(1, recollector))
    t.run()


def test_deaths_before_the_recollector_entered_count():
    swamp, recollector = card(Swamp), card(BloodlineRecollector)
    library = _library()
    lions = [card(SavannahLions) for _ in range(3)]
    bolts = [card(BurstLightning) for _ in range(3)]
    game = create_game(
        Side(hand=[*bolts, recollector], battlefield=[swamp, *lions], library=_library(),
             mana={ManaType.RED: 3, ManaType.BLACK: 2}),
        Side(library=library),
        start=MAIN,
    )
    t = Table(game)
    _kill(t, 0, bolts, lions)
    t.act(0, recollector, then=[moves(recollector, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(recollector, Zone.BATTLEFIELD)])
    _into_end_step(t)
    _cast_craving(t, 0, swamp, 1, recollector)
    _resolve_craving(t, 0, 1, library[:3], 17)
    t.run()


def test_deaths_on_an_earlier_turn_do_not_count():
    """Three creatures die on player 0's turn; player 1's Recollector, cast on
    the next turn, does not become prepared at that turn's end step."""
    recollector, lands = card(BloodlineRecollector), [card(Swamp), card(Swamp), card(Swamp)]
    lions = [card(SavannahLions) for _ in range(3)]
    bolts = [card(BurstLightning) for _ in range(3)]
    game = create_game(
        Side(hand=bolts, battlefield=lions, library=_library(), mana={ManaType.RED: 3}),
        Side(hand=[recollector], battlefield=lands, library=_library()),
        start=MAIN,
    )
    t = Table(game)
    _kill(t, 0, bolts, lions)
    t.pass_to(Phase.PRECOMBAT_MAIN, 1)
    t.act(1, lands[0], then=[taps(lands[0])])
    t.act(1, lands[1], then=[taps(lands[1])])
    t.act(1, recollector, then=[moves(recollector, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(recollector, Zone.BATTLEFIELD)])
    t.pass_to(Phase.POSTCOMBAT_MAIN, 1)
    t.pass_(1)
    t.pass_(0, note="no Recollector trigger: no creature died this turn")
    t.act(1, lands[2], then=[taps(lands[2])])
    t.act_illegal(1, branches=craving(0, recollector))
    t.run()


def test_the_copy_needs_black_mana():
    mountain = card(Mountain)
    game, recollector, lions, bolts = _three_deaths(lands=[mountain])
    t = Table(game)
    _kill(t, 0, bolts, lions)
    _into_end_step(t)
    t.act(0, mountain, then=[taps(mountain)])
    t.act_illegal(0, branches=craving(1, recollector), note="{R} cannot pay {B}")
    t.run()


def test_preparation_ends_when_the_recollector_leaves():
    swamp, mountain, bolt = card(Swamp), card(Mountain), card(BurstLightning)
    game, recollector, lions, bolts = _three_deaths(lands=[swamp, mountain], extra_hand=[bolt])
    t = Table(game)
    _kill(t, 0, bolts, lions)
    _into_end_step(t)
    t.act(0, mountain, then=[taps(mountain)])
    _bolt(t, 0, bolt, recollector, then=[moves(recollector, Zone.GRAVEYARD)])
    t.act(0, swamp, then=[taps(swamp)])
    t.act_illegal(0, branches=craving(1, recollector))
    t.run()


def test_leaving_before_the_trigger_resolves_prepares_nothing():
    """The Recollector dies with its trigger on the stack: nothing can be cast."""
    swamp = card(Swamp)
    bolt = card(BurstLightning)
    mountain = card(Mountain)
    game, recollector, lions, bolts = _three_deaths(
        lands=[swamp], seat1=Side(hand=[bolt], battlefield=[mountain], library=_library()))
    t = Table(game)
    _kill(t, 0, bolts, lions)
    t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
    t.pass_(0)
    t.pass_(1, then=[on_stack(PREPARE, 0)])
    t.pass_(0)
    t.act(1, mountain, then=[taps(mountain)])
    _bolt(t, 1, bolt, recollector, then=[moves(recollector, Zone.GRAVEYARD)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(PREPARE)])
    t.act(0, swamp, then=[taps(swamp)])
    t.act_illegal(0, branches=craving(1, recollector))
    t.run()


def test_a_cast_copy_resolves_after_the_recollector_leaves():
    swamp, library = card(Swamp), _library()
    bolt, mountain = card(BurstLightning), card(Mountain)
    game, recollector, lions, bolts = _three_deaths(
        lands=[swamp], seat1=Side(hand=[bolt], battlefield=[mountain], library=library))
    t = Table(game)
    _kill(t, 0, bolts, lions)
    _into_end_step(t)
    _cast_craving(t, 0, swamp, 1, recollector)
    t.pass_(0)
    t.act(1, mountain, then=[taps(mountain)])
    _bolt(t, 1, bolt, recollector, then=[moves(recollector, Zone.GRAVEYARD)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(AncestralCraving), *[moves(c, Zone.HAND) for c in library[:3]], life(1, 17)])
    t.run()


def test_a_countered_copy_still_unprepares():
    first, second = card(Swamp), card(Swamp)
    refute = card(Refute)
    islands = [card(Island) for _ in range(3)]
    discard = card(Plains)
    game, recollector, lions, bolts = _three_deaths(
        lands=[first, second], seat1=Side(hand=[refute], battlefield=islands, library=[discard, *_library()]))
    t = Table(game)
    _kill(t, 0, bolts, lions)
    _into_end_step(t)
    _cast_craving(t, 0, first, 1, recollector)
    t.pass_(0)
    for island in islands:
        t.act(1, island, then=[taps(island)])
    t.act(1, refute, choices=[spell_copy(1)], then=[moves(refute, Zone.STACK)])
    t.pass_(1, choices=[discard])
    t.pass_(0, then=[moves(refute, Zone.GRAVEYARD), off_stack(AncestralCraving), moves(discard, Zone.HAND),
                     moves(discard, Zone.GRAVEYARD)])
    t.act(0, second, then=[taps(second)])
    t.act_illegal(0, branches=craving(1, recollector))
    t.run()


def test_two_recollectors_prepare_independently():
    first, second = card(Swamp), card(Swamp)
    library = _library(7)
    other = card(BloodlineRecollector)
    game, recollector, lions, bolts = _three_deaths(lands=[other, first, second], seat1=Side(library=library))
    t = Table(game)
    _kill(t, 0, bolts, lions)
    t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
    t.pass_(0)
    t.pass_(1, then=[on_stack(PREPARE, 0), on_stack(PREPARE, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(PREPARE)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(PREPARE)])
    _cast_craving(t, 0, first, 1, recollector, other)
    _resolve_craving(t, 0, 1, library[:3], 17)
    t.act(0, second, then=[taps(second)])
    t.act(0, branches=craving(1, recollector, other), then=[copied(AncestralCraving, 0)])
    _resolve_craving(t, 0, 1, library[3:6], 14)
    t.run()


def test_control_of_the_recollector_carries_its_preparation():
    """Player 1 gains control of a prepared Recollector and casts its copy."""
    employment = card(InvoluntaryEmployment)
    lands = [card(Mountain) for _ in range(4)] + [card(Swamp)]
    game, recollector, lions, bolts = _three_deaths(
        seat1=Side(hand=[employment], battlefield=lands, library=_library()))
    t = Table(game)
    _kill(t, 0, bolts, lions)
    _into_end_step(t)
    t.pass_to(Phase.PRECOMBAT_MAIN, 1)
    for land in lands[:4]:
        t.act(1, land, then=[taps(land)])
    t.act(1, employment, choices=[recollector], then=[moves(employment, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(employment, Zone.GRAVEYARD), gains_control(recollector, 1), appears(1)])
    t.act(1, lands[4], then=[taps(lands[4])])
    t.act(1, branches=craving(0, recollector), then=[copied(AncestralCraving, 1)])
    t.run()


def test_recollector_attacks_as_a_two_two():
    recollector = card(BloodlineRecollector)
    game = create_game(Side(battlefield=[recollector], library=_library()), Side(library=_library()), start=MAIN)
    t = Table(game)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, recollector, then=[taps(recollector)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, 18)])
    t.run()
