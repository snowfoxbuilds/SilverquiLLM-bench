"""Chandra, Flameshaper's +2 and −4, activated at the table.

+2 is judged by what its mana casts and by the cards it exiles; −4's division
by which targets die: a creature dies when its share reaches its toughness.
"""

from cards.fdn.fdn_39.card_impl import GrapplingKraken
from cards.fdn.fdn_81.card_impl import (
    ChandraFlameshaper,
    ChandraFlameshaperAbility1,
    ChandraFlameshaperAbility3,
)
from cards.fdn.fdn_83.card_impl import CracklingCyclops
from cards.fdn.fdn_87.card_impl import GoblinBoarders
from cards.fdn.fdn_110.card_impl import QuakestriderCeratops
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_278.card_impl import Mountain
from engine.card import Planeswalker, printed_class
from engine.decisions import Decision
from engine.types import ManaCost, ManaType
from test_interface import Phase, Side, Zone, card, create_game

from table import Table, moves, off_stack, on_stack


def test_is_planeswalker():
    assert isinstance(ChandraFlameshaper(), Planeswalker)


def test_name():
    assert printed_class(ChandraFlameshaper()) is ChandraFlameshaper


def test_mana_cost():
    assert ChandraFlameshaper().mana_cost == ManaCost.parse("{5}{R}{R}")


def _plus_two(library, played):
    """Player 0 activates Chandra's +2 with ``library`` (top first) and both
    players pass, so it resolves; Goblin Boarders ({2}{R}) and Burst
    Lightning ({R}) wait in hand to spend the mana it adds; player 0 chooses
    ``played`` among the exiled cards as it resolves."""
    boarders, bolt = card(GoblinBoarders), card(BurstLightning)
    game = create_game(
        Side(hand=[boarders, bolt], battlefield=[card(ChandraFlameshaper)], library=library),
        Side(),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, ChandraFlameshaperAbility1, then=[on_stack(ChandraFlameshaperAbility1, 0)])
    t.pass_(0, choices=[played])
    return t, boarders, bolt


