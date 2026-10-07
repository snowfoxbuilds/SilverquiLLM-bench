"""Supper for Spiders, played at the table.

Player 1's creatures die on player 0's turn, usually to player 0's Burst
Lightning, and player 0 then casts Supper for Spiders. A returned card shows on
player 0's side as the card it is, still player 1's. That it is a Food and no
longer a creature shows in what it can do: it gains 3 life, cannot attack or
block, and is not a creature to target.
"""

from card_impl import SupperForSpiders, SupperForSpidersAbility1
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_175.card_impl import HerosDownfall
from cards.fdn.fdn_187.card_impl import Zombify
from cards.fdn.fdn_188.card_impl import Abrade, AbradeAbility3
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_203.card_impl import InvoluntaryEmployment
from cards.fdn.fdn_205.card_impl import SeismicRupture
from cards.fdn.fdn_223.card_impl import GiantGrowth
from cards.fdn.fdn_227.card_impl import LlanowarElves, LlanowarElvesAbility1
from cards.fdn.fdn_258.card_impl import SwiftfootBoots
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_276.card_impl import Swamp
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game

from table import Table, appears, gains_control, life, moves, off_stack, on_stack, taps

MAIN = (Phase.PRECOMBAT_MAIN, 0)
FOOD = SupperForSpidersAbility1


def _plains(n: int = 3) -> list:
    return [card(Plains) for _ in range(n)]


def _game(*, hand=(), battlefield=(), graveyard=(), mana=None, seat1_battlefield=(), seat1_graveyard=(),
          seat1_hand=(), seat1_mana=None, start=MAIN):
    supper = card(SupperForSpiders)
    pool = {ManaType.BLACK: 1, ManaType.COLORLESS: 1}
    for kind, amount in (mana or {}).items():
        pool[kind] = pool.get(kind, 0) + amount
    game = create_game(
        Side(hand=[supper, *hand], battlefield=list(battlefield), graveyard=list(graveyard), library=_plains(),
             mana=pool),
        Side(battlefield=list(seat1_battlefield), graveyard=list(seat1_graveyard), hand=list(seat1_hand),
             library=_plains(), mana=dict(seat1_mana or {})),
        start=start,
    )
    return game, supper


def _resolve(t: Table, *, then=(), note: str = "") -> None:
    t.pass_(0)
    t.pass_(1, then=list(then), note=note)


def _bolt(t: Table, bolt, target, *, then=()) -> None:
    """Player 0's Burst Lightning kills ``target``."""
    t.act(0, bolt, choices=[target], then=[moves(bolt, Zone.STACK)])
    _resolve(t, then=[moves(bolt, Zone.GRAVEYARD), moves(target, Zone.GRAVEYARD), *then])


def _supper(t: Table, supper, returned=(), *, note: str = "") -> None:
    t.act(0, supper, then=[moves(supper, Zone.STACK)])
    _resolve(t, then=[moves(supper, Zone.GRAVEYARD), *(moves(c, Zone.BATTLEFIELD, seat=0) for c in returned)],
             note=note)


def _killed_lions(**kwargs):
    lions, bolt = card(SavannahLions), card(BurstLightning)
    game, supper = _game(hand=[bolt, *kwargs.pop("hand", ())], seat1_battlefield=[lions],
                         mana={ManaType.RED: 1, **kwargs.pop("mana", {})}, **kwargs)
    t = Table(game)
    _bolt(t, bolt, lions)
    return t, supper, lions


def test_an_opponents_creature_that_died_this_turn_returns_under_the_casters_control():
    t, supper, lions = _killed_lions()
    _supper(t, supper, [lions])
    t.run()


def test_the_food_ability_gains_three_life_and_sacrifices_it():
    t, supper, lions = _killed_lions(mana={ManaType.COLORLESS: 3})
    _supper(t, supper, [lions])
    t.act(0, FOOD, then=[moves(lions, Zone.GRAVEYARD), on_stack(FOOD, 0)],
          note="tapped and sacrificed as its cost, it goes to its owner's graveyard")
    _resolve(t, then=[off_stack(FOOD), life(0, 23)])
    t.run()


def test_the_food_ability_needs_its_two_mana():
    t, supper, lions = _killed_lions(mana={ManaType.COLORLESS: 1})
    _supper(t, supper, [lions])
    t.act_illegal(0, FOOD, note="only {1} is left")
    t.run()


