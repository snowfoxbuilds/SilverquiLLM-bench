"""Summoning sickness and {T} abilities (rule 302.6).

A creature's activated ability with {T} in its cost can be activated only if
the creature has been under its controller's control continuously since their
most recent turn began; haste lifts the restriction. It applies to mana
abilities too, and it is the creature's controller's turn that counts, not
whose turn it is now.

Each is seen through real FDN cards: Krenko, Mob Boss's {T} ability makes a
Goblin when it resolves; Llanowar Elves and Ruby, Daring Tracker tap for mana;
Confiscate hands Llanowar Elves to a new controller; Burnished Hart's cost
has no {T}, so the restriction never applies to it.
"""

from __future__ import annotations

from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_204.card_impl import KrenkoMobBoss, KrenkoMobBossAbility1
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_245.card_impl import RubyDaringTracker
from cards.fdn.fdn_250.card_impl import BurnishedHart, BurnishedHartAbility1
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_278.card_impl import Mountain
from cards.fdn.fdn_280.card_impl import Forest
from cards.fdn.fdn_709.card_impl import Confiscate
from table import Table, appears, gains_control, life, moves, off_stack, on_stack, taps
from test_interface import ManaType, Phase, Side, Zone, card, create_game, player, shuffled


def _library() -> list:
    return [card(Plains) for _ in range(3)]


def _cast(t: Table, seat: int, spell, lands, *, choices=(), then=()) -> None:
    """``seat`` taps ``lands`` and casts ``spell``; it resolves with ``then``."""
    for land in lands:
        t.act(seat, land, then=[taps(land)])
    t.act(seat, spell, choices=list(choices), then=[moves(spell, Zone.STACK)])
    t.pass_(seat)
    t.pass_(1 - seat, then=[moves(spell, Zone.BATTLEFIELD), *then])


def _krenko_activates(t: Table, seat: int, krenko) -> None:
    """``seat`` taps Krenko for its ability, which resolves into a Goblin."""
    t.act(seat, KrenkoMobBossAbility1, then=[taps(krenko), on_stack(KrenkoMobBossAbility1, seat)])
    t.pass_(seat)
    t.pass_(1 - seat, then=[off_stack(KrenkoMobBossAbility1), appears(seat)])


def _krenko_cast() -> tuple[Table, object]:
    """Player 0 casts Krenko, Mob Boss with four Mountains in their first main
    phase."""
    krenko = card(KrenkoMobBoss)
    mountains = [card(Mountain) for _ in range(4)]
    t = Table(create_game(
        Side(hand=[krenko], battlefield=mountains, library=_library()),
        Side(library=_library()),
        start=(Phase.PRECOMBAT_MAIN, 0),
    ))
    _cast(t, 0, krenko, mountains)
    return t, krenko


class TestCreatureThatJustArrived:
    def test_cannot_use_its_tap_ability_the_turn_it_is_cast(self):
        t, _ = _krenko_cast()
        t.act_illegal(0, KrenkoMobBossAbility1, note="Krenko arrived this turn")
        t.pass_(0)
        t.pass_(1)
        t.run()

    def test_still_cannot_on_the_opponents_turn(self):
        """Player 0's most recent turn began before Krenko arrived, so it
        stays unable to tap through player 1's turn."""
        t, _ = _krenko_cast()
        t.pass_to(Phase.PRECOMBAT_MAIN, 1)
        t.pass_(1)
        t.act_illegal(0, KrenkoMobBossAbility1, note="player 1's turn; player 0's began without Krenko")
        t.pass_(0)
        t.run()

    def test_can_from_its_controllers_next_turn(self):
        t, krenko = _krenko_cast()
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        _krenko_activates(t, 0, krenko)
        t.run()

    def test_cannot_tap_for_mana_the_turn_it_is_cast(self):
        elves, forest = card(LlanowarElves), card(Forest)
        t = Table(create_game(Side(hand=[elves], battlefield=[forest]), Side(), start=(Phase.PRECOMBAT_MAIN, 0)))
        _cast(t, 0, elves, [forest])
        t.act_illegal(0, elves, note="a mana ability is a {T} ability too")
        t.pass_(0)
        t.pass_(1)
        t.run()

    def test_with_haste_taps_for_mana_at_once(self):
        """Ruby has haste: its mana, the turn it is cast, pays for Burst
        Lightning."""
        ruby, bolt = card(RubyDaringTracker), card(BurstLightning)
        lands = [card(Mountain), card(Forest)]
        t = Table(create_game(Side(hand=[ruby, bolt], battlefield=lands), Side(), start=(Phase.PRECOMBAT_MAIN, 0)))
        _cast(t, 0, ruby, lands)
        t.act(0, ruby, then=[taps(ruby)], note="{R} from Ruby")
        t.act(0, bolt, choices=[player(1)], then=[moves(bolt, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), life(1, 18)])
        t.run()


class TestCreatureThatChangedControl:
    def _confiscated_elves(self) -> tuple[Table, object, object]:
        """Player 0 casts Confiscate on player 1's Llanowar Elves, which player 1
        has controlled since before the game's first turn; player 0 holds a
        second Elves."""
        confiscate, elves, second = card(Confiscate), card(LlanowarElves), card(LlanowarElves)
        islands = [card(Island) for _ in range(6)]
        t = Table(create_game(
            Side(hand=[confiscate, second], battlefield=islands, library=_library()),
            Side(battlefield=[elves], library=_library()),
            start=(Phase.PRECOMBAT_MAIN, 0),
        ))
        _cast(t, 0, confiscate, islands, choices=[elves], then=[gains_control(elves, 0)])
        return t, elves, second

    def test_cannot_tap_for_its_new_controller(self):
        t, elves, _ = self._confiscated_elves()
        t.act_illegal(0, elves, note="the Elves changed control this turn")
        t.pass_(0)
        t.pass_(1)
        t.run()

    def test_taps_for_its_new_controller_from_their_next_turn(self):
        """On player 0's next turn the Elves' {G} casts the second Elves."""
        t, elves, second = self._confiscated_elves()
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        _cast(t, 0, second, [elves])
        t.run()

    def test_an_ability_without_tap_in_its_cost_is_not_restricted(self):
        """Burnished Hart's cost is {3} and sacrificing it, with no {T}: taken
        with Confiscate, tapped, it is sacrificed and its ability resolves for
        its new controller that same turn."""
        confiscate, hart, lions = card(Confiscate), card(BurnishedHart, tapped=True), card(SavannahLions)
        islands = [card(Island) for _ in range(6)]
        t = Table(create_game(
            Side(hand=[confiscate], battlefield=islands, library=[lions], mana={ManaType.COLORLESS: 3}),
            Side(battlefield=[hart]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        ))
        _cast(t, 0, confiscate, islands, choices=[hart], then=[gains_control(hart, 0)])
        t.act(0, hart, then=[moves(hart, Zone.GRAVEYARD), moves(confiscate, Zone.GRAVEYARD),
                             on_stack(BurnishedHartAbility1, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(BurnishedHartAbility1)], note="no basic land to find")
        t.run(chance=[shuffled(lions)])
