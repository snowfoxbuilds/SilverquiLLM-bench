"""Uldaros Theorix, played at the table.

Each test builds a position, plays it through both players' scripts and judges
Uldaros by what the players can see: which graveyard cards go to exile, which
copies are cast and what they do, and which tokens appear. A copy cast this
way shows on the stack as a spell copy of its card's class; a permanent copy
resolves into a token.

Uldaros asks for up to one target of each card type; an engine may ask those
questions in any order, offer a card already chosen again, or ask them
together, so the scripts list each card it should choose and let the branches
absorb how the questions come.
"""

from card_impl import UldarosTheorix, UldarosTheorixAbility2
from cards.fdn.fdn_9.card_impl import DazzlingAngel, DazzlingAngelAbility2
from cards.fdn.fdn_79.card_impl import Boltwave
from cards.fdn.fdn_98.card_impl import AmbushWolf, AmbushWolfAbility2
from cards.fdn.fdn_116.card_impl import AnthemOfChampions
from cards.fdn.fdn_129.card_impl import LeylineAxe
from cards.fdn.fdn_134.card_impl import AjaniCallerOfThePride, AjaniCallerOfThePrideAbility2
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_163.card_impl import SelfReflection
from cards.fdn.fdn_172.card_impl import EatenAlive, EatenAliveAbility1
from cards.fdn.fdn_173.card_impl import Exsanguinate
from cards.fdn.fdn_175.card_impl import HerosDownfall
from cards.fdn.fdn_184.card_impl import RuneScarredDemon
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_196.card_impl import FirebrandArcher, FirebrandArcherAbility1
from cards.fdn.fdn_212.card_impl import BiteDown
from cards.fdn.fdn_250.card_impl import BurnishedHart
from cards.fdn.fdn_272.card_impl import Plains
from cards.fut.fut_78.card_impl import SlaughterPact, SlaughterPactAbility2
from cards.hob.hob_174.card_impl import GlamdringFoehammer, GleamOfDeath
from test_interface import (
    Decision,
    ManaType,
    Phase,
    Side,
    Step,
    Zone,
    branch,
    card,
    create_game,
    player,
    token,
)

from table import (
    Table,
    appears,
    ceases,
    copied,
    life,
    moves,
    off_stack,
    on_stack,
    taps,
    wins,
)

MAIN = (Phase.PRECOMBAT_MAIN, 0)
TRIGGER = UldarosTheorixAbility2
ULDAROS_MANA = {ManaType.BLUE: 1, ManaType.BLACK: 2, ManaType.COLORLESS: 3}
SACRIFICE = Decision.ability(index=0, printed=EatenAliveAbility1)
PAY_MANA = Decision.ability(index=1, printed=EatenAliveAbility1)


def _library(n: int = 3) -> list:
    return [card(Plains) for _ in range(n)]


def _game(graveyard=(), *, hand=(), battlefield=(), extra_mana=None, seat1: Side | None = None, start=MAIN):
    uldaros = card(UldarosTheorix)
    mana = dict(ULDAROS_MANA)
    for kind, amount in (extra_mana or {}).items():
        mana[kind] = mana.get(kind, 0) + amount
    game = create_game(
        Side(hand=[uldaros, *hand], battlefield=list(battlefield), graveyard=list(graveyard), library=_library(),
             mana=mana),
        seat1 or Side(library=_library()),
        start=start,
    )
    return game, uldaros


def _cast_uldaros(t: Table, uldaros, targets=(), **options) -> None:
    """Player 0 casts Uldaros; it resolves, choosing ``targets`` for its trigger."""
    t.act(0, uldaros, then=[moves(uldaros, Zone.STACK)])
    if "branches" in options:
        t.pass_(0, **options)
    else:
        t.pass_(0, choices=list(targets), **options)
    t.pass_(1, then=[moves(uldaros, Zone.BATTLEFIELD), on_stack(TRIGGER, 0)])


def _resolve_trigger(t: Table, casts=(), *, then=(), note: str = "", branches=None) -> None:
    """The trigger resolves; player 0 answers its questions with ``casts``, or
    from ``branches`` when an engine may reject one of them and ask again."""
    if branches is not None:
        t.pass_(0, branches=branches)
    else:
        t.pass_(0, choices=list(casts))
    t.pass_(1, then=[off_stack(TRIGGER), *then], note=note)


