"""Glamdring, Foe-hammer // Gleam of Death, played at the table.

Glamdring is an Adventure card: it may be cast as the Equipment or as its
Adventure, Gleam of Death, which shows on the stack as its own face. An engine
may offer each face as its own action or offer the card and then ask which
face to cast, so a script that casts a face names the face first and the card
second: whichever way the engine asks, the face is chosen.

A resolved Gleam of Death exiles the card, and only the Equipment may then be
cast from that exile.
"""

from card_impl import GlamdringFoehammer, GlamdringFoehammerAbility2, GleamOfDeath
from cards.fdn.fdn_43.card_impl import InspirationFromBeyond
from cards.fdn.fdn_79.card_impl import Boltwave
from cards.fdn.fdn_86.card_impl import FieryAnnihilation
from cards.fdn.fdn_90.card_impl import IncineratingBlast
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_160.card_impl import AnOfferYouCantRefuse
from cards.fdn.fdn_165.card_impl import ThinkTwice
from cards.fdn.fdn_184.card_impl import RuneScarredDemon
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_223.card_impl import GiantGrowth
from cards.fdn.fdn_248.card_impl import ThousandYearStorm, ThousandYearStormAbility1
from cards.fdn.fdn_250.card_impl import BurnishedHart
from cards.fdn.fdn_272.card_impl import Plains
from test_interface import ManaType, Phase, Side, Step, Zone, branch, card, create_game, player, spell_copy

from table import Table, appears, copied, life, moves, off_stack, on_stack, taps

MAIN = (Phase.PRECOMBAT_MAIN, 0)
GLEAM_MANA = {ManaType.BLUE: 1, ManaType.COLORLESS: 3}
EQUIPMENT_MANA = {ManaType.COLORLESS: 2}


def offers_gleam(query) -> bool:
    """A question that offers Gleam of Death among its options, such as which
    face of the card to cast."""
    return any(dict(getattr(option, "attrs", ())).get("printed") is GleamOfDeath for option in query.options)


def _plains(n: int = 3) -> list:
    return [card(Plains) for _ in range(n)]


def _game(*, hand=(), library=None, battlefield=(), graveyard=(), mana=None, seat1: Side | None = None,
          start=MAIN):
    glamdring = card(GlamdringFoehammer)
    game = create_game(
        Side(hand=[glamdring, *hand], library=_plains() if library is None else list(library),
             battlefield=list(battlefield), graveyard=list(graveyard), mana=dict(mana or {})),
        seat1 or Side(library=_plains()),
        start=start,
    )
    return game, glamdring


def _cast_gleam(t: Table, glamdring, *, then=()) -> None:
    """Player 0 casts Gleam of Death; it shows on the stack as its own face."""
    t.act(0, GleamOfDeath, glamdring, then=[moves(glamdring, Zone.STACK, face=GleamOfDeath), *then])


def _resolve(t: Table, *, then=(), note: str = "") -> None:
    t.pass_(0)
    t.pass_(1, then=list(then), note=note)


def _gleam_resolves(t: Table, glamdring, library, *, recovered=(), then=()) -> None:
    """Gleam of Death resolves: the top six cards are milled, the instants
    and sorceries among them go to hand, and the card goes to exile."""
    milled = library[:6]
    _resolve(t, then=[
        *(moves(c, Zone.HAND if c in recovered else Zone.GRAVEYARD) for c in milled),
        moves(glamdring, Zone.EXILE), *then,
    ])


def test_the_equipment_face_is_cast_as_an_artifact_without_milling():
    library = _plains(7)
    game, glamdring = _game(library=library, mana=EQUIPMENT_MANA)
    t = Table(game)
    t.act(0, GlamdringFoehammer, glamdring, then=[moves(glamdring, Zone.STACK)])
    _resolve(t, then=[moves(glamdring, Zone.BATTLEFIELD)], note="nothing is milled")
    t.run()


def test_gleam_of_death_mills_six_and_recovers_only_instants_and_sorceries():
    wave, bolt, lions = card(Boltwave), card(BurstLightning), card(SavannahLions)
    library = [wave, card(Plains), bolt, lions, card(Plains), card(Plains), card(Plains)]
    game, glamdring = _game(library=library, mana=GLEAM_MANA)
    t = Table(game)
    _cast_gleam(t, glamdring)
    _gleam_resolves(t, glamdring, library, recovered=(wave, bolt))
    t.run()


