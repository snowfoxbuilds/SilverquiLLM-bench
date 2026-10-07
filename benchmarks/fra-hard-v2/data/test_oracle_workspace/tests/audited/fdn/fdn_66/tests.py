"""Reference tests for FDN 66 — Nine-Lives Familiar.

"This creature enters with eight revival counters on it if you cast it." A
cast Familiar has revival counters, so when it dies it returns at the
beginning of the next end step; one put onto the battlefield from the
graveyard has none, so when it dies it stays dead.
"""

from __future__ import annotations

from cards.fdn.fdn_66.card_impl import NineLivesFamiliar, NineLivesFamiliarAbility2
from cards.fdn.fdn_187.card_impl import Zombify
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_278.card_impl import Mountain
from engine.card import printed_class
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game

from silverquillm.table import Table, moves, off_stack, on_stack, taps


class TestNineLivesProperties:
    def test_name_and_cost(self) -> None:
        card_ = NineLivesFamiliar(owner=None)
        assert printed_class(card_) is NineLivesFamiliar
        assert card_.mana_cost == ManaCost.parse("{1}{B}{B}")


def _cast_and_kill(*, second_bolt=None, second_mountain=None):
    """Turn 1: player 0 casts the Familiar, then kills it with Burst
    Lightning; its dies trigger resolves."""
    familiar, bolt, mountain = card(NineLivesFamiliar), card(BurstLightning), card(Mountain)
    extra_hand = [second_bolt] if second_bolt else []
    extra_lands = [second_mountain] if second_mountain else []
    game = create_game(
        Side(
            hand=[familiar, bolt, *extra_hand],
            battlefield=[mountain, *extra_lands],
            mana={ManaType.BLACK: 2, ManaType.COLORLESS: 1},
        ),
        Side(library=[card(Mountain)]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, familiar, then=[moves(familiar, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(familiar, Zone.BATTLEFIELD)])
    t.act(0, mountain, then=[taps(mountain)])
    t.act(0, bolt, choices=[familiar], then=[moves(bolt, Zone.STACK)])
    t.pass_(0)
    t.pass_(
        1,
        then=[
            moves(bolt, Zone.GRAVEYARD),
            moves(familiar, Zone.GRAVEYARD),
            on_stack(NineLivesFamiliarAbility2, 0),
        ],
    )
    t.pass_(0)
    t.pass_(1, then=[off_stack(NineLivesFamiliarAbility2)])
    return t, familiar


def _returns_at_end_step(t, familiar):
    t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
    t.pass_(0)
    t.pass_(1, then=[on_stack(NineLivesFamiliarAbility2, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(NineLivesFamiliarAbility2), moves(familiar, Zone.BATTLEFIELD)])


class TestNineLivesEntersWithRevival:
    def test_enters_from_stack_gets_eight_revival(self) -> None:
        """Cast, it has revival counters: it returns after it dies."""
        t, familiar = _cast_and_kill()
        _returns_at_end_step(t, familiar)
        t.run()

    def test_return_from_graveyard_adds_no_fresh_counters(self) -> None:
        """Zombified, it has no revival counter, so its dies ability does not
        trigger and it stays in the graveyard."""
        familiar, zombify, bolt, mountain = (
            card(NineLivesFamiliar),
            card(Zombify),
            card(BurstLightning),
            card(Mountain),
        )
        game = create_game(
            Side(
                graveyard=[familiar],
                hand=[zombify, bolt],
                battlefield=[mountain],
                mana={ManaType.BLACK: 1, ManaType.COLORLESS: 3},
            ),
            Side(),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, zombify, choices=[familiar], then=[moves(zombify, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(zombify, Zone.GRAVEYARD), moves(familiar, Zone.BATTLEFIELD)])
        t.act(0, mountain, then=[taps(mountain)])
        t.act(0, bolt, choices=[familiar], then=[moves(bolt, Zone.STACK)])
        t.pass_(0)
        t.pass_(
            1,
            then=[moves(bolt, Zone.GRAVEYARD), moves(familiar, Zone.GRAVEYARD)],
            note="nothing triggers",
        )
        t.pass_to(Step.END, 0)
        t.run()


class TestNineLivesDiesReturn:

    def test_dies_returns_with_one_fewer_revival(self) -> None:
        """It returns at the next end step with one fewer revival counter —
        still one at least, so killed again in that end step it returns at the
        end step after, on player 1's turn."""
        bolt, mountain = card(BurstLightning), card(Mountain)
        t, familiar = _cast_and_kill(second_bolt=bolt, second_mountain=mountain)
        _returns_at_end_step(t, familiar)
        t.act(0, mountain, then=[taps(mountain)])
        t.act(0, bolt, choices=[familiar], then=[moves(bolt, Zone.STACK)])
        t.pass_(0)
        t.pass_(
            1,
            then=[
                moves(bolt, Zone.GRAVEYARD),
                moves(familiar, Zone.GRAVEYARD),
                on_stack(NineLivesFamiliarAbility2, 0),
            ],
        )
        t.pass_(0)
        t.pass_(1, then=[off_stack(NineLivesFamiliarAbility2)])
        t.pass_to(Phase.POSTCOMBAT_MAIN, 1)
        t.pass_(1)
        t.pass_(0, then=[on_stack(NineLivesFamiliarAbility2, 0)])
        t.pass_(1)
        t.pass_(0, then=[off_stack(NineLivesFamiliarAbility2), moves(familiar, Zone.BATTLEFIELD)])
        t.run()

    def test_does_not_return_before_the_next_end_step(self) -> None:
        t, _familiar = _cast_and_kill()
        t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
        t.run()
