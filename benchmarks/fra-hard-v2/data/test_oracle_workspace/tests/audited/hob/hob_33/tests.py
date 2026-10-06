"""Bilbo, Thief in the Night, played at the table.

Bilbo attacks from player 0's beginning of combat; its trigger offers one
artifact, instant or sorcery card in player 0's graveyard to cast. Mana pools
empty between steps, so the caster taps lands while the trigger waits. Bilbo's
discount shows in what a given amount of mana can pay for, and its exile
replacement in where the spell goes afterwards.
"""

from card_impl import BilboThiefInTheNight, BilboThiefInTheNightAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_160.card_impl import AnOfferYouCantRefuse
from cards.fdn.fdn_165.card_impl import ThinkTwice
from cards.fdn.fdn_175.card_impl import HerosDownfall
from cards.fdn.fdn_181.card_impl import Pilfer
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_250.card_impl import BurnishedHart
from cards.fdn.fdn_258.card_impl import SwiftfootBoots
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_276.card_impl import Swamp
from cards.fdn.fdn_278.card_impl import Mountain
from cards.hob.hob_174.card_impl import GlamdringFoehammer, GleamOfDeath
from test_interface import ManaType, Phase, Side, Step, Zone, branch, card, create_game, player

from silverquillm.table import Table, appears, life, moves, off_stack, on_stack, taps

TRIGGER = BilboThiefInTheNightAbility2
COMBAT = (Step.BEGIN_COMBAT, 0)
MAIN = (Phase.PRECOMBAT_MAIN, 0)


def _plains(n: int = 3) -> list:
    return [card(Plains) for _ in range(n)]


def _game(*, graveyard=(), lands=(), battlefield=(), hand=(), mana=None, seat1: Side | None = None, start=COMBAT):
    bilbo = card(BilboThiefInTheNight)
    game = create_game(
        Side(battlefield=[bilbo, *lands, *battlefield], graveyard=list(graveyard), hand=list(hand),
             library=_plains(), mana=dict(mana or {})),
        seat1 or Side(library=_plains()),
        start=start,
    )
    return game, bilbo


def _attack(t: Table, *attackers) -> None:
    """Player 0 moves to combat and attacks with ``attackers``."""
    t.pass_(0)
    t.pass_(1)
    t.act(0, *attackers, then=[taps(a) for a in attackers]
          + [on_stack(TRIGGER, 0) for a in attackers if a is t.bilbo])


def _tap(t: Table, lands) -> None:
    for land in lands:
        t.act(0, land, then=[taps(land)])


def _resolve(t: Table, *, then=(), note: str = "", **options) -> None:
    t.pass_(0, **options)
    t.pass_(1, then=list(then), note=note)


def _table(game, bilbo) -> Table:
    t = Table(game)
    t.bilbo = bilbo
    return t


def test_an_instant_from_the_graveyard_costs_one_less_and_is_exiled():
    """Hero's Downfall ({1}{B}{B}) is cast for {B}{B} and exiled after it resolves."""
    downfall, theirs = card(HerosDownfall), card(SavannahLions)
    lands = [card(Swamp), card(Swamp)]
    game, bilbo = _game(graveyard=[downfall], lands=lands, seat1=Side(battlefield=[theirs], library=_plains()))
    t = _table(game, bilbo)
    _attack(t, bilbo)
    _tap(t, lands)
    _resolve(t, choices=[downfall, theirs], then=[off_stack(TRIGGER), moves(downfall, Zone.STACK)])
    _resolve(t, then=[moves(downfall, Zone.EXILE), moves(theirs, Zone.GRAVEYARD)])
    t.run()


def test_a_sorcery_is_cast_during_combat_and_exiled():
    """Pilfer ({1}{B}) is cast for {B} in the declare attackers step."""
    pilfer, bolt = card(Pilfer), card(BurstLightning)
    swamp = card(Swamp)
    game, bilbo = _game(graveyard=[pilfer], lands=[swamp], seat1=Side(hand=[bolt], library=_plains()))
    t = _table(game, bilbo)
    _attack(t, bilbo)
    _tap(t, [swamp])
    _resolve(t, choices=[pilfer, player(1)], then=[off_stack(TRIGGER), moves(pilfer, Zone.STACK)])
    _resolve(t, choices=[bolt], then=[moves(pilfer, Zone.EXILE), moves(bolt, Zone.GRAVEYARD)])
    t.run()