def test_gleam_of_death_does_not_recover_spells_already_in_the_graveyard():
    old = card(ThinkTwice)
    library = _plains(7)
    game, glamdring = _game(library=library, graveyard=[old], mana=GLEAM_MANA)
    t = Table(game)
    _cast_gleam(t, glamdring)
    _gleam_resolves(t, glamdring, library)
    t.run()


def test_gleam_of_death_mills_a_short_library_without_drawing_from_it():
    """With three cards left, all three are milled and nobody loses for it;
    player 0 does lose on drawing from the empty library next turn."""
    wave = card(Boltwave)
    library = [card(Plains), wave, card(Plains)]
    game, glamdring = _game(library=library, mana=GLEAM_MANA)
    t = Table(game)
    _cast_gleam(t, glamdring)
    _gleam_resolves(t, glamdring, library, recovered=(wave,))
    t.pass_to(Step.UPKEEP, 0)
    t.pass_(0)
    t.pass_(1)
    t.run()


def test_the_equipment_may_be_cast_from_the_adventure_exile():
    library = _plains(7)
    game, glamdring = _game(library=library, mana={ManaType.BLUE: 1, ManaType.COLORLESS: 5})
    t = Table(game)
    _cast_gleam(t, glamdring)
    _gleam_resolves(t, glamdring, library)
    t.act(0, GlamdringFoehammer, glamdring, then=[moves(glamdring, Zone.STACK)])
    _resolve(t, then=[moves(glamdring, Zone.BATTLEFIELD)])
    t.run()


def test_the_adventure_cannot_be_cast_again_from_its_exile():
    library = _plains(7)
    game, glamdring = _game(library=library, mana={ManaType.BLUE: 2, ManaType.COLORLESS: 6})
    t = Table(game)
    _cast_gleam(t, glamdring)
    _gleam_resolves(t, glamdring, library)
    t.act_illegal(0, GleamOfDeath, note="only the Equipment may be cast from this exile")
    t.act(0, branches=[branch(GlamdringFoehammer, glamdring, per_query={offers_gleam: [GleamOfDeath]}),
                       branch(GlamdringFoehammer, glamdring)],
          then=[moves(glamdring, Zone.STACK)],
          note="asked which face to cast, player 0 tries Gleam of Death first; only the Equipment is cast")
    _resolve(t, then=[moves(glamdring, Zone.BATTLEFIELD)])
    t.run()


def test_the_exile_permission_lasts_into_later_turns():
    library = _plains(7)
    lands = [card(Plains), card(Plains)]
    game, glamdring = _game(library=library, mana=GLEAM_MANA, battlefield=lands)
    t = Table(game)
    _cast_gleam(t, glamdring)
    _gleam_resolves(t, glamdring, library)
    t.pass_to(Phase.PRECOMBAT_MAIN, 0)
    for land in lands:
        t.act(0, land, then=[taps(land)])
    t.act(0, GlamdringFoehammer, glamdring, then=[moves(glamdring, Zone.STACK)])
    _resolve(t, then=[moves(glamdring, Zone.BATTLEFIELD)])
    t.run()