def _asked_by(printed):
    """A ``per_query`` key: a question whose source is a ``printed`` object, so
    each copy's target is answered apart from the others'."""
    return lambda query: any(dict(source.attrs).get("printed") is printed for source in query.source)


def _resolve_top(t: Table, cls, *, then=()) -> None:
    t.pass_(0)
    t.pass_(1, then=[off_stack(cls), *then])


def test_a_cast_uldaros_exiles_a_creature_card_and_casts_its_copy_as_a_token():
    lions = card(SavannahLions)
    game, uldaros = _game([lions])
    t = Table(game)
    _cast_uldaros(t, uldaros, [lions])
    _resolve_trigger(t, [SavannahLions], then=[moves(lions, Zone.EXILE), copied(SavannahLions, 0)])
    _resolve_top(t, SavannahLions, then=[appears(0)])
    t.run()


def test_the_token_copy_fights_as_the_card_it_copies():
    lions = card(SavannahLions)
    game, uldaros = _game([lions], seat1=Side(library=_library()))
    t = Table(game)
    _cast_uldaros(t, uldaros, [lions])
    _resolve_trigger(t, [SavannahLions], then=[moves(lions, Zone.EXILE), copied(SavannahLions, 0)])
    _resolve_top(t, SavannahLions, then=[appears(0)])
    t.pass_to(Phase.PRECOMBAT_MAIN, 0)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, token(1), then=[taps(token(1))])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, 18)])
    t.run()


def test_an_uldaros_not_cast_does_not_exile_anything():
    """A token copy of Uldaros made by Self-Reflection enters without being
    cast, so its trigger does nothing."""
    lions, reflection, uldaros = card(SavannahLions), card(SelfReflection), card(UldarosTheorix)
    game = create_game(
        Side(hand=[reflection], battlefield=[uldaros], graveyard=[lions], library=_library(),
             mana={ManaType.BLUE: 2, ManaType.COLORLESS: 4}),
        Side(library=_library()),
        start=MAIN,
    )
    t = Table(game)
    t.act(0, reflection, choices=[uldaros], then=[moves(reflection, Zone.STACK)])
    t.pass_(0, choices=[lions, uldaros])
    t.pass_(1, then=[moves(reflection, Zone.GRAVEYARD), appears(0), ceases(token(1))],
            note="the legend rule keeps the original; the Lions stays in the graveyard")
    t.run()


def test_an_instant_copy_resolves_and_ceases_to_exist():
    bolt = card(BurstLightning)
    game, uldaros = _game([bolt])
    t = Table(game)
    _cast_uldaros(t, uldaros, [bolt])
    _resolve_trigger(t, [BurstLightning, player(1)], then=[moves(bolt, Zone.EXILE), copied(BurstLightning, 0)])
    _resolve_top(t, BurstLightning, then=[life(1, 18)])
    t.run()


def test_one_card_of_each_type_is_copied_and_cast():
    lions, bolt, wave = card(SavannahLions), card(BurstLightning), card(Boltwave)
    game, uldaros = _game([lions, bolt, wave])
    t = Table(game)
    _cast_uldaros(t, uldaros, [lions, bolt, wave])
    _resolve_trigger(t, [Boltwave, BurstLightning, SavannahLions, player(1)], then=[
        moves(lions, Zone.EXILE), moves(bolt, Zone.EXILE), moves(wave, Zone.EXILE),
        copied(Boltwave, 0), copied(BurstLightning, 0), copied(SavannahLions, 0),
    ])
    _resolve_top(t, SavannahLions, then=[appears(0)])
    _resolve_top(t, BurstLightning, then=[life(1, 18)])
    _resolve_top(t, Boltwave, then=[life(1, 15)])
    t.run()


def test_only_one_card_of_a_type_is_exiled():
    first, second = card(SavannahLions), card(SavannahLions)
    game, uldaros = _game([first, second])
    t = Table(game)
    _cast_uldaros(t, uldaros, branches=[branch(choices=[first, second], distinct=True),
                                        branch(choices=[first])])
    _resolve_trigger(t, [SavannahLions], then=[moves(first, Zone.EXILE), copied(SavannahLions, 0)],
                     note="the second Lions stays in the graveyard")
    _resolve_top(t, SavannahLions, then=[appears(0)])
    t.run()