def test_an_artifact_creature_is_cast_and_stays_on_the_battlefield():
    """Burnished Hart ({3}) is cast for {2}; an artifact is not exiled."""
    hart = card(BurnishedHart)
    lands = [card(Plains), card(Plains)]
    game, bilbo = _game(graveyard=[hart], lands=lands)
    t = _table(game, bilbo)
    _attack(t, bilbo)
    _tap(t, lands)
    _resolve(t, choices=[hart], then=[off_stack(TRIGGER), moves(hart, Zone.STACK)])
    _resolve(t, then=[moves(hart, Zone.BATTLEFIELD)])
    t.run()


def test_a_noncreature_artifact_is_cast_onto_the_battlefield():
    boots = card(SwiftfootBoots)
    plains = card(Plains)
    game, bilbo = _game(graveyard=[boots], lands=[plains])
    t = _table(game, bilbo)
    _attack(t, bilbo)
    _tap(t, [plains])
    _resolve(t, choices=[boots], then=[off_stack(TRIGGER), moves(boots, Zone.STACK)])
    _resolve(t, then=[moves(boots, Zone.BATTLEFIELD)])
    t.run()


def test_a_creature_card_is_not_offered():
    lions = card(SavannahLions)
    plains = card(Plains)
    game, bilbo = _game(graveyard=[lions], lands=[plains])
    t = _table(game, bilbo)
    _attack(t, bilbo)
    _tap(t, [plains])
    _resolve(t, branches=[branch(choices=[lions]), branch()], then=[off_stack(TRIGGER)],
             note="the Lions stays in the graveyard, whether or not it is offered and rejected")
    t.run()


def test_the_opponents_graveyard_is_not_offered():
    downfall, lions = card(HerosDownfall), card(SavannahLions)
    lands = [card(Swamp), card(Swamp)]
    game, bilbo = _game(lands=lands, seat1=Side(graveyard=[downfall], battlefield=[lions], library=_plains()))
    t = _table(game, bilbo)
    _attack(t, bilbo)
    _tap(t, lands)
    _resolve(t, branches=[branch(choices=[downfall, lions]), branch()], then=[off_stack(TRIGGER)],
             note="the opponent's Hero's Downfall stays put, whether or not it is offered and rejected")
    t.run()


def test_the_cast_may_be_declined():
    downfall, theirs = card(HerosDownfall), card(SavannahLions)
    lands = [card(Swamp), card(Swamp)]
    game, bilbo = _game(graveyard=[downfall], lands=lands, seat1=Side(battlefield=[theirs], library=_plains()))
    t = _table(game, bilbo)
    _attack(t, bilbo)
    _tap(t, lands)
    _resolve(t, then=[off_stack(TRIGGER)], note="Hero's Downfall stays in the graveyard")
    t.run()


def test_the_discount_does_not_reduce_colored_mana():
    """With {B} and {W}, Hero's Downfall's {B}{B} cannot be paid: the cast is
    refused and the script falls back to declining."""
    downfall, theirs = card(HerosDownfall), card(SavannahLions)
    lands = [card(Swamp), card(Plains)]
    game, bilbo = _game(graveyard=[downfall], lands=lands, seat1=Side(battlefield=[theirs], library=_plains()))
    t = _table(game, bilbo)
    _attack(t, bilbo)
    _tap(t, lands)
    _resolve(t, branches=[branch(choices=[downfall, theirs]), branch()], then=[off_stack(TRIGGER)])
    t.run()


def test_only_one_spell_is_cast():
    downfall, pilfer, theirs = card(HerosDownfall), card(Pilfer), card(SavannahLions)
    lands = [card(Swamp), card(Swamp), card(Swamp)]
    game, bilbo = _game(graveyard=[downfall, pilfer], lands=lands,
                        seat1=Side(battlefield=[theirs], hand=[card(Plains)], library=_plains()))
    t = _table(game, bilbo)
    _attack(t, bilbo)
    _tap(t, lands)
    _resolve(t, choices=[downfall, theirs, pilfer, player(1)],
             then=[off_stack(TRIGGER), moves(downfall, Zone.STACK)], note="Pilfer is not cast as well")
    _resolve(t, then=[moves(downfall, Zone.EXILE), moves(theirs, Zone.GRAVEYARD)])
    t.run()


def test_another_attacker_does_not_trigger_bilbo():
    lions, downfall = card(SavannahLions), card(HerosDownfall)
    game, bilbo = _game(graveyard=[downfall], battlefield=[lions])
    t = _table(game, bilbo)
    _attack(t, lions)
    t.pass_(0)
    t.pass_(1, note="nothing triggered")
    t.run()


