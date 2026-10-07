"""Hall of Echoes, played at the table.

Each test builds a position, plays it through both players' scripts and judges
Hall of Echoes by what the players can see: what the Hall shows as while it is
a copy, what it pays for, how it fights, which permanents survive, and what
its copied abilities do.
"""

from card_impl import HallOfEchoes, HallOfEchoesAbility1, HallOfEchoesAbility2
from cards.fdn.fdn_16.card_impl import HelpfulHunter
from cards.fdn.fdn_40.card_impl import HighFaeTrickster
from cards.fdn.fdn_76.card_impl import VengefulBloodwitch, VengefulBloodwitchAbility1
from cards.fdn.fdn_77.card_impl import ZulAshurLichLord
from cards.fdn.fdn_117.card_impl import AshrootAnimist, AshrootAnimistAbility2
from cards.fdn.fdn_134.card_impl import AjaniCallerOfThePride, AjaniCallerOfThePrideAbility1
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_163.card_impl import SelfReflection
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_195.card_impl import FanaticalFirebrand
from cards.fdn.fdn_249.card_impl import AdventuringGear
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_276.card_impl import Swamp
from cards.fdn.fdn_278.card_impl import Mountain
from cards.fdn.fdn_687.card_impl import DemolitionField, DemolitionFieldAbility2
from cards.fdn.fdn_709.card_impl import Confiscate
from cards.fra.fra_49.card_impl import (
    AncestralCraving,
    BloodlineRecollector,
    BloodlineRecollectorAbility1,
)
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
    spell_copy,
    token,
)

from table import (
    Table,
    appears,
    becomes,
    copied,
    gains_control,
    life,
    moves,
    off_stack,
    on_stack,
    taps,
)

MAIN = (Phase.PRECOMBAT_MAIN, 0)
COPY = HallOfEchoesAbility2


def offers_craving(query) -> bool:
    """A question that offers Ancestral Craving among its options."""
    return any(dict(getattr(option, "attrs", ())).get("printed") is AncestralCraving for option in query.options)


def _library(n: int = 3) -> list:
    return [card(Plains) for _ in range(n)]


def _game(battlefield, *, hand=(), mana=5, seat1: Side | None = None, start=MAIN):
    return create_game(
        Side(hand=list(hand), battlefield=list(battlefield), library=_library(), mana={ManaType.COLORLESS: mana}),
        seat1 or Side(library=_library()),
        start=start,
    )


