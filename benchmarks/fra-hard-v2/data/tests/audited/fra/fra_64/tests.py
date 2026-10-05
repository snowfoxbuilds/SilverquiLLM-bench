"""Sanctum Lurker, played at the table.

Each test builds a position, plays it through both players' scripts and judges
Sanctum Lurker by what the players can see: a Jace token appearing, which
loyalty abilities the rules allow, life totals, and permanents leaving the
battlefield. A planeswalker's loyalty shows only through the loyalty abilities
it may activate and whether it survives at 0.
"""

from card_impl import SanctumLurker, SanctumLurkerAbility1, SanctumLurkerAbility3
from cards.fdn.fdn_134.card_impl import AjaniCallerOfThePride
from cards.fdn.fdn_175.card_impl import HerosDownfall
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_203.card_impl import InvoluntaryEmployment
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_276.card_impl import Swamp
from cards.fdn.fdn_278.card_impl import Mountain
from cards.fra.tokens import JaceTokenAbility1, JaceTokenAbility2
from test_interface import Decision, ManaType, Phase, Side, Step, Zone, card, create_game, token

from silverquillm.table import Table, appears, ceases, gains_control, life, moves, off_stack, on_stack, taps

MAIN = (Phase.PRECOMBAT_MAIN, 0)
DRAIN = SanctumLurkerAbility3
SURVEIL = JaceTokenAbility1
DRAW = JaceTokenAbility2
JACE = token(1)


def _game(seat0: Side, seat1: Side | None = None, start=MAIN):
    return create_game(seat0, seat1 or Side(library=[Plains, Plains]), start=start)


def _cast_lurker(t: Table, seat: int, lurker, *, new_token: bool = True) -> None:
    """``seat`` casts ``lurker``; it resolves and its enters trigger empowers Jace 1."""
    t.act(seat, lurker, then=[moves(lurker, Zone.STACK)])
    t.pass_(seat)
    t.pass_(1 - seat, then=[moves(lurker, Zone.BATTLEFIELD), on_stack(SanctumLurkerAbility1, seat)])
    t.pass_(seat)
    t.pass_(1 - seat, then=[off_stack(SanctumLurkerAbility1)] + ([appears(seat)] if new_token else []))


def _activate(t: Table, seat: int, ability, *, then=(), choices=(), note: str = "") -> None:
    """``seat`` activates loyalty ability ``ability``; both pass and it resolves."""
    t.act(seat, ability, then=[on_stack(ability, seat)], note=note)
    t.pass_(seat, choices=list(choices))
    t.pass_(1 - seat, then=[off_stack(ability), *then])


def _kill(t: Table, seat: int, bolt, target, *, then=()) -> None:
    """``seat`` casts Burst Lightning at ``target``; both pass and it resolves."""
    t.act(seat, bolt, choices=[target], then=[moves(bolt, Zone.STACK)])
    t.pass_(seat)
    t.pass_(1 - seat, then=[moves(bolt, Zone.GRAVEYARD), *then])


def test_enters_and_creates_a_jace_token_with_one_loyalty():
    """The enters trigger makes a Jace token with 1 loyalty: its −3 cannot be
    paid, and the rejected try leaves it free to −1 the same turn."""
    lurker, top = card(SanctumLurker), card(Plains)
    game = _game(Side(hand=[lurker], library=[top], mana={ManaType.BLACK: 3}))
    t = Table(game)
    _cast_lurker(t, 0, lurker)
    t.act_illegal(0, DRAW, note="1 loyalty cannot pay −3")
    _activate(t, 0, SURVEIL, choices=[Decision.yes()], then=[moves(top, Zone.GRAVEYARD)])
    t.run()


def test_lurker_attacks_for_three():
    lurker = card(SanctumLurker)
    game = _game(Side(battlefield=[lurker]))
    t = Table(game)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, lurker, then=[taps(lurker)])
    t.pass_(0)
    t.pass_(1)
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, 17)])
    t.run()


def test_lurker_dies_to_two_damage():
    lurker, bolt = card(SanctumLurker), card(BurstLightning)
    game = _game(Side(battlefield=[lurker]), Side(hand=[bolt], mana={ManaType.RED: 1}, library=[Plains]))
    t = Table(game)
    t.pass_(0)
    _kill(t, 1, bolt, lurker, then=[moves(lurker, Zone.GRAVEYARD)])
    t.run()