def test_graveyard_cards_cannot_be_cast_outside_the_trigger():
    pilfer = card(Pilfer)
    game, bilbo = _game(graveyard=[pilfer], hand=[], mana={ManaType.BLACK: 2}, start=MAIN)
    t = _table(game, bilbo)
    t.act_illegal(0, pilfer, choices=[player(1)])
    t.run()


def test_a_countered_instant_cast_this_way_is_exiled():
    downfall, theirs, offer = card(HerosDownfall), card(SavannahLions), card(AnOfferYouCantRefuse)
    lands, island = [card(Swamp), card(Swamp)], card(Island)
    game, bilbo = _game(graveyard=[downfall], lands=lands,
                        seat1=Side(battlefield=[theirs, island], hand=[offer], library=_plains()))
    t = _table(game, bilbo)
    _attack(t, bilbo)
    _tap(t, lands)
    _resolve(t, choices=[downfall, theirs], then=[off_stack(TRIGGER), moves(downfall, Zone.STACK)])
    t.pass_(0)
    t.act(1, island, then=[taps(island)])
    t.act(1, offer, choices=[downfall], then=[moves(offer, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(offer, Zone.GRAVEYARD), moves(downfall, Zone.EXILE), appears(0), appears(0)])
    t.run()


def test_the_trigger_resolves_without_bilbo_but_without_the_discount():
    """Player 1 kills Bilbo in response; the trigger still offers the cast,
    but Hero's Downfall now costs {1}{B}{B}, more than {B}{B}."""
    downfall, theirs, bolt, mountain = card(HerosDownfall), card(SavannahLions), card(BurstLightning), card(Mountain)
    lands = [card(Swamp), card(Swamp)]
    game, bilbo = _game(graveyard=[downfall], lands=lands,
                        seat1=Side(battlefield=[theirs, mountain], hand=[bolt], library=_plains()))
    t = _table(game, bilbo)
    _attack(t, bilbo)
    _tap(t, lands)
    t.pass_(0)
    t.act(1, mountain, then=[taps(mountain)])
    t.act(1, bolt, choices=[bilbo], then=[moves(bolt, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD), moves(bilbo, Zone.GRAVEYARD)])
    _resolve(t, branches=[branch(choices=[downfall, theirs]), branch()], then=[off_stack(TRIGGER)],
             note="the cast cannot be paid")
    t.run()


def test_with_one_more_mana_the_trigger_resolves_without_bilbo():
    downfall, theirs, bolt, mountain = card(HerosDownfall), card(SavannahLions), card(BurstLightning), card(Mountain)
    lands = [card(Swamp), card(Swamp), card(Plains)]
    game, bilbo = _game(graveyard=[downfall], lands=lands,
                        seat1=Side(battlefield=[theirs, mountain], hand=[bolt], library=_plains()))
    t = _table(game, bilbo)
    _attack(t, bilbo)
    _tap(t, lands)
    t.pass_(0)
    t.act(1, mountain, then=[taps(mountain)])
    t.act(1, bolt, choices=[bilbo], then=[moves(bolt, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD), moves(bilbo, Zone.GRAVEYARD)])
    _resolve(t, choices=[downfall, theirs], then=[off_stack(TRIGGER), moves(downfall, Zone.STACK)])
    _resolve(t, then=[moves(downfall, Zone.EXILE), moves(theirs, Zone.GRAVEYARD)])
    t.run()


def test_spells_cast_from_hand_get_no_discount():
    downfall, theirs = card(HerosDownfall), card(SavannahLions)
    game, bilbo = _game(hand=[downfall], mana={ManaType.BLACK: 2}, start=MAIN,
                        seat1=Side(battlefield=[theirs], library=_plains()))
    t = _table(game, bilbo)
    t.act_illegal(0, downfall, choices=[theirs])
    t.run()


def test_a_flashback_cast_gets_the_discount():
    """Think Twice's flashback ({2}{U}) is paid with {1}{U} while Bilbo is on
    the battlefield."""
    think = card(ThinkTwice)
    game, bilbo = _game(graveyard=[think], mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1}, start=MAIN)
    t = _table(game, bilbo)
    t.act(0, think, then=[moves(think, Zone.STACK)])
    _resolve(t, then=[moves(think, Zone.EXILE), moves(t.expected.players[0].library[0].handle, Zone.HAND)])
    t.run()