def test_the_casters_own_dead_creature_is_not_returned():
    mine, bolt = card(SavannahLions), card(BurstLightning)
    game, supper = _game(hand=[bolt], battlefield=[mine], mana={ManaType.RED: 1})
    t = Table(game)
    _bolt(t, bolt, mine)
    _supper(t, supper, note="player 0's own Lions stays in their graveyard")
    t.run()


def test_a_creature_card_already_in_the_graveyard_is_not_returned():
    lions = card(SavannahLions)
    game, supper = _game(seat1_graveyard=[lions])
    t = Table(game)
    _supper(t, supper, note="it was not put there from the battlefield this turn")
    t.run()


def test_a_creature_that_died_last_turn_is_not_returned():
    """The Lions dies on player 0's turn; Supper is cast in player 1's upkeep."""
    lions, bolt, swamps = card(SavannahLions), card(BurstLightning), [card(Swamp), card(Swamp)]
    game, supper = _game(hand=[bolt], battlefield=swamps, mana={ManaType.RED: 1}, seat1_battlefield=[lions])
    t = Table(game)
    _bolt(t, bolt, lions)
    t.pass_to(Step.UPKEEP, 1)
    t.pass_(1)
    for swamp in swamps:
        t.act(0, swamp, then=[taps(swamp)])
    t.act(0, supper, then=[moves(supper, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(supper, Zone.GRAVEYARD)], note="the Lions stays in player 1's graveyard")
    t.run()


def test_every_creature_that_died_this_turn_returns():
    first, second, rupture = card(SavannahLions), card(SavannahLions), card(SeismicRupture)
    game, supper = _game(hand=[rupture], mana={ManaType.RED: 1, ManaType.COLORLESS: 2},
                         seat1_battlefield=[first, second])
    t = Table(game)
    t.act(0, rupture, then=[moves(rupture, Zone.STACK)])
    _resolve(t, then=[moves(rupture, Zone.GRAVEYARD), moves(first, Zone.GRAVEYARD), moves(second, Zone.GRAVEYARD)])
    _supper(t, supper, [first, second])
    t.run()


def test_a_noncreature_permanent_put_into_the_graveyard_is_not_returned():
    boots, abrade = card(SwiftfootBoots), card(Abrade)
    game, supper = _game(hand=[abrade], mana={ManaType.RED: 1, ManaType.COLORLESS: 1},
                         seat1_battlefield=[boots])
    t = Table(game)
    t.act(0, abrade, choices=[AbradeAbility3, boots], then=[moves(abrade, Zone.STACK)])
    _resolve(t, then=[moves(abrade, Zone.GRAVEYARD), moves(boots, Zone.GRAVEYARD)])
    _supper(t, supper, note="the Boots stays in player 1's graveyard")
    t.run()


def test_a_food_is_not_a_creature_to_target():
    """With no creature on the battlefield, player 1's Hero's Downfall has
    nothing to target: the Food Lions is not a creature."""
    downfall = card(HerosDownfall)
    t, supper, lions = _killed_lions(seat1_hand=[downfall], seat1_mana={ManaType.BLACK: 3})
    _supper(t, supper, [lions])
    t.pass_(0)
    t.act_illegal(1, downfall, choices=[lions])
    t.run()


def test_a_food_cannot_attack_on_a_later_turn():
    t, supper, lions = _killed_lions()
    _supper(t, supper, [lions])
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act_illegal(0, lions, note="it is not a creature, now or after the turn it was made a Food")
    t.run()


def test_a_food_cannot_block():
    attacker, lions, bolt = card(SavannahLions), card(SavannahLions), card(BurstLightning)
    game, supper = _game(hand=[bolt], mana={ManaType.RED: 1}, seat1_battlefield=[lions, attacker])
    t = Table(game)
    _bolt(t, bolt, lions)
    _supper(t, supper, [lions])
    t.pass_to(Step.DECLARE_ATTACKERS, 1)
    t.act(1, attacker, then=[taps(attacker)])
    t.pass_(1)
    t.pass_(0)
    t.act_illegal(0, lions, note="it is not a creature to block with")
    t.pass_(0)
    t.pass_(1)
    t.pass_(0, then=[life(0, 18)])
    t.run()


def test_the_food_ability_still_works_on_a_later_turn():
    swamps = [card(Swamp), card(Swamp)]
    t, supper, lions = _killed_lions(battlefield=swamps)
    _supper(t, supper, [lions])
    t.pass_to(Phase.PRECOMBAT_MAIN, 0)
    for swamp in swamps:
        t.act(0, swamp, then=[taps(swamp)])
    t.act(0, FOOD, then=[moves(lions, Zone.GRAVEYARD), on_stack(FOOD, 0)])
    _resolve(t, then=[off_stack(FOOD), life(0, 23)])
    t.run()


def test_a_sacrificed_food_is_a_creature_card_again():
    """Player 1 returns their sacrificed Lions with Zombify on their turn; it
    is their creature again, with no Food ability."""
    swamps, zombify = [card(Swamp) for _ in range(6)], card(Zombify)
    lions, bolt = card(SavannahLions), card(BurstLightning)
    game, supper = _game(hand=[bolt], mana={ManaType.RED: 1, ManaType.COLORLESS: 2},
                         seat1_battlefield=[lions, *swamps], seat1_hand=[zombify])
    t = Table(game)
    _bolt(t, bolt, lions)
    _supper(t, supper, [lions])
    t.act(0, FOOD, then=[moves(lions, Zone.GRAVEYARD), on_stack(FOOD, 0)])
    _resolve(t, then=[off_stack(FOOD), life(0, 23)])
    t.pass_to(Phase.PRECOMBAT_MAIN, 1)
    for swamp in swamps:
        t.act(1, swamp, then=[taps(swamp)])
    t.act(1, zombify, choices=[lions], then=[moves(zombify, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(zombify, Zone.GRAVEYARD), moves(lions, Zone.BATTLEFIELD, seat=1)])
    t.pass_to(Phase.PRECOMBAT_MAIN, 1)
    for swamp in swamps[:2]:
        t.act(1, swamp, then=[taps(swamp)])
    t.act_illegal(1, FOOD, note="on player 1's next turn the Lions could pay {T} and {2}, but it is a new "
                                "object, not a Food")
    t.run()


def test_a_sacrificed_food_can_be_returned_again():
    second = card(SupperForSpiders)
    t, supper, lions = _killed_lions(hand=[second], mana={ManaType.BLACK: 1, ManaType.COLORLESS: 3})
    _supper(t, supper, [lions])
    t.act(0, FOOD, then=[moves(lions, Zone.GRAVEYARD), on_stack(FOOD, 0)])
    _resolve(t, then=[off_stack(FOOD), life(0, 23)])
    _supper(t, second, [lions])
    t.run()


def test_an_opponents_card_dying_under_the_casters_control_returns():
    """Player 0 steals player 1's Lions with Involuntary Employment, and it
    dies under player 0's control: it goes to player 1's graveyard and
    returns."""
    lions, employment, bolt = card(SavannahLions), card(InvoluntaryEmployment), card(BurstLightning)
    game, supper = _game(hand=[employment, bolt], mana={ManaType.RED: 2, ManaType.COLORLESS: 3},
                         seat1_battlefield=[lions])
    t = Table(game)
    t.act(0, employment, choices=[lions], then=[moves(employment, Zone.STACK)])
    _resolve(t, then=[moves(employment, Zone.GRAVEYARD), gains_control(lions, 0), appears(0)],
             note="Involuntary Employment also makes a Treasure")
    _bolt(t, bolt, lions)
    _supper(t, supper, [lions])
    t.run()


def test_a_returned_card_keeps_its_other_abilities():
    """Llanowar Elves returns as a Food that can still tap for {G} — at once,
    since summoning sickness only stops creatures — and the {G} casts Giant
    Growth."""
    elves, bolt, growth = card(LlanowarElves), card(BurstLightning), card(GiantGrowth)
    target = card(SavannahLions)
    game, supper = _game(hand=[bolt, growth], battlefield=[target], mana={ManaType.RED: 1},
                         seat1_battlefield=[elves])
    t = Table(game)
    _bolt(t, bolt, elves)
    _supper(t, supper, [elves])
    t.act(0, LlanowarElvesAbility1, then=[taps(elves)])
    t.act(0, growth, choices=[target], then=[moves(growth, Zone.STACK)])
    _resolve(t, then=[moves(growth, Zone.GRAVEYARD)])
    t.run()
