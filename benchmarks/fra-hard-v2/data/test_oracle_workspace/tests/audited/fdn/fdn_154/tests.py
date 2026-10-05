"""Regression tests for FDN 154 — Extravagant Replication.

"At the beginning of your upkeep, create a token that's a copy of another
target nonland permanent you control." The copy is a token (rule 707.2): a
distinct game object carrying only the copiable characteristics — none of the
copied permanent's counters, damage or tapped status. The tests play player
0's upkeep and judge the token by what it does: Burst Lightning's 2 damage,
or a block on player 1's turn.
"""

from __future__ import annotations

from cards.fdn.fdn_62.card_impl import HungryGhoul, HungryGhoulAbility1
from cards.fdn.fdn_96.card_impl import StrongboxRaider
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_154.card_impl import ExtravagantReplication, ExtravagantReplicationAbility1
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_278.card_impl import Mountain
from engine.card import Enchantment
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game, token

from silverquillm.table import Table, appears, ceases, life, moves, off_stack, on_stack, taps


class TestExtravagantReplicationProperties:
    def test_is_enchantment(self) -> None:
        assert isinstance(ExtravagantReplication(owner=None), Enchantment)

    def test_mana_cost(self) -> None:
        assert ExtravagantReplication(owner=None).mana_cost == ManaCost.parse("{4}{U}{U}")


def _upkeep_copy(original, *, battlefield=(), hand=(), p1=None, before=None):
    """From player 1's end step into player 0's upkeep, where Extravagant
    Replication copies ``original``. ``before(t)`` plays player 0's actions
    in player 1's end step first."""
    game = create_game(
        Side(
            battlefield=[ExtravagantReplication, original, *battlefield],
            hand=list(hand),
            library=[card(Plains)],
            mana={ManaType.COLORLESS: 1},
        ),
        p1 or Side(library=[card(Plains)]),
        start=(Step.END, 1),
    )
    t = Table(game)
    t.pass_(1)
    if before:
        before(t)
    # The target is chosen as the trigger is put on the stack, or as it
    # resolves: both entries name it.
    t.pass_(0, choices=[original], then=[on_stack(ExtravagantReplicationAbility1, 0)])
    t.pass_(0, choices=[original])
    t.pass_(1, then=[off_stack(ExtravagantReplicationAbility1), appears(0)])
    return t


def _burst(t, target, then):
    """Player 0's main phase: Burst Lightning, from a Mountain, at ``target``."""
    t.pass_to(Phase.PRECOMBAT_MAIN, 0)
    mountain = t.mountain
    burst = t.burst
    t.act(0, mountain, then=[taps(mountain)])
    t.act(0, burst, choices=[target], then=[moves(burst, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(burst, Zone.GRAVEYARD), *then])


def _with_burst(original, **kwargs):
    mountain, burst = card(Mountain), card(BurstLightning)
    t = _upkeep_copy(original, battlefield=[mountain, *kwargs.pop("battlefield", ())], hand=[burst], **kwargs)
    t.mountain, t.burst = mountain, burst
    return t


class TestExtravagantReplicationCopyToken:
    def test_upkeep_creates_one_token_copy(self) -> None:
        t = _upkeep_copy(card(SavannahLions))
        t.run()

    def test_token_is_a_distinct_object(self) -> None:
        """2 damage to the token kills it alone: the Lions it copies stays."""
        t = _with_burst(card(SavannahLions))
        _burst(t, token(1), [ceases(token(1))])
        t.run()

    def test_token_carries_copiable_characteristics(self) -> None:
        """The copy of Savannah Lions is a 2/1 creature: on player 1's turn it
        blocks Strongbox Raider (5/2), and both die."""
        lions, raider = card(SavannahLions), card(StrongboxRaider)
        t = _upkeep_copy(lions, p1=Side(battlefield=[raider], library=[card(Plains)]))
        t.pass_to(Step.DECLARE_ATTACKERS, 1)
        t.act(1, raider, then=[taps(raider)])
        t.pass_(1)
        t.pass_(0)
        t.act(0, token(1), scoped={token(1): raider})
        t.pass_(1)
        t.pass_(0, then=[ceases(token(1)), moves(raider, Zone.GRAVEYARD)])
        t.run()

    def test_token_containers_are_de_aliased(self) -> None:
        """2 damage to the original kills it alone: the token stays."""
        lions = card(SavannahLions)
        t = _with_burst(lions)
        _burst(t, lions, [moves(lions, Zone.GRAVEYARD)])
        t.run()

    def test_token_excludes_the_originals_counters(self) -> None:
        """Counters are not copiable (rule 707.2): Hungry Ghoul gets a +1/+1
        counter in player 1's end step, its copy dies to 2 damage, and the 3/3
        Ghoul then attacks for 3."""
        ghoul, elves = card(HungryGhoul), card(LlanowarElves)

        def counter(t):
            t.act(0, ghoul, choices=[elves], then=[moves(elves, Zone.GRAVEYARD), on_stack(HungryGhoulAbility1, 0)])
            t.pass_(0)
            t.pass_(1, then=[off_stack(HungryGhoulAbility1)])
            t.pass_(1)

        t = _with_burst(ghoul, battlefield=[elves], before=counter)
        _burst(t, token(1), [ceases(token(1))])
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, ghoul, then=[taps(ghoul)])
        t.pass_(0)
        t.pass_(1)
        t.pass_(1)
        t.pass_(0)
        t.pass_(1, then=[life(1, 17)])
        t.run()