def test_a_countered_gleam_of_death_goes_to_the_graveyard_and_cannot_be_cast():
    library = _plains(7)
    offer = card(AnOfferYouCantRefuse)
    game, glamdring = _game(library=library, mana={ManaType.BLUE: 1, ManaType.COLORLESS: 5},
                            seat1=Side(hand=[offer], library=_plains(), mana={ManaType.BLUE: 1}))
    t = Table(game)
    _cast_gleam(t, glamdring)
    t.pass_(0)
    t.act(1, offer, choices=[GleamOfDeath], then=[moves(offer, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(offer, Zone.GRAVEYARD), moves(glamdring, Zone.GRAVEYARD), appears(0), appears(0)],
            note="countered, Gleam of Death is not exiled; nothing is milled")
    t.act_illegal(0, GlamdringFoehammer, note="the card is in the graveyard, not on an adventure")
    t.run()


def test_an_equipment_cast_from_the_adventure_exile_and_countered_cannot_be_cast_again():
    library = _plains(7)
    offer = card(AnOfferYouCantRefuse)
    game, glamdring = _game(library=library, mana={ManaType.BLUE: 1, ManaType.COLORLESS: 7},
                            seat1=Side(hand=[offer], library=_plains(), mana={ManaType.BLUE: 1}))
    t = Table(game)
    _cast_gleam(t, glamdring)
    _gleam_resolves(t, glamdring, library)
    t.act(0, GlamdringFoehammer, glamdring, then=[moves(glamdring, Zone.STACK)])
    t.pass_(0)
    t.act(1, offer, choices=[GlamdringFoehammer], then=[moves(offer, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(offer, Zone.GRAVEYARD), moves(glamdring, Zone.GRAVEYARD), appears(0), appears(0)])
    t.act_illegal(0, GlamdringFoehammer, note="the permission ended when the card left exile")
    t.run()


def test_an_unaffordable_adventure_leaves_the_card_in_hand_and_the_equipment_can_be_cast_instead():
    """With only {2}, Gleam of Death cannot be paid; the script's fallback
    casts the Equipment, however the engine presents the two faces."""
    library = _plains(7)
    game, glamdring = _game(library=library, mana=EQUIPMENT_MANA)
    t = Table(game)
    t.act(0, branches=[branch(GleamOfDeath, glamdring), branch(GlamdringFoehammer, glamdring)],
          then=[moves(glamdring, Zone.STACK)])
    _resolve(t, then=[moves(glamdring, Zone.BATTLEFIELD)])
    t.run()


def test_an_unaffordable_cast_changes_nothing():
    library = _plains(7)
    game, glamdring = _game(library=library, mana={ManaType.COLORLESS: 1})
    t = Table(game)
    t.act_illegal(0, GleamOfDeath, glamdring, note="{3}{U} is not paid from {1}")
    t.act_illegal(0, GlamdringFoehammer, glamdring, note="nor {2}")
    t.run()


def test_gleam_of_death_has_sorcery_timing():
    """Player 0 holds priority in player 1's upkeep and cannot cast Gleam of
    Death, nor the Equipment."""
    library = _plains(7)
    game, glamdring = _game(library=library, mana=GLEAM_MANA, start=(Step.UPKEEP, 1))
    t = Table(game)
    t.pass_(1)
    t.act_illegal(0, GleamOfDeath, glamdring)
    t.act_illegal(0, GlamdringFoehammer, glamdring)
    t.run()


def test_gleam_of_death_cannot_be_cast_while_a_spell_is_on_the_stack():
    library = _plains(7)
    bolt = card(BurstLightning)
    game, glamdring = _game(library=library, hand=[bolt], mana={**GLEAM_MANA, ManaType.RED: 1})
    t = Table(game)
    t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK)])
    t.act_illegal(0, GleamOfDeath, glamdring)
    _resolve(t, then=[moves(bolt, Zone.GRAVEYARD), life(1, 18)])
    t.run()


# -- the Equipment ------------------------------------------------------------


def _equipped(creature=SavannahLions, *, hand=(), mana=None, seat1=None):
    """Glamdring and a creature on player 0's battlefield; player 0 equips it."""
    glamdring, lions = card(GlamdringFoehammer), card(creature)
    game = create_game(
        Side(battlefield=[glamdring, lions], hand=list(hand), library=_plains(),
             mana={ManaType.COLORLESS: 2, **(mana or {})}),
        seat1 or Side(library=_plains()),
        start=MAIN,
    )
    t = Table(game)
    t.act(0, GlamdringFoehammerAbility2, choices=[lions], then=[on_stack(GlamdringFoehammerAbility2, 0)])
    _resolve(t, then=[off_stack(GlamdringFoehammerAbility2)])
    return t, glamdring, lions


def test_the_equipped_creatures_power_reduces_an_instants_generic_cost():
    """Savannah Lions has power 2, so Think Twice ({1}{U}) costs {U}."""
    think = card(ThinkTwice)
    t, _, _ = _equipped(hand=[think], mana={ManaType.BLUE: 1})
    t.act(0, think, then=[moves(think, Zone.STACK)])
    _resolve(t, then=[moves(think, Zone.GRAVEYARD), moves(t.expected.players[0].library[0].handle, Zone.HAND)])
    t.run()


def test_the_discount_reduces_a_sorcerys_generic_cost():
    """Inspiration from Beyond ({2}{U}) costs {U}."""
    inspiration = card(InspirationFromBeyond)
    t, _, _ = _equipped(hand=[inspiration], mana={ManaType.BLUE: 1})
    library = [s.handle for s in t.expected.players[0].library]
    t.act(0, inspiration, then=[moves(inspiration, Zone.STACK)])
    t.pass_(0, choices=[inspiration])
    t.pass_(1, then=[*(moves(h, Zone.GRAVEYARD) for h in library), moves(inspiration, Zone.GRAVEYARD)],
            note="three Plains are milled; there is no instant or sorcery to return")
    t.run()