def test_the_opponents_flashback_gets_no_discount():
    think = card(ThinkTwice)
    game, bilbo = _game(start=MAIN, seat1=Side(graveyard=[think], library=_plains(),
                                               mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1}))
    t = _table(game, bilbo)
    t.pass_(0)
    t.act_illegal(1, think)
    t.run()


def test_bilbo_still_deals_combat_damage():
    """The trigger declined, Bilbo connects for 2."""
    game, bilbo = _game()
    t = _table(game, bilbo)
    _attack(t, bilbo)
    _resolve(t, then=[off_stack(TRIGGER)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, 18)])
    t.run()


def _gleam_then_glamdring(with_bilbo: bool, mana: dict) -> Table:
    """Player 0 casts Gleam of Death from hand; once it resolves, Glamdring is
    in exile and may be cast from there."""
    glamdring = card(GlamdringFoehammer)
    library = _plains(7)
    game = create_game(
        Side(hand=[glamdring], battlefield=[BilboThiefInTheNight] if with_bilbo else [], library=library, mana=mana),
        Side(library=_plains()),
        start=MAIN,
    )
    t = Table(game)
    t.glamdring = glamdring
    t.act(0, GleamOfDeath, glamdring, then=[moves(glamdring, Zone.STACK, face=GleamOfDeath)],
          note="cast from hand, it gets no discount")
    _resolve(t, then=[*(moves(c, Zone.GRAVEYARD) for c in library[:6]), moves(glamdring, Zone.EXILE)])
    return t


def test_an_adventure_card_cast_from_exile_gets_the_discount():
    """Glamdring ({2}) is cast from the exile Gleam of Death left it in for {1}."""
    t = _gleam_then_glamdring(True, {ManaType.BLUE: 1, ManaType.COLORLESS: 4})
    t.act(0, GlamdringFoehammer, t.glamdring, then=[moves(t.glamdring, Zone.STACK)])
    _resolve(t, then=[moves(t.glamdring, Zone.BATTLEFIELD)])
    t.run()


def test_without_bilbo_the_same_mana_does_not_cast_it():
    t = _gleam_then_glamdring(False, {ManaType.BLUE: 1, ManaType.COLORLESS: 4})
    t.act_illegal(0, GlamdringFoehammer, t.glamdring, note="{2} is not paid from {1}")
    t.run()


def test_the_adventure_is_not_cast_again_from_its_own_exile_even_with_the_discount():
    """With Bilbo's discount, {2}{U} would pay Gleam of Death from exile, but
    only the Equipment may be cast from the exile its Adventure left it in."""
    t = _gleam_then_glamdring(True, {ManaType.BLUE: 2, ManaType.COLORLESS: 5})
    t.act_illegal(0, GleamOfDeath, note="only the Equipment may be cast from this exile")
    t.act(0, GlamdringFoehammer, t.glamdring, then=[moves(t.glamdring, Zone.STACK)])
    _resolve(t, then=[moves(t.glamdring, Zone.BATTLEFIELD)])
    t.run()


def test_a_countered_adventure_cast_this_way_is_exiled_without_a_permission():
    """Bilbo casts Glamdring from the graveyard as Gleam of Death; countered, it
    is exiled by Bilbo, not by its Adventure resolving, so Glamdring may not be
    cast from there (CR 715.4)."""
    glamdring, offer = card(GlamdringFoehammer), card(AnOfferYouCantRefuse)
    lands, island, spare = [card(Island), card(Plains), card(Plains)], card(Island), [card(Plains), card(Plains)]
    game, bilbo = _game(graveyard=[glamdring], lands=[*lands, *spare],
                        seat1=Side(battlefield=[island], hand=[offer], library=_plains()))
    t = _table(game, bilbo)
    _attack(t, bilbo)
    _tap(t, lands)
    _resolve(t, choices=[GleamOfDeath, glamdring],
             then=[off_stack(TRIGGER), moves(glamdring, Zone.STACK, face=GleamOfDeath)])
    t.pass_(0)
    t.act(1, island, then=[taps(island)])
    t.act(1, offer, choices=[GleamOfDeath], then=[moves(offer, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(offer, Zone.GRAVEYARD), moves(glamdring, Zone.EXILE), appears(0), appears(0)],
            note="countered, Gleam of Death is exiled by Bilbo; nothing is milled")
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, 18)])
    t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
    _tap(t, spare)
    t.act_illegal(0, GlamdringFoehammer, note="the card was not exiled by its Adventure resolving")
    t.run()