def test_the_casts_share_a_budget_of_six_mana_value():
    """A 7-mana-value creature is exiled but cannot be cast; Boltwave can. An
    engine that offers the Demon's copy rejects casting it, and player 0 then
    casts only Boltwave."""
    demon, wave = card(RuneScarredDemon), card(Boltwave)
    game, uldaros = _game([demon, wave])
    t = Table(game)
    _cast_uldaros(t, uldaros, [demon, wave])
    _resolve_trigger(t, branches=[branch(choices=[RuneScarredDemon, Boltwave]), branch(choices=[Boltwave])], then=[
        moves(demon, Zone.EXILE), moves(wave, Zone.EXILE), copied(Boltwave, 0),
    ], note="the Demon's copy is over the budget")
    _resolve_top(t, Boltwave, then=[life(1, 17)])
    t.run()


def test_exactly_six_mana_value_casts_three_spells():
    """Ajani (3) and Anthem of Champions (2) and Boltwave (1) make exactly 6."""
    ajani, anthem, wave = card(AjaniCallerOfThePride), card(AnthemOfChampions), card(Boltwave)
    game, uldaros = _game([ajani, anthem, wave])
    t = Table(game)
    _cast_uldaros(t, uldaros, [ajani, anthem, wave])
    _resolve_trigger(t, [AjaniCallerOfThePride, AnthemOfChampions, Boltwave], then=[
        moves(ajani, Zone.EXILE), moves(anthem, Zone.EXILE), moves(wave, Zone.EXILE),
        copied(AjaniCallerOfThePride, 0), copied(AnthemOfChampions, 0), copied(Boltwave, 0),
    ])
    _resolve_top(t, Boltwave, then=[life(1, 17)])
    _resolve_top(t, AnthemOfChampions, then=[appears(0)])
    _resolve_top(t, AjaniCallerOfThePride, then=[appears(0)])
    t.run()


def test_a_copy_over_the_remaining_budget_is_not_cast():
    """After Ajani (3) and Anthem (2) only 1 of the budget remains, so Hero's
    Downfall (3) is exiled but not cast. An engine that offers its copy rejects
    casting it, keeps the two casts already made, and player 0 then declines."""
    ajani, anthem, downfall = card(AjaniCallerOfThePride), card(AnthemOfChampions), card(HerosDownfall)
    game, uldaros = _game([ajani, anthem, downfall])
    t = Table(game)
    _cast_uldaros(t, uldaros, [ajani, anthem, downfall])
    _resolve_trigger(t, branches=[
        branch(choices=[AjaniCallerOfThePride, AnthemOfChampions, HerosDownfall]), branch(choices=[]),
    ], then=[
        moves(ajani, Zone.EXILE), moves(anthem, Zone.EXILE), moves(downfall, Zone.EXILE),
        copied(AjaniCallerOfThePride, 0), copied(AnthemOfChampions, 0),
    ], note="Hero's Downfall (3) no longer fits the budget")
    _resolve_top(t, AnthemOfChampions, then=[appears(0)])
    _resolve_top(t, AjaniCallerOfThePride, then=[appears(0)])
    t.run()


def test_the_opponents_graveyard_is_not_eligible():
    """An engine that offers player 1's Lions as a target rejects choosing it,
    and player 0 then chooses nothing."""
    theirs = card(SavannahLions)
    game, uldaros = _game(seat1=Side(graveyard=[theirs], library=_library()))
    t = Table(game)
    _cast_uldaros(t, uldaros, branches=[branch(choices=[theirs]), branch(choices=[])])
    _resolve_trigger(t, [SavannahLions], note="nothing of player 1's is exiled")
    t.run()


def test_targets_may_be_declined():
    lions = card(SavannahLions)
    game, uldaros = _game([lions])
    t = Table(game)
    _cast_uldaros(t, uldaros, [])
    _resolve_trigger(t, [SavannahLions], note="no target was chosen: the Lions stays")
    t.run()