def _spend_three_red(t, boarders, bolt):
    """The three red mana cast Goblin Boarders, and none is left for Burst
    Lightning."""
    t.act(0, boarders, then=[moves(boarders, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(boarders, Zone.BATTLEFIELD)])
    t.act_illegal(0, bolt, choices=[boarders], note="the pool held exactly three mana")


def test_plus_two_adds_mana_and_exiles_three_cards():
    top = [card(SavannahLions), card(LlanowarElves), card(Mountain)]
    rest = card(Mountain)
    t, boarders, bolt = _plus_two([*top, rest], top[0])
    t.pass_(1, then=[
        off_stack(ChandraFlameshaperAbility1), *(moves(c, Zone.EXILE) for c in top),
    ], note="the top three cards are exiled and none is drawn")
    _spend_three_red(t, boarders, bolt)
    t.run()


def test_plus_two_handles_fewer_than_three_library_cards():
    only = card(SavannahLions)
    t, boarders, bolt = _plus_two([only], only)
    t.pass_(1, then=[off_stack(ChandraFlameshaperAbility1), moves(only, Zone.EXILE)],
            note="the only card is exiled; the mana is still added")
    _spend_three_red(t, boarders, bolt)
    t.run()


def test_plus_two_cannot_be_repeated_in_the_same_turn():
    top = [card(SavannahLions), card(LlanowarElves), card(Mountain)]
    t, _boarders, _bolt = _plus_two(top, top[0])
    t.pass_(1, then=[
        off_stack(ChandraFlameshaperAbility1), *(moves(c, Zone.EXILE) for c in top),
    ])
    t.act_illegal(0, ChandraFlameshaperAbility1, note="one loyalty ability per turn")
    t.run()


def _minus_four(targets, *, library=(), opponent_library=()):
    """Chandra (loyalty 6) on player 0's battlefield and ``targets`` on
    player 1's."""
    chandra = card(ChandraFlameshaper)
    game = create_game(
        Side(battlefield=[chandra], hand=[card(BurstLightning)], library=list(library),
             mana={ManaType.RED: 1}),
        Side(battlefield=list(targets), library=list(opponent_library)),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    return Table(game), chandra


class TestChandraFlameshaperMinus4Split:
    """−4: 8 damage divided as the controller chooses among any number of
    target creatures and/or planeswalkers (rules 601.2c-d via 602.2b)."""

    def test_intent_chooses_the_split(self) -> None:
        """5 to a 0/4 kills it; 3 to the other leaves it alive; and Chandra,
        at 2 loyalty, cannot −4 again on her controller's next turn."""
        a, b = card(CracklingCyclops), card(CracklingCyclops)
        t, _chandra = _minus_four([a, b], library=[card(Mountain)], opponent_library=[card(Mountain)])
        t.act(0, ChandraFlameshaperAbility3, choices=[a, b, Decision.number(5)],
              then=[on_stack(ChandraFlameshaperAbility3, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(ChandraFlameshaperAbility3), moves(a, Zone.GRAVEYARD)])
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        t.act_illegal(0, ChandraFlameshaperAbility3, choices=[b, Decision.number(4)],
                      note="2 loyalty cannot pay −4")
        t.run()

    def test_baseline_takes_first_offered_lowest(self) -> None:
        """Choosing 1 for each queried target leaves the last the remaining
        6: the two 0/4s live and the 5/6 dies."""
        a, b, c = card(CracklingCyclops), card(CracklingCyclops), card(GrapplingKraken)
        t, _chandra = _minus_four([a, b, c])
        t.act(0, ChandraFlameshaperAbility3, choices=[a, b, c, Decision.number(1)],
              then=[on_stack(ChandraFlameshaperAbility3, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(ChandraFlameshaperAbility3), moves(c, Zone.GRAVEYARD)])
        t.run()

    def test_each_queried_target_must_get_at_least_one(self) -> None:
        """A zero share is illegal (rule 601.2d) — not offered, or offered and
        rejected: preferring 0, then 1, gives each 1/1 one damage and the 5/6
        the remaining 6, so all die."""
        a, b, c = card(LlanowarElves), card(LlanowarElves), card(GrapplingKraken)
        t, _chandra = _minus_four([a, b, c])
        t.act(0, branches=[
            [ChandraFlameshaperAbility3, a, b, c, Decision.number(0), Decision.number(1)],
            [ChandraFlameshaperAbility3, a, b, c, Decision.number(1)],
        ], then=[on_stack(ChandraFlameshaperAbility3, 0)])
        t.pass_(0)
        t.pass_(1, then=[
            off_stack(ChandraFlameshaperAbility3),
            moves(a, Zone.GRAVEYARD), moves(b, Zone.GRAVEYARD), moves(c, Zone.GRAVEYARD),
        ])
        t.run()

    def test_single_target_takes_all_8_without_a_query(self) -> None:
        """A single target can only be dealt all 8, so no amount needs
        choosing: the 12/8 dies."""
        only = card(QuakestriderCeratops)
        t, _chandra = _minus_four([only])
        t.act(0, ChandraFlameshaperAbility3, choices=[only],
              then=[on_stack(ChandraFlameshaperAbility3, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(ChandraFlameshaperAbility3), moves(only, Zone.GRAVEYARD)])
        t.run()

    def test_division_is_locked_in_at_activation(self) -> None:
        """The division is announced while activating (rule 601.2d via
        602.2b); a target that becomes illegal is dealt nothing and the other
        keeps exactly its share (608.2b): the 0/4 survives its 3."""
        a, b = card(LlanowarElves), card(CracklingCyclops)
        t, _chandra = _minus_four([a, b])
        bolt = t.start.players[0].hand[0].handle
        t.act(0, ChandraFlameshaperAbility3, choices=[a, b, Decision.number(5)],
              then=[on_stack(ChandraFlameshaperAbility3, 0)])
        t.act(0, bolt, choices=[a], then=[moves(bolt, Zone.STACK)], note="in response, Burst Lightning kills a")
        t.pass_(0)
        t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), moves(a, Zone.GRAVEYARD)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(ChandraFlameshaperAbility3)], note="the 0/4 takes only its 3")
        t.run()