def test_without_the_discount_the_same_spell_cannot_be_paid():
    think = card(ThinkTwice)
    glamdring, lions = card(GlamdringFoehammer), card(SavannahLions)
    game = create_game(
        Side(battlefield=[glamdring, lions], hand=[think], library=_plains(), mana={ManaType.BLUE: 1}),
        Side(library=_plains()),
        start=MAIN,
    )
    t = Table(game)
    t.act_illegal(0, think, note="Glamdring is not attached to anything")
    t.run()


def test_the_discount_does_not_reduce_colored_mana():
    """Boltwave costs {R}: equipped power 2 does not pay it from no red."""
    wave = card(Boltwave)
    t, _, _ = _equipped(hand=[wave])
    t.act_illegal(0, wave)
    t.run()


def test_the_discount_does_not_apply_to_creature_spells():
    """Burnished Hart costs {3}: the {1} left after equipping would pay it
    only if equipped power 2 discounted it."""
    hart = card(BurnishedHart)
    t, _, _ = _equipped(hand=[hart], mana={ManaType.COLORLESS: 3})
    t.act_illegal(0, hart)
    t.run()


def test_the_discount_does_not_apply_to_the_opponents_spells():
    think = card(ThinkTwice)
    t, _, _ = _equipped(seat1=Side(hand=[think], library=_plains(), mana={ManaType.BLUE: 1}))
    t.pass_(0)
    t.act_illegal(1, think)
    t.run()


def test_the_discount_follows_the_equipped_creatures_current_power():
    """Incinerating Blast ({4}{R}) costs {2}{R} with the 2-power Lions
    equipped, more than {G}{R} pays; once Giant Growth makes the Lions 5/4
    it costs {R}."""
    growth, blast = card(GiantGrowth), card(IncineratingBlast)
    target = card(SavannahLions)
    t, _, lions = _equipped(hand=[growth, blast], mana={ManaType.GREEN: 1, ManaType.RED: 1},
                            seat1=Side(battlefield=[target], library=_plains()))
    t.act_illegal(0, blast, choices=[target])
    t.act(0, growth, choices=[lions], then=[moves(growth, Zone.STACK)])
    _resolve(t, then=[moves(growth, Zone.GRAVEYARD)])
    t.act(0, blast, choices=[target], then=[moves(blast, Zone.STACK)])
    _resolve(t, then=[moves(blast, Zone.GRAVEYARD), moves(target, Zone.GRAVEYARD)])
    t.run()


def test_a_glamdring_no_longer_attached_gives_no_discount():
    """The equipped Lions dies to Burst Lightning; Think Twice then costs
    {1}{U} again."""
    think, bolt = card(ThinkTwice), card(BurstLightning)
    t, _, lions = _equipped(hand=[think], mana={ManaType.BLUE: 1},
                            seat1=Side(hand=[bolt], library=_plains(), mana={ManaType.RED: 1}))
    t.pass_(0)
    t.act(1, bolt, choices=[lions], then=[moves(bolt, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD)])
    t.act_illegal(0, think)
    t.run()