def test_a_copy_may_be_left_uncast_and_is_gone_afterwards():
    """The exiled Lions's copy is not cast; it cannot be cast later either."""
    lions = card(SavannahLions)
    game, uldaros = _game([lions], extra_mana={ManaType.WHITE: 1})
    t = Table(game)
    _cast_uldaros(t, uldaros, [lions])
    _resolve_trigger(t, [], then=[moves(lions, Zone.EXILE)])
    t.act_illegal(0, SavannahLions, note="neither the copy nor the exiled card can be cast")
    t.run()


def test_a_target_exiled_in_response_is_not_copied_and_the_other_still_is():
    """Player 1's Ambush Wolf exiles the targeted Lions in response; Boltwave
    is still copied and cast."""
    lions, wave, wolf = card(SavannahLions), card(Boltwave), card(AmbushWolf)
    game, uldaros = _game([lions, wave], seat1=Side(hand=[wolf], library=_library(), mana={ManaType.GREEN: 3}),)
    t = Table(game)
    t.act(0, uldaros, then=[moves(uldaros, Zone.STACK)])
    t.pass_(0, choices=[lions, wave])
    t.pass_(1, then=[moves(uldaros, Zone.BATTLEFIELD), on_stack(TRIGGER, 0)])
    t.pass_(0)
    t.act(1, wolf, then=[moves(wolf, Zone.STACK)])
    t.pass_(1, choices=[lions])
    t.pass_(0, then=[moves(wolf, Zone.BATTLEFIELD), on_stack(AmbushWolfAbility2, 1)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(AmbushWolfAbility2), moves(lions, Zone.EXILE)])
    _resolve_trigger(t, [SavannahLions, Boltwave], then=[moves(wave, Zone.EXILE), copied(Boltwave, 0)])
    _resolve_top(t, Boltwave, then=[life(1, 17)])
    t.run()