def test_second_lurker_empowers_the_same_jace():
    """A second Lurker adds loyalty to the existing Jace instead of making
    another: Jace goes 2 → 4 with +2, 4 → 1 with −3 next turn, and can still
    −1 on the turn after."""
    first, second = card(SanctumLurker), card(SanctumLurker)
    second_draw = card(Plains)
    game = _game(
        Side(hand=[first, second], library=[Plains, second_draw, Plains, Plains], mana={ManaType.BLACK: 6}),
        Side(library=[Plains, Plains, Plains]),
    )
    t = Table(game)
    _cast_lurker(t, 0, first)
    _cast_lurker(t, 0, second, new_token=False)
    _activate(t, 0, DRAIN, then=[life(0, 21), life(1, 19)])
    t.pass_to(Phase.PRECOMBAT_MAIN, 0)
    _activate(t, 0, DRAW, then=[moves(second_draw, Zone.HAND)])
    t.pass_to(Phase.PRECOMBAT_MAIN, 0)
    _activate(t, 0, SURVEIL, choices=[Decision.no()], note="Jace still has 1 loyalty to pay −1")
    t.run()


def test_granted_plus_two_drains_each_opponent_and_gains_life():
    lurker = card(SanctumLurker)
    game = _game(Side(hand=[lurker], mana={ManaType.BLACK: 3}))
    t = Table(game)
    _cast_lurker(t, 0, lurker)
    _activate(t, 0, DRAIN, then=[life(0, 21), life(1, 19)])
    t.run()


def test_granted_ability_is_a_loyalty_ability_once_per_turn():
    """After the granted +2, neither it nor Jace's own −1 may be activated
    that turn."""
    lurker = card(SanctumLurker)
    game = _game(Side(hand=[lurker], mana={ManaType.BLACK: 3}))
    t = Table(game)
    _cast_lurker(t, 0, lurker)
    _activate(t, 0, DRAIN, then=[life(0, 21), life(1, 19)])
    t.act_illegal(0, DRAIN)
    t.act_illegal(0, SURVEIL)
    t.run()


def test_granted_ability_needs_sorcery_timing():
    """The granted +2 cannot be activated with a spell on the stack or on the
    opponent's turn."""
    lurker, bolt = card(SanctumLurker), card(BurstLightning)
    game = _game(Side(hand=[lurker, bolt], mana={ManaType.BLACK: 3, ManaType.RED: 1}))
    t = Table(game)
    _cast_lurker(t, 0, lurker)
    t.act(0, bolt, choices=[lurker], then=[moves(bolt, Zone.STACK)])
    t.act_illegal(0, DRAIN, note="a spell is on the stack")
    t.pass_(0)
    t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), moves(lurker, Zone.GRAVEYARD)])
    t.pass_to(Step.UPKEEP, 1)
    t.pass_(1)
    t.act_illegal(0, SURVEIL, note="it is the opponent's turn")
    t.run()


def test_grant_needs_sanctum_lurker_on_the_battlefield():
    """Once the Lurker is gone, Jace has only its own abilities: the +2 is not
    allowed, its −1 is, and at 0 loyalty Jace dies."""
    lurker, bolt, top = card(SanctumLurker), card(BurstLightning), card(Plains)
    game = _game(Side(hand=[lurker, bolt], library=[top], mana={ManaType.BLACK: 3, ManaType.RED: 1}))
    t = Table(game)
    _cast_lurker(t, 0, lurker)
    _kill(t, 0, bolt, lurker, then=[moves(lurker, Zone.GRAVEYARD)])
    t.act_illegal(0, DRAIN)
    t.act(0, SURVEIL, then=[on_stack(SURVEIL, 0), ceases(JACE)], note="paying −1 leaves Jace at 0, and nothing keeps it")
    t.pass_(0, choices=[Decision.yes()])
    t.pass_(1, then=[off_stack(SURVEIL), moves(top, Zone.GRAVEYARD)])
    t.run()