def _copy(t: Table, hall, target, cls, *, then=()) -> None:
    """Player 0 activates the Hall's copy ability at ``target``; it resolves
    and the Hall shows as ``cls``."""
    t.act(0, COPY, choices=[target], then=[on_stack(COPY, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(COPY), becomes(hall, cls), *then])


def _attack(t: Table, attacker, damage) -> None:
    """Player 0 attacks with ``attacker`` on its next combat, unblocked."""
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, attacker, then=[taps(attacker)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=damage)


def _bolt(t: Table, seat: int, bolt, target, *, then=()) -> None:
    t.act(seat, bolt, choices=[target], then=[moves(bolt, Zone.STACK)])
    t.pass_(seat)
    t.pass_(1 - seat, then=[moves(bolt, Zone.GRAVEYARD), *then])


def test_taps_for_colorless_mana():
    """The Hall's {C} pays for Adventuring Gear's {1}."""
    hall, gear = card(HallOfEchoes), card(AdventuringGear)
    game = _game([hall], hand=[gear], mana=0)
    t = Table(game)
    t.act(0, HallOfEchoesAbility1, then=[taps(hall)])
    t.act(0, gear, then=[moves(gear, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(gear, Zone.BATTLEFIELD)])
    t.run()


def test_becomes_a_copy_that_attacks_with_the_copied_power():
    hall, lions = card(HallOfEchoes), card(SavannahLions)
    game = _game([hall, lions])
    t = Table(game)
    _copy(t, hall, lions, SavannahLions)
    _attack(t, hall, [life(1, 18)])
    t.run()


def test_the_copy_ends_at_cleanup():
    """The next turn the Hall is a land again: it cannot attack, and taps for {C}."""
    hall, lions, gear = card(HallOfEchoes), card(SavannahLions), card(AdventuringGear)
    game = _game([hall, lions], hand=[gear])
    t = Table(game)
    _copy(t, hall, lions, SavannahLions)
    t.pass_to(Step.END, 0)
    t.pass_(0)
    t.pass_(1, then=[becomes(hall, HallOfEchoes)])
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act_illegal(0, hall, note="a land cannot attack")
    t.pass_(0)
    t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
    t.act(0, HallOfEchoesAbility1, then=[taps(hall)])
    t.act(0, gear, then=[moves(gear, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(gear, Zone.BATTLEFIELD)])
    t.run()


def test_counters_are_not_copied():
    """Lions with Ajani's +1/+1 counter is a 3/2; the Hall copying it is a 2/1."""
    hall, lions, ajani = card(HallOfEchoes), card(SavannahLions), card(AjaniCallerOfThePride)
    game = _game([hall, lions, ajani])
    t = Table(game)
    t.act(0, AjaniCallerOfThePrideAbility1, choices=[lions], then=[on_stack(AjaniCallerOfThePrideAbility1, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(AjaniCallerOfThePrideAbility1)])
    _copy(t, hall, lions, SavannahLions)
    _attack(t, hall, [life(1, 18)])
    t.run()


def test_tapped_status_is_not_copied():
    """Copying a tapped creature leaves the Hall untapped, free to attack."""
    hall, lions = card(HallOfEchoes), card(SavannahLions, tapped=True)
    game = _game([hall, lions])
    t = Table(game)
    _copy(t, hall, lions, SavannahLions)
    _attack(t, hall, [life(1, 18)])
    t.run()


def test_needs_five_mana():
    hall, lions = card(HallOfEchoes), card(SavannahLions)
    game = _game([hall, lions], mana=4)
    t = Table(game)
    t.act_illegal(0, COPY, choices=[lions])
    t.run()


def test_needs_a_creature_its_controller_controls():
    """With only the opponent's creature on the battlefield, nothing can be copied."""
    hall, theirs = card(HallOfEchoes), card(SavannahLions)
    game = _game([hall], seat1=Side(battlefield=[theirs], library=_library()))
    t = Table(game)
    t.act_illegal(0, COPY, choices=[theirs])
    t.run()


def test_a_target_gone_before_resolution_copies_nothing():
    hall, lions, bolt, mountain = card(HallOfEchoes), card(SavannahLions), card(BurstLightning), card(Mountain)
    game = _game([hall, lions], seat1=Side(hand=[bolt], battlefield=[mountain], library=_library()))
    t = Table(game)
    t.act(0, COPY, choices=[lions], then=[on_stack(COPY, 0)])
    t.pass_(0)
    t.act(1, mountain, then=[taps(mountain)])
    _bolt(t, 1, bolt, lions, then=[moves(lions, Zone.GRAVEYARD)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(COPY)], note="the Hall stays a land")
    t.run()


def test_the_legend_rule_does_not_apply_this_turn():
    """The Hall copying Zul Ashur, the original and another Zul Ashur cast
    that turn all stay on the battlefield until the copy ends."""
    hall, zul, another = card(HallOfEchoes), card(ZulAshurLichLord), card(ZulAshurLichLord)
    swamps = [card(Swamp), card(Swamp)]
    game = _game([hall, zul, *swamps], hand=[another])
    t = Table(game)
    _copy(t, hall, zul, ZulAshurLichLord)
    for land in swamps:
        t.act(0, land, then=[taps(land)])
    t.act(0, another, then=[moves(another, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(another, Zone.BATTLEFIELD)], note="three Zul Ashurs, and the legend rule does not apply")
    t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
    t.run()


def test_a_copy_leaves_as_hall_of_echoes():
    """Destroyed while a copy, the Hall goes to the graveyard as itself."""
    hall, lions, bolt = card(HallOfEchoes), card(SavannahLions), card(BurstLightning)
    game = create_game(
        Side(hand=[bolt], battlefield=[hall, lions], library=_library(), mana={ManaType.COLORLESS: 5, ManaType.RED: 1}),
        Side(library=_library()),
        start=MAIN,
    )
    t = Table(game)
    _copy(t, hall, lions, SavannahLions)
    _bolt(t, 0, bolt, hall, then=[becomes(hall, HallOfEchoes), moves(hall, Zone.GRAVEYARD)])
    t.run()


def test_copying_does_not_trigger_enters_abilities():
    """The Hall copying Helpful Hunter does not enter, so nobody draws."""
    hall, hunter = card(HallOfEchoes), card(HelpfulHunter)
    game = _game([hall, hunter])
    t = Table(game)
    _copy(t, hall, hunter, HelpfulHunter)
    t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
    t.run()


def test_the_copy_has_the_copied_dies_trigger():
    """The Hall as a Vengeful Bloodwitch dies, and its dies trigger drains."""
    hall, witch, bolt = card(HallOfEchoes), card(VengefulBloodwitch), card(BurstLightning)
    game = create_game(
        Side(hand=[bolt], battlefield=[hall, witch], library=_library(), mana={ManaType.COLORLESS: 5, ManaType.RED: 1}),
        Side(library=_library()),
        start=MAIN,
    )
    t = Table(game)
    _copy(t, hall, witch, VengefulBloodwitch)
    t.act(0, bolt, choices=[hall], then=[moves(bolt, Zone.STACK)])
    t.pass_(0, choices=[player(1), VengefulBloodwitchAbility1, VengefulBloodwitchAbility1])
    t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), becomes(hall, HallOfEchoes), moves(hall, Zone.GRAVEYARD),
                     on_stack(VengefulBloodwitchAbility1, 0), on_stack(VengefulBloodwitchAbility1, 0)],
            note="both the dying Hall-Bloodwitch and the real one see it die")
    t.pass_(0)
    t.pass_(1, then=[off_stack(VengefulBloodwitchAbility1), life(1, 19), life(0, 21)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(VengefulBloodwitchAbility1), life(1, 18), life(0, 22)])
    t.run()


def test_a_hall_played_this_turn_attacks_only_as_a_creature_with_haste():
    hall, firebrand, lions = card(HallOfEchoes), card(FanaticalFirebrand), card(SavannahLions)
    game = _game([firebrand, lions], hand=[hall])
    t = Table(game)
    t.act(0, hall, then=[moves(hall, Zone.BATTLEFIELD)])
    _copy(t, hall, firebrand, FanaticalFirebrand)
    _attack(t, hall, [life(1, 19)])
    t.run()


def test_a_hall_played_this_turn_cannot_attack_as_a_creature_without_haste():
    hall, lions = card(HallOfEchoes), card(SavannahLions)
    game = _game([lions], hand=[hall])
    t = Table(game)
    t.act(0, hall, then=[moves(hall, Zone.BATTLEFIELD)])
    _copy(t, hall, lions, SavannahLions)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act_illegal(0, hall, note="the Hall came under its controller's control this turn")
    t.run()


def test_a_copied_recollector_prepares_and_casts_its_spell():
    """The Hall copying Bloodline Recollector sees three creatures die — the
    real Recollector among them — is prepared at the end step, and its
    controller casts its copy of Ancestral Craving."""
    hall, recollector, swamp = card(HallOfEchoes), card(BloodlineRecollector), card(Swamp)
    lions = [card(SavannahLions) for _ in range(2)]
    bolts = [card(BurstLightning) for _ in range(3)]
    library = _library()
    game = create_game(
        Side(hand=bolts, battlefield=[hall, recollector, swamp, *lions], library=_library(),
             mana={ManaType.COLORLESS: 5, ManaType.RED: 3}),
        Side(library=library),
        start=MAIN,
    )
    t = Table(game)
    _copy(t, hall, recollector, BloodlineRecollector)
    for bolt, victim in zip(bolts, [*lions, recollector]):
        _bolt(t, 0, bolt, victim, then=[moves(victim, Zone.GRAVEYARD)])
    t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
    t.pass_(0)
    t.pass_(1, then=[on_stack(BloodlineRecollectorAbility1, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(BloodlineRecollectorAbility1), copied(AncestralCraving, 0, to=Zone.EXILE)])
    t.act(0, swamp, then=[taps(swamp)])
    t.act(0, branches=[branch(AncestralCraving, choices=[player(1)]),
                       branch(hall, choices=[player(1)], per_query={offers_craving: [AncestralCraving]})],
          then=[moves(spell_copy(1), Zone.STACK, seat=0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(AncestralCraving), *[moves(c, Zone.HAND) for c in library], life(1, 17)])
    t.run()


def test_another_copy_ability_can_change_what_the_hall_copies():
    """A second activation the same turn makes the Hall a copy of another creature."""
    hall, lions, firebrand = card(HallOfEchoes), card(SavannahLions), card(FanaticalFirebrand)
    game = _game([hall, lions, firebrand], mana=10)
    t = Table(game)
    _copy(t, hall, lions, SavannahLions)
    t.act_illegal(0, COPY, choices=[firebrand], note="the Hall is a Lions now and has no copy ability")
    t.run()


def test_the_hall_destroyed_in_response_copies_nothing_but_still_lifts_the_legend_rule():
    """Player 1's Demolition Field destroys the Hall in response. Its target is
    still legal, so the ability resolves: there is no Hall to become a copy, but
    the legend rule still does not apply to player 0 this turn, and a second
    Zul Ashur stays beside the first."""
    hall, zul, another = card(HallOfEchoes), card(ZulAshurLichLord), card(ZulAshurLichLord)
    field, plains = card(DemolitionField), [card(Plains), card(Plains)]
    game = create_game(
        Side(hand=[another], battlefield=[hall, zul], library=[SavannahLions] * 3,
             mana={ManaType.COLORLESS: 5, ManaType.BLACK: 2}),
        Side(battlefield=[field, *plains], library=[SavannahLions] * 3),
        start=MAIN,
    )
    t = Table(game)
    t.act(0, COPY, choices=[zul], then=[on_stack(COPY, 0)])
    t.pass_(0)
    for land in plains:
        t.act(1, land, then=[taps(land)])
    t.act(1, DemolitionFieldAbility2, choices=[hall],
          then=[moves(field, Zone.GRAVEYARD), on_stack(DemolitionFieldAbility2, 1)])
    t.pass_(1, choices=[Decision.no()], note="declines Demolition Field's search")
    t.pass_(0, choices=[Decision.no()], then=[off_stack(DemolitionFieldAbility2), moves(hall, Zone.GRAVEYARD)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(COPY)])
    t.act(0, another, then=[moves(another, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(another, Zone.BATTLEFIELD)], note="two Zul Ashurs, and the legend rule does not apply")
    t.run()


def test_a_copy_of_the_copy_copies_what_the_hall_copies():
    """Self-Reflection makes a token copy of the Hall while it is a Lions, then
    a token copy of that token: both are Lions, and stay Lions after the Hall's
    copy ends — next turn they attack for 2 each."""
    hall, lions = card(HallOfEchoes), card(SavannahLions)
    first, second = card(SelfReflection), card(SelfReflection)
    game = create_game(
        Side(hand=[first, second], battlefield=[hall, lions], library=_library(),
             mana={ManaType.COLORLESS: 13, ManaType.BLUE: 4}),
        Side(library=_library()),
        start=MAIN,
    )
    t = Table(game)
    _copy(t, hall, lions, SavannahLions)
    t.act(0, first, choices=[hall], then=[moves(first, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(first, Zone.GRAVEYARD), appears(0)])
    t.act(0, second, choices=[token(1)], then=[moves(second, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(second, Zone.GRAVEYARD), appears(0)])
    t.pass_to(Step.END, 0)
    t.pass_(0)
    t.pass_(1, then=[becomes(hall, HallOfEchoes)])
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, token(1), token(2), then=[taps(token(1)), taps(token(2))])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, 16)])
    t.run()


def test_temporary_keywords_and_boosts_are_not_copied():
    """Ashroot Animist's attack gives the Lions trample and +4/+4; the Hall
    copying the Lions is a plain 2/1, and 2 damage kills it."""
    hall, lions, animist, bolt = card(HallOfEchoes), card(SavannahLions), card(AshrootAnimist), card(BurstLightning)
    mountains, theirs = [card(Mountain) for _ in range(5)], card(Mountain)
    game = create_game(
        Side(battlefield=[hall, lions, animist, *mountains], library=_library()),
        Side(hand=[bolt], battlefield=[theirs], library=_library()),
        start=(Step.BEGIN_COMBAT, 0),
    )
    t = Table(game)
    t.pass_(0)
    t.pass_(1)
    t.act(0, animist, choices=[lions], then=[taps(animist), on_stack(AshrootAnimistAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(AshrootAnimistAbility2)], note="the Lions is a 6/5 with trample this turn")
    for mountain in mountains:
        t.act(0, mountain, then=[taps(mountain)])
    _copy(t, hall, lions, SavannahLions)
    t.pass_(0)
    t.act(1, theirs, then=[taps(theirs)])
    _bolt(t, 1, bolt, hall, then=[becomes(hall, HallOfEchoes), moves(hall, Zone.GRAVEYARD)])
    t.run()


def test_a_target_stolen_in_response_is_not_copied():
    """Player 1, with High Fae Trickster's flash, Confiscates the Lions in
    response: it is no longer a creature player 0 controls, and the Hall stays
    a land."""
    hall, lions = card(HallOfEchoes), card(SavannahLions)
    trickster, confiscate = card(HighFaeTrickster), card(Confiscate)
    game = create_game(
        Side(battlefield=[hall, lions], library=_library(), mana={ManaType.COLORLESS: 5}),
        Side(hand=[confiscate], battlefield=[trickster], library=_library(), mana={ManaType.BLUE: 6}),
        start=MAIN,
    )
    t = Table(game)
    t.act(0, COPY, choices=[lions], then=[on_stack(COPY, 0)])
    t.pass_(0)
    t.act(1, confiscate, choices=[lions], then=[moves(confiscate, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(confiscate, Zone.BATTLEFIELD), gains_control(lions, 1)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(COPY)], note="the Hall copies nothing")
    t.run()


def test_each_players_hall_lifts_the_legend_rule_for_its_controller():
    """Both players' Halls copy their own Zul Ashur: each player keeps both."""
    mine, theirs = card(HallOfEchoes), card(HallOfEchoes)
    my_zul, their_zul = card(ZulAshurLichLord), card(ZulAshurLichLord)
    game = create_game(
        Side(battlefield=[mine, my_zul], library=_library(), mana={ManaType.COLORLESS: 5}),
        Side(battlefield=[theirs, their_zul], library=_library(), mana={ManaType.COLORLESS: 5}),
        start=MAIN,
    )
    t = Table(game)
    _copy(t, mine, my_zul, ZulAshurLichLord)
    t.pass_(0)
    t.act(1, COPY, choices=[their_zul], then=[on_stack(COPY, 1)])
    t.pass_(1)
    t.pass_(0, then=[off_stack(COPY), becomes(theirs, ZulAshurLichLord)],
            note="player 1's own Hall lifts the legend rule for player 1")
    t.run()