def test_an_equipment_exiled_by_another_effect_cannot_be_cast():
    """Fiery Annihilation exiles the attached Glamdring (its 6/6 bearer
    survives); only Gleam of Death's own exile lets the card be cast."""
    blast = card(FieryAnnihilation)
    t, glamdring, demon = _equipped(RuneScarredDemon, mana={ManaType.COLORLESS: 4},
                                    seat1=Side(hand=[blast], library=_plains(), mana={ManaType.RED: 3}))
    t.pass_(0)
    t.act(1, blast, choices=[demon, glamdring], then=[moves(blast, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(blast, Zone.GRAVEYARD), moves(glamdring, Zone.EXILE)])
    t.act_illegal(0, GlamdringFoehammer, glamdring, note="{2} is still in the pool")
    t.run()


def test_equip_cannot_target_an_opponents_creature():
    """With no creature of its own, player 0's equip has nothing it may
    target; player 1's Lions is not one."""
    glamdring, theirs = card(GlamdringFoehammer), card(SavannahLions)
    game = create_game(
        Side(battlefield=[glamdring], library=_plains(), mana=EQUIPMENT_MANA),
        Side(battlefield=[theirs], library=_plains()),
        start=MAIN,
    )
    t = Table(game)
    t.act_illegal(0, GlamdringFoehammerAbility2, choices=[theirs])
    t.run()


def test_equip_has_sorcery_timing():
    """In player 0's beginning of combat step, equip cannot be activated."""
    glamdring, lions = card(GlamdringFoehammer), card(SavannahLions)
    game = create_game(
        Side(battlefield=[glamdring, lions], library=_plains(), mana=EQUIPMENT_MANA),
        Side(library=_plains()),
        start=(Step.BEGIN_COMBAT, 0),
    )
    t = Table(game)
    t.act_illegal(0, GlamdringFoehammerAbility2, choices=[lions])
    t.run()


def _stormed_gleam(*, seat1: Side | None = None):
    """Player 0, with Thousand-Year Storm, casts Boltwave and then Gleam of
    Death, so Storm copies Gleam of Death once. The copy is a spell of its own
    on top of the original: it has its own number, not Glamdring's handle."""
    library = _plains(12)
    wave = card(Boltwave)
    game, glamdring = _game(hand=[wave], library=library, battlefield=[card(ThousandYearStorm)],
                            mana={ManaType.BLUE: 1, ManaType.COLORLESS: 5, ManaType.RED: 1},
                            seat1=seat1)
    t = Table(game)
    t.act(0, wave, then=[moves(wave, Zone.STACK), on_stack(ThousandYearStormAbility1, 0)])
    _resolve(t, then=[off_stack(ThousandYearStormAbility1)], note="no spell was cast before Boltwave")
    _resolve(t, then=[moves(wave, Zone.GRAVEYARD), life(1, 17)])
    _cast_gleam(t, glamdring, then=[on_stack(ThousandYearStormAbility1, 0)])
    _resolve(t, then=[off_stack(ThousandYearStormAbility1), copied(GleamOfDeath, 0)])
    return t, glamdring, library


def _offer() -> tuple:
    offer = card(AnOfferYouCantRefuse)
    return offer, Side(hand=[offer], library=_plains(), mana={ManaType.BLUE: 1})


def test_a_copy_of_gleam_of_death_resolves_without_moving_the_card():
    """The copy mills six and ceases to exist; Glamdring stays on the stack
    until its own Gleam of Death resolves and exiles it."""
    t, glamdring, library = _stormed_gleam()
    _resolve(t, then=[off_stack(GleamOfDeath), *(moves(c, Zone.GRAVEYARD) for c in library[:6])],
             note="the copy resolves: six milled, the card stays on the stack")
    _resolve(t, then=[*(moves(c, Zone.GRAVEYARD) for c in library[6:]), moves(glamdring, Zone.EXILE)])
    t.act(0, GlamdringFoehammer, glamdring, note="the Equipment may be cast from the Adventure's exile",
          then=[moves(glamdring, Zone.STACK)])
    t.run()


def test_countering_only_the_copy_leaves_the_original_gleam_of_death():
    offer, seat1 = _offer()
    t, glamdring, library = _stormed_gleam(seat1=seat1)
    t.pass_(0)
    t.act(1, offer, choices=[spell_copy(1)], then=[moves(offer, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(offer, Zone.GRAVEYARD), off_stack(GleamOfDeath), appears(0), appears(0)],
            note="the copy is countered and ceases to exist; Glamdring is still on the stack")
    _gleam_resolves(t, glamdring, library)
    t.run()


def test_countering_only_the_original_leaves_the_copy():
    offer, seat1 = _offer()
    t, glamdring, library = _stormed_gleam(seat1=seat1)
    t.pass_(0)
    t.act(1, offer, choices=[glamdring], then=[moves(offer, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(offer, Zone.GRAVEYARD), moves(glamdring, Zone.GRAVEYARD), appears(0), appears(0)],
            note="the original is countered: Glamdring goes to the graveyard, not on an adventure")
    _resolve(t, then=[off_stack(GleamOfDeath), *(moves(c, Zone.GRAVEYARD) for c in library[:6])],
             note="the copy still resolves")
    t.act_illegal(0, GlamdringFoehammer, note="the card is in the graveyard, not on an adventure")
    t.run()