def test_pending_empower_resolves_after_lurker_leaves():
    """The enters trigger empowers Jace even if the Lurker dies in response."""
    lurker, bolt = card(SanctumLurker), card(BurstLightning)
    game = _game(Side(hand=[lurker], mana={ManaType.BLACK: 3}), Side(hand=[bolt], mana={ManaType.RED: 1}, library=[Plains]))
    t = Table(game)
    t.act(0, lurker, then=[moves(lurker, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(lurker, Zone.BATTLEFIELD), on_stack(SanctumLurkerAbility1, 0)])
    t.pass_(0)
    t.act(1, bolt, choices=[lurker], then=[moves(bolt, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD), moves(lurker, Zone.GRAVEYARD)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(SanctumLurkerAbility1), appears(0)])
    t.act_illegal(0, DRAIN, note="no Lurker grants the +2 now")
    t.run()


def test_zero_loyalty_jace_stays_while_lurker_remains():
    """At 0 loyalty Jace stays on the battlefield with the Lurker, and dies as
    soon as the Lurker leaves."""
    lurker, bolt, top = card(SanctumLurker), card(BurstLightning), card(Plains)
    game = _game(Side(hand=[lurker], library=[top], mana={ManaType.BLACK: 3}),
                 Side(hand=[bolt], mana={ManaType.RED: 1}, library=[Plains]))
    t = Table(game)
    _cast_lurker(t, 0, lurker)
    _activate(t, 0, SURVEIL, choices=[Decision.yes()], then=[moves(top, Zone.GRAVEYARD)], note="Jace at 0 stays")
    t.pass_(0)
    _kill(t, 1, bolt, lurker, then=[moves(lurker, Zone.GRAVEYARD), ceases(JACE)])
    t.run()


def test_another_lurker_keeps_zero_loyalty_jace():
    """With two Lurkers, either one keeps a 0-loyalty Jace on the battlefield;
    it dies when the last one leaves."""
    cast, kept = card(SanctumLurker), card(SanctumLurker)
    first, second, top = card(BurstLightning), card(BurstLightning), card(Plains)
    game = _game(
        Side(hand=[cast], battlefield=[kept], library=[top], mana={ManaType.BLACK: 3}),
        Side(hand=[first, second], mana={ManaType.RED: 2}, library=[Plains]),
    )
    t = Table(game)
    _cast_lurker(t, 0, cast)
    _activate(t, 0, SURVEIL, choices=[Decision.yes()], then=[moves(top, Zone.GRAVEYARD)])
    t.pass_(0)
    _kill(t, 1, first, cast, then=[moves(cast, Zone.GRAVEYARD)])
    t.pass_(0)
    _kill(t, 1, second, kept, then=[moves(kept, Zone.GRAVEYARD), ceases(JACE)])
    t.run()


def test_minus_three_draws_once_jace_has_three_loyalty():
    lurker, top = card(SanctumLurker), card(Plains)
    game = _game(Side(hand=[lurker], library=[Plains, top], mana={ManaType.BLACK: 3}),
                 Side(library=[Plains, Plains]))
    t = Table(game)
    _cast_lurker(t, 0, lurker)
    _activate(t, 0, DRAIN, then=[life(0, 21), life(1, 19)])
    t.pass_to(Phase.PRECOMBAT_MAIN, 0)
    _activate(t, 0, DRAW, then=[moves(top, Zone.HAND)], note="3 loyalty pays −3; Jace stays at 0")
    t.run()


def test_pending_drain_resolves_after_jace_leaves():
    """The +2 resolves even when Jace is destroyed in response: the drain still
    happens."""
    lurker, downfall = card(SanctumLurker), card(HerosDownfall)
    game = _game(Side(hand=[lurker], mana={ManaType.BLACK: 3}),
                 Side(hand=[downfall], mana={ManaType.BLACK: 3}, library=[Plains]))
    t = Table(game)
    _cast_lurker(t, 0, lurker)
    t.act(0, DRAIN, then=[on_stack(DRAIN, 0)])
    t.pass_(0)
    t.act(1, downfall, choices=[JACE], then=[moves(downfall, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(downfall, Zone.GRAVEYARD), ceases(JACE)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(DRAIN), life(0, 21), life(1, 19)])
    t.run()


def test_pending_drain_resolves_after_lurker_leaves():
    lurker, bolt = card(SanctumLurker), card(BurstLightning)
    game = _game(Side(hand=[lurker], mana={ManaType.BLACK: 3}),
                 Side(hand=[bolt], mana={ManaType.RED: 1}, library=[Plains]))
    t = Table(game)
    _cast_lurker(t, 0, lurker)
    t.act(0, DRAIN, then=[on_stack(DRAIN, 0)])
    t.pass_(0)
    _kill(t, 1, bolt, lurker, then=[moves(lurker, Zone.GRAVEYARD)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(DRAIN), life(0, 21), life(1, 19)])
    t.run()


def test_opponents_jace_token_is_not_empowered():
    """Each player's Lurker empowers only their own Jace: the second Lurker
    makes player 0 a token of their own, with 1 loyalty."""
    theirs, mine = card(SanctumLurker), card(SanctumLurker)
    swamps = [card(Swamp) for _ in range(3)]
    game = _game(
        Side(hand=[mine], battlefield=swamps, library=[Plains, Plains]),
        Side(hand=[theirs], library=[Plains, Plains], mana={ManaType.BLACK: 3}),
        start=(Phase.PRECOMBAT_MAIN, 1),
    )
    t = Table(game)
    _cast_lurker(t, 1, theirs)
    t.pass_to(Phase.PRECOMBAT_MAIN, 0)
    for swamp in swamps:
        t.act(0, swamp, then=[taps(swamp)])
    _cast_lurker(t, 0, mine)
    t.act_illegal(0, DRAW, note="player 0's own Jace has 1 loyalty")
    t.run()


def test_opponents_lurker_does_not_protect_my_jace():
    """Only the Lurkers a planeswalker's controller controls keep it at 0: with
    player 0's Lurker gone, player 1's Lurker does not save player 0's Jace."""
    mine, theirs, bolt, top = card(SanctumLurker), card(SanctumLurker), card(BurstLightning), card(Plains)
    game = _game(Side(hand=[mine], library=[top], mana={ManaType.BLACK: 3}),
                 Side(hand=[bolt], battlefield=[theirs], mana={ManaType.RED: 1}, library=[Plains]))
    t = Table(game)
    _cast_lurker(t, 0, mine)
    _activate(t, 0, SURVEIL, choices=[Decision.yes()], then=[moves(top, Zone.GRAVEYARD)])
    t.pass_(0)
    _kill(t, 1, bolt, mine, then=[moves(mine, Zone.GRAVEYARD), ceases(JACE)])
    t.run()


def test_nontoken_planeswalker_gets_the_granted_ability():
    """Any planeswalker its controller controls gets the +2, not only Jace."""
    ajani = card(AjaniCallerOfThePride)
    game = _game(Side(battlefield=[SanctumLurker, ajani]))
    t = Table(game)
    _activate(t, 0, DRAIN, then=[life(0, 21), life(1, 19)])
    t.act_illegal(0, DRAIN, note="once per turn for Ajani too")
    t.run()


def test_opponents_planeswalkers_do_not_get_the_ability():
    ajani = card(AjaniCallerOfThePride)
    game = _game(Side(battlefield=[ajani]), Side(battlefield=[SanctumLurker], library=[Plains]))
    t = Table(game)
    t.act_illegal(0, DRAIN)
    t.run()


def test_stolen_lurker_stops_protecting_its_owners_jace():
    """When the opponent gains control of the Lurker, it protects their
    planeswalkers, not its owner's: player 0's 0-loyalty Jace dies."""
    lurker, employment, top = card(SanctumLurker), card(InvoluntaryEmployment), card(Plains)
    mountains = [card(Mountain) for _ in range(4)]
    game = _game(Side(hand=[lurker], library=[top, Plains], mana={ManaType.BLACK: 3}),
                 Side(hand=[employment], battlefield=mountains, library=[Plains]))
    t = Table(game)
    _cast_lurker(t, 0, lurker)
    _activate(t, 0, SURVEIL, choices=[Decision.yes()], then=[moves(top, Zone.GRAVEYARD)])
    t.pass_to(Phase.PRECOMBAT_MAIN, 1)
    for mountain in mountains:
        t.act(1, mountain, then=[taps(mountain)])
    t.act(1, employment, choices=[lurker], then=[moves(employment, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(employment, Zone.GRAVEYARD), gains_control(lurker, 1), appears(1), ceases(JACE)])
    t.run()