def test_the_trigger_resolves_after_uldaros_leaves():
    lions, downfall = card(SavannahLions), card(HerosDownfall)
    game, uldaros = _game([lions], seat1=Side(hand=[downfall], library=_library(), mana={ManaType.BLACK: 3}))
    t = Table(game)
    _cast_uldaros(t, uldaros, [lions])
    t.pass_(0)
    t.act(1, downfall, choices=[uldaros], then=[moves(downfall, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(downfall, Zone.GRAVEYARD), moves(uldaros, Zone.GRAVEYARD)])
    _resolve_trigger(t, [SavannahLions], then=[moves(lions, Zone.EXILE), copied(SavannahLions, 0)])
    _resolve_top(t, SavannahLions, then=[appears(0)])
    t.run()


def test_an_artifact_creature_and_a_creature_fill_both_slots():
    """Burnished Hart fills the artifact slot and Lions the creature slot,
    whichever the engine asks first."""
    hart, lions = card(BurnishedHart), card(SavannahLions)
    game, uldaros = _game([hart, lions])
    t = Table(game)
    _cast_uldaros(t, uldaros, [lions, hart], distinct=True)
    _resolve_trigger(t, [BurnishedHart, SavannahLions], then=[
        moves(hart, Zone.EXILE), moves(lions, Zone.EXILE), copied(BurnishedHart, 0), copied(SavannahLions, 0),
    ])
    _resolve_top(t, SavannahLions, then=[appears(0)])
    _resolve_top(t, BurnishedHart, then=[appears(0)])
    t.run()


def test_a_single_artifact_creature_is_copied_once():
    """With one artifact creature card, it is exiled and copied once, however
    the engine asks for the artifact and the creature: a repeat is tried, and
    if the engine rejects it the fallback chooses it once."""
    hart = card(BurnishedHart)
    game, uldaros = _game([hart])
    t = Table(game)
    _cast_uldaros(t, uldaros, branches=[branch(choices=[hart]), branch(choices=[hart], distinct=True)])
    _resolve_trigger(t, [BurnishedHart], then=[moves(hart, Zone.EXILE), copied(BurnishedHart, 0)])
    _resolve_top(t, BurnishedHart, then=[appears(0)])
    t.run()


def test_an_adventure_card_in_the_graveyard_fills_only_the_artifact_type():
    """Glamdring in the graveyard is only an artifact (CR 715.4): the scripts
    prefer Gleam of Death for the sorcery question, so an engine that let it
    fill that type would exile both artifacts and leave Boltwave behind. An
    engine that offers Gleam of Death and rejects it, or asks one question for
    every type and rejects two artifacts, is answered from a fallback."""
    wave, glamdring, axe = card(Boltwave), card(GlamdringFoehammer), card(LeylineAxe)
    game, uldaros = _game([wave, glamdring, axe])
    t = Table(game)
    _cast_uldaros(t, uldaros, branches=[
        branch(choices=[GleamOfDeath, LeylineAxe, GlamdringFoehammer, Boltwave]),
        branch(choices=[LeylineAxe, GlamdringFoehammer, Boltwave]),
        branch(choices=[LeylineAxe, Boltwave]),
    ])
    _resolve_trigger(t, [], then=[moves(axe, Zone.EXILE), moves(wave, Zone.EXILE)],
                     note="Glamdring stays in the graveyard; no copy is cast")
    t.run()


def test_an_adventure_copy_is_cast_as_its_adventure_within_the_budget():
    """Glamdring's copy is cast as Gleam of Death (mana value 4) and mills six;
    the 2 left of the budget would still cast Boltwave's copy, which is declined."""
    wave, glamdring, uldaros = card(Boltwave), card(GlamdringFoehammer), card(UldarosTheorix)
    library = _library(7)
    game = create_game(
        Side(hand=[uldaros], graveyard=[wave, glamdring], library=library, mana=dict(ULDAROS_MANA)),
        Side(library=_library()),
        start=MAIN,
    )
    t = Table(game)
    _cast_uldaros(t, uldaros, [GlamdringFoehammer, Boltwave])
    _resolve_trigger(t, [GleamOfDeath, GlamdringFoehammer], then=[
        moves(glamdring, Zone.EXILE), moves(wave, Zone.EXILE), copied(GleamOfDeath, 0),
    ])
    _resolve_top(t, GleamOfDeath, then=[moves(c, Zone.GRAVEYARD) for c in library[:6]])
    t.run()


def test_an_adventure_over_the_remaining_budget_is_cast_as_its_artifact():
    """After Dazzling Angel (3), Gleam of Death (4) no longer fits the budget,
    so Glamdring's copy is cast as the Equipment (2)."""
    angel, glamdring = card(DazzlingAngel), card(GlamdringFoehammer)
    game, uldaros = _game([angel, glamdring])
    t = Table(game)
    _cast_uldaros(t, uldaros, [DazzlingAngel, GlamdringFoehammer])
    t.pass_(0, branches=[
        branch(choices=[DazzlingAngel, GleamOfDeath, GlamdringFoehammer]),
        branch(choices=[DazzlingAngel, GlamdringFoehammer]),
    ])
    t.pass_(1, then=[
        off_stack(TRIGGER), moves(angel, Zone.EXILE), moves(glamdring, Zone.EXILE),
        copied(DazzlingAngel, 0), copied(GlamdringFoehammer, 0),
    ])
    _resolve_top(t, GlamdringFoehammer, then=[appears(0)])
    _resolve_top(t, DazzlingAngel, then=[appears(0)])
    t.run()


def test_a_copy_that_cannot_be_cast_leaves_the_original_in_exile():
    """Bite Down needs a creature or planeswalker player 0 does not control;
    with none, its copy is not cast, and the card stays exiled."""
    bite = card(BiteDown)
    game, uldaros = _game([bite])
    t = Table(game)
    _cast_uldaros(t, uldaros, [bite])
    t.pass_(0, branches=[branch(choices=[BiteDown]), branch(choices=[])])
    t.pass_(1, then=[off_stack(TRIGGER), moves(bite, Zone.EXILE)],
            note="casting the copy is offered or not; either way it cannot be cast")
    t.run()


def test_the_copies_are_cast():
    """Firebrand Archer sees the copy of Boltwave cast: 1 more damage."""
    wave = card(Boltwave)
    game, uldaros = _game([wave], battlefield=[FirebrandArcher])
    t = Table(game)
    _cast_uldaros(t, uldaros, [wave])
    _resolve_trigger(t, [Boltwave], then=[moves(wave, Zone.EXILE), copied(Boltwave, 0),
                                          on_stack(FirebrandArcherAbility1, 0)])
    _resolve_top(t, FirebrandArcherAbility1, then=[life(1, 19)])
    _resolve_top(t, Boltwave, then=[life(1, 16)])
    t.run()


def test_a_free_x_spell_has_x_zero():
    """Exsanguinate's copy is cast without paying its mana cost, so X is 0
    even with mana to spare: nobody's life changes."""
    exsanguinate = card(Exsanguinate)
    game, uldaros = _game([exsanguinate], extra_mana={ManaType.BLACK: 5})
    t = Table(game)
    _cast_uldaros(t, uldaros, [exsanguinate])
    _resolve_trigger(t, [Exsanguinate], then=[moves(exsanguinate, Zone.EXILE), copied(Exsanguinate, 0)])
    _resolve_top(t, Exsanguinate)
    t.run()


def test_a_planeswalker_copy_has_its_printed_loyalty():
    """Ajani's token copy starts with 4 loyalty: its −3 can be activated."""
    ajani = card(AjaniCallerOfThePride)
    lions = card(SavannahLions)
    game, uldaros = _game([ajani], battlefield=[lions])
    t = Table(game)
    _cast_uldaros(t, uldaros, [ajani])
    _resolve_trigger(t, [AjaniCallerOfThePride], then=[moves(ajani, Zone.EXILE), copied(AjaniCallerOfThePride, 0)])
    _resolve_top(t, AjaniCallerOfThePride, then=[appears(0)])
    t.act(0, AjaniCallerOfThePrideAbility2, choices=[lions], then=[on_stack(AjaniCallerOfThePrideAbility2, 0)])
    _resolve_top(t, AjaniCallerOfThePrideAbility2)
    t.run()


def test_a_permanent_copy_has_its_triggered_abilities():
    """A token copy of Dazzling Angel gains life when another creature enters."""
    angel, lions = card(DazzlingAngel), card(SavannahLions)
    game, uldaros = _game([angel], hand=[lions], extra_mana={ManaType.WHITE: 1})
    t = Table(game)
    _cast_uldaros(t, uldaros, [angel])
    _resolve_trigger(t, [DazzlingAngel], then=[moves(angel, Zone.EXILE), copied(DazzlingAngel, 0)])
    _resolve_top(t, DazzlingAngel, then=[appears(0)])
    t.act(0, lions, then=[moves(lions, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(lions, Zone.BATTLEFIELD), on_stack(DazzlingAngelAbility2, 0)])
    _resolve_top(t, DazzlingAngelAbility2, then=[life(0, 21)])
    t.run()


def test_a_token_copy_leaving_does_not_return_the_original():
    """The Lions token dies and ceases to exist; the exiled card stays exiled."""
    lions, bolt = card(SavannahLions), card(BurstLightning)
    game, uldaros = _game([lions], seat1=Side(hand=[bolt], library=_library(), mana={ManaType.RED: 1}))
    t = Table(game)
    _cast_uldaros(t, uldaros, [lions])
    _resolve_trigger(t, [SavannahLions], then=[moves(lions, Zone.EXILE), copied(SavannahLions, 0)])
    _resolve_top(t, SavannahLions, then=[appears(0)])
    t.pass_(0)
    t.act(1, bolt, choices=[token(1)], then=[moves(bolt, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD), ceases(token(1))])
    t.run()


def test_a_slaughter_pact_copy_is_cast_free_and_still_comes_due():
    """Slaughter Pact's copy has mana value 0, so it fits the budget; it destroys
    player 1's Lions, and its pact comes due at player 0's next upkeep, which
    player 0 cannot pay."""
    pact, theirs = card(SlaughterPact), card(SavannahLions)
    game, uldaros = _game([pact], seat1=Side(battlefield=[theirs], library=_library()))
    t = Table(game)
    _cast_uldaros(t, uldaros, [pact])
    _resolve_trigger(t, [SlaughterPact, theirs], then=[moves(pact, Zone.EXILE), copied(SlaughterPact, 0)])
    _resolve_top(t, SlaughterPact, then=[moves(theirs, Zone.GRAVEYARD)])
    t.pass_to(Step.END, 1)
    t.pass_(1)
    t.pass_(0, then=[on_stack(SlaughterPactAbility2, 0)])
    t.pass_(0, choices=[Decision.no()])
    t.pass_(1, then=[off_stack(SlaughterPactAbility2), wins(1)])
    t.run()


def test_a_slaughter_pact_copy_with_only_uldaros_to_target_is_not_cast():
    """Uldaros is black, so with no other creature the Pact's copy has no legal
    target: the card is exiled and its copy is never cast."""
    pact = card(SlaughterPact)
    game, uldaros = _game([pact])
    t = Table(game)
    _cast_uldaros(t, uldaros, [pact])
    t.pass_(0, branches=[branch(choices=[SlaughterPact]), branch(choices=[])])
    t.pass_(1, then=[off_stack(TRIGGER), moves(pact, Zone.EXILE)],
            note="casting the copy is offered or not; either way it has no legal target")
    t.run()


def test_a_zero_mana_value_copy_leaves_the_budget_for_a_six():
    """Self-Reflection (6) and Slaughter Pact (0) together fit the budget of 6:
    both are cast."""
    reflection, pact = card(SelfReflection), card(SlaughterPact)
    mine, theirs = card(SavannahLions), card(SavannahLions)
    game, uldaros = _game([reflection, pact], battlefield=[mine],
                          seat1=Side(battlefield=[theirs], library=_library()))
    t = Table(game)
    _cast_uldaros(t, uldaros, [reflection, pact])
    t.pass_(0, choices=[SelfReflection, SlaughterPact],
            per_query={_asked_by(SelfReflection): [mine], _asked_by(SlaughterPact): [theirs]})
    t.pass_(1, then=[
        off_stack(TRIGGER), moves(reflection, Zone.EXILE), moves(pact, Zone.EXILE),
        copied(SelfReflection, 0), copied(SlaughterPact, 0),
    ])
    _resolve_top(t, SlaughterPact, then=[moves(theirs, Zone.GRAVEYARD)])
    _resolve_top(t, SelfReflection, then=[appears(0)])
    t.run()


def test_a_free_eaten_alive_copy_still_pays_its_additional_cost():
    """Casting a copy without paying its mana cost still owes Eaten Alive's
    additional cost (rule 118.9d): with the pool spent on Uldaros, player 0
    sacrifices their Lions, and the copy exiles player 1's."""
    eaten, mine, theirs = card(EatenAlive), card(SavannahLions), card(SavannahLions)
    game, uldaros = _game([eaten], battlefield=[mine], seat1=Side(battlefield=[theirs], library=_library()))
    t = Table(game)
    _cast_uldaros(t, uldaros, [eaten])
    _resolve_trigger(t, [EatenAlive, SACRIFICE, theirs, mine], then=[
        moves(eaten, Zone.EXILE), copied(EatenAlive, 0), moves(mine, Zone.GRAVEYARD),
    ])
    _resolve_top(t, EatenAlive, then=[moves(theirs, Zone.EXILE)])
    t.run()


def test_a_free_eaten_alive_copy_with_no_creature_and_no_mana_is_not_cast():
    """With Uldaros destroyed in response, player 0 has no creature to
    sacrifice and no mana for {3}{B}: the copy cannot be cast, though its mana
    cost is not paid."""
    eaten, theirs, downfall = card(EatenAlive), card(SavannahLions), card(HerosDownfall)
    game, uldaros = _game([eaten], seat1=Side(battlefield=[theirs], hand=[downfall], library=_library(),
                                               mana={ManaType.BLACK: 3}))
    t = Table(game)
    _cast_uldaros(t, uldaros, [eaten])
    t.pass_(0)
    t.act(1, downfall, choices=[uldaros], then=[moves(downfall, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(downfall, Zone.GRAVEYARD), moves(uldaros, Zone.GRAVEYARD)])
    t.pass_(0, branches=[branch(choices=[EatenAlive, SACRIFICE, theirs]), branch(choices=[EatenAlive, PAY_MANA, theirs]),
                         branch(choices=[])])
    t.pass_(1, then=[off_stack(TRIGGER), moves(eaten, Zone.EXILE)],
            note="casting the copy, with either alternative, is offered or not; neither can be paid")
    t.run()
