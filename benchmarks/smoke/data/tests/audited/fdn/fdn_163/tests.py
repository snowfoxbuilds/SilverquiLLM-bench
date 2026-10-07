"""Regression tests for FDN 163 — Self-Reflection.

"Create a token that's a copy of target creature you control." The token is a
copy (rule 707.2): a distinct game object carrying only the copiable
characteristics — none of the original's counters, damage or tapped status.
The tests cast Self-Reflection in player 0's main phase and judge the token by
what it does: Burst Lightning's 2 damage, or a block on player 1's turn.
"""

from __future__ import annotations

from cards.fdn.fdn_62.card_impl import HungryGhoul, HungryGhoulAbility1
from cards.fdn.fdn_96.card_impl import StrongboxRaider
from cards.fdn.fdn_131.card_impl import RavenousAmulet
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_163.card_impl import SelfReflection
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_278.card_impl import Mountain
from engine.card import Sorcery
from engine.types import ManaCost
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game, token

from table import Table, appears, ceases, life, moves, off_stack, on_stack, taps

_SIX = {ManaType.BLUE: 2, ManaType.COLORLESS: 4}


class TestSelfReflectionProperties:
    def test_is_sorcery(self) -> None:
        assert isinstance(SelfReflection(owner=None), Sorcery)

    def test_mana_and_flashback_cost(self) -> None:
        card = SelfReflection(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}{U}{U}")
        assert card.flashback_cost == ManaCost.parse("{3}{U}")


def _reflect(t, spell, original, *, lands=()):
    """Player 0 casts Self-Reflection on ``original``, tapping ``lands``
    first when the mana comes from them."""
    for land in lands:
        t.act(0, land, then=[taps(land)])
    t.act(0, spell, choices=[original], then=[moves(spell, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(spell, Zone.GRAVEYARD), appears(0)])


def _game(original, *, battlefield=(), hand=(), p1=None, mana=_SIX, start=(Phase.PRECOMBAT_MAIN, 0)):
    spell = card(SelfReflection)
    game = create_game(
        Side(battlefield=[original, *battlefield], hand=[spell, *hand], library=[card(Plains)], mana=mana),
        p1 or Side(library=[card(Plains)]),
        start=start,
    )
    return Table(game), spell


def _burst(t, mountain, burst, target, then):
    t.act(0, mountain, then=[taps(mountain)])
    t.act(0, burst, choices=[target], then=[moves(burst, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(burst, Zone.GRAVEYARD), *then])


class TestSelfReflectionCopyToken:
    def test_creates_one_token_copy(self) -> None:
        lions = card(SavannahLions)
        t, spell = _game(lions)
        _reflect(t, spell, lions)
        t.run()

    def test_token_is_a_distinct_object(self) -> None:
        """2 damage to the token kills it alone: the Lions it copies stays."""
        lions, mountain, burst = card(SavannahLions), card(Mountain), card(BurstLightning)
        t, spell = _game(lions, battlefield=[mountain], hand=[burst])
        _reflect(t, spell, lions)
        _burst(t, mountain, burst, token(1), [ceases(token(1))])
        t.run()

    def test_token_carries_copiable_characteristics(self) -> None:
        """The copy of Savannah Lions is a 2/1 creature: on player 1's turn it
        blocks Strongbox Raider (5/2), and both die."""
        lions, raider = card(SavannahLions), card(StrongboxRaider)
        t, spell = _game(lions, p1=Side(battlefield=[raider], library=[card(Plains)]))
        _reflect(t, spell, lions)
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
        lions, mountain, burst = card(SavannahLions), card(Mountain), card(BurstLightning)
        t, spell = _game(lions, battlefield=[mountain], hand=[burst])
        _reflect(t, spell, lions)
        _burst(t, mountain, burst, lions, [moves(lions, Zone.GRAVEYARD)])
        t.run()

    def test_token_excludes_the_originals_counters(self) -> None:
        """Counters are not copiable (rule 707.2): Hungry Ghoul gets a +1/+1
        counter in player 1's end step, its copy dies to 2 damage, and the 3/3
        Ghoul then attacks for 3."""
        ghoul, elves, mountain, burst = card(HungryGhoul), card(LlanowarElves), card(Mountain), card(BurstLightning)
        lands = [card(Island), card(Island), card(Plains), card(Plains), card(Plains), card(Plains)]
        t, spell = _game(
            ghoul,
            battlefield=[elves, mountain, *lands],
            hand=[burst],
            mana={ManaType.COLORLESS: 1},
            start=(Step.END, 1),
        )
        t.pass_(1)
        t.act(0, HungryGhoulAbility1, choices=[elves], then=[moves(elves, Zone.GRAVEYARD), on_stack(HungryGhoulAbility1, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(HungryGhoulAbility1)])
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        _reflect(t, spell, ghoul, lands=lands)
        _burst(t, mountain, burst, token(1), [ceases(token(1))])
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, ghoul, then=[taps(ghoul)])
        t.pass_(0)
        t.pass_(1)
        t.pass_(1)
        t.pass_(0)
        t.pass_(1, then=[life(1, 17)])
        t.run()

    def test_no_target_is_a_noop(self) -> None:
        """With no creature to target, Self-Reflection cannot be cast."""
        t, spell = _game(card(RavenousAmulet))
        t.act_illegal(0, spell)
        t.run()
