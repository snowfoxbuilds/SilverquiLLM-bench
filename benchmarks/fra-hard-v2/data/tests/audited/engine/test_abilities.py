"""Activated abilities (rules 602, 605, 606).

Covers:
- ActivatedAbilityInstance / LoyaltyAbilityInstance construction and fields.
- A {T} cost taps its untapped source and cannot be paid by a tapped one.
- Mana abilities resolve at once, without the stack, whenever their
  controller has priority — in combat, on the other player's turn.
- Other activated abilities go on the stack under their controller, take
  effect only when they resolve, and may be activated at instant speed.
- Loyalty abilities: +N and −N change loyalty, a cost larger than the
  loyalty is illegal and changes nothing, once per planeswalker per turn
  (again the next turn), only at sorcery speed, only by the controller,
  and their targets are chosen as they are activated.
- Two abilities of one permanent share its {T} cost.

Each is seen through real FDN cards: Krenko, Mob Boss's {T} ability makes a
Goblin when it resolves; a Mountain's mana casts Burst Lightning; loyalty
shows in how much damage a planeswalker survives, or in which of its
abilities the rules allow.
"""

from __future__ import annotations

from cards.fdn.fdn_44.card_impl import (
    KaitoCunningInfiltrator,
    KaitoCunningInfiltratorAbility2,
    KaitoCunningInfiltratorAbility3,
)
from cards.fdn.fdn_134.card_impl import (
    AjaniCallerOfThePride,
    AjaniCallerOfThePrideAbility1,
    AjaniCallerOfThePrideAbility2,
    AjaniCallerOfThePrideAbility3,
)
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_176.card_impl import LilianaDreadhordeGeneral, LilianaDreadhordeGeneralAbility2
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_204.card_impl import KrenkoMobBoss, KrenkoMobBossAbility1
from cards.fdn.fdn_264.card_impl import RoguesPassage, RoguesPassageAbility1, RoguesPassageAbility2
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_278.card_impl import Mountain
from test_interface import Phase, Side, Step, Zone, card, create_game, player
from test_utils import DeterministicPlayer

from engine.abilities import (
    ActivatedAbilityInstance,
    LoyaltyAbilityInstance,
)
from engine.game_state import GameState
from silverquillm.table import Table, appears, life, moves, off_stack, on_stack, taps

# ---------------------------------------------------------------------------
# ActivatedAbilityInstance — construction
# ---------------------------------------------------------------------------


class TestActivatedAbilityInstanceConstruction:
    """ActivatedAbilityInstance dataclass stores all expected fields."""

    def test_fields_assigned(self):
        source = object()
        controller = DeterministicPlayer("Alice")
        cost = lambda g, s: True
        effect = lambda g: None
        ability = ActivatedAbilityInstance(
            source=source,
            controller=controller,
            cost=cost,
            effect=effect,
            is_mana_ability=True,
            description="Tap for mana",
        )
        assert ability.source is source
        assert ability.controller is controller
        assert ability.cost is cost
        assert ability.effect is effect
        assert ability.is_mana_ability is True
        assert ability.description == "Tap for mana"

    def test_defaults(self):
        source = object()
        controller = DeterministicPlayer("Alice")
        ability = ActivatedAbilityInstance(
            source=source,
            controller=controller,
            cost=lambda g, s: True,
            effect=lambda g: None,
        )
        assert ability.is_mana_ability is False
        assert ability.description == ""


# ---------------------------------------------------------------------------
# LoyaltyAbilityInstance — construction
# ---------------------------------------------------------------------------


class TestLoyaltyAbilityInstanceConstruction:
    """LoyaltyAbilityInstance dataclass stores all expected fields."""

    def test_fields_assigned(self):
        source = object()
        controller = DeterministicPlayer("Alice")
        effect = lambda g: None
        ability = LoyaltyAbilityInstance(
            source=source,
            controller=controller,
            loyalty_cost=-3,
            effect=effect,
            description="Destroy target creature",
        )
        assert ability.source is source
        assert ability.controller is controller
        assert ability.loyalty_cost == -3
        assert ability.effect is effect
        assert ability.description == "Destroy target creature"

    def test_defaults(self):
        source = object()
        controller = DeterministicPlayer("Alice")
        ability = LoyaltyAbilityInstance(
            source=source,
            controller=controller,
        )
        assert ability.loyalty_cost == 0
        assert ability.description == ""
        # default effect should be callable
        ability.effect(None)  # should not raise


# ---------------------------------------------------------------------------
# Engine entry points with no counterpart at the table
# ---------------------------------------------------------------------------


def _bare_game() -> GameState:
    return GameState([DeterministicPlayer("Alice"), DeterministicPlayer("Bob")])






# ---------------------------------------------------------------------------
# {T} costs
# ---------------------------------------------------------------------------


def _main(p0: Side, p1: Side | None = None, *, active: int = 0) -> Table:
    return Table(create_game(p0, p1 or Side(), start=(Phase.PRECOMBAT_MAIN, active)))


def _resolve(t: Table, first: int, *results) -> None:
    """Both players pass, ``first`` first, and the top of the stack resolves."""
    t.pass_(first)
    t.pass_(1 - first, then=list(results))


class TestTapCost:
    def test_untapped_source_pays_by_tapping(self):
        krenko = card(KrenkoMobBoss)
        t = _main(Side(battlefield=[krenko]))
        t.act(0, KrenkoMobBossAbility1, then=[taps(krenko), on_stack(KrenkoMobBossAbility1, 0)])
        _resolve(t, 0, off_stack(KrenkoMobBossAbility1), appears(0))
        t.run()

    def test_tapped_source_cannot_pay(self):
        krenko = card(KrenkoMobBoss, tapped=True)
        t = _main(Side(battlefield=[krenko]))
        t.act_illegal(0, KrenkoMobBossAbility1, note="Krenko is already tapped; nothing goes on the stack")
        t.pass_(0)
        t.pass_(1)
        t.run()


# ---------------------------------------------------------------------------
# Mana abilities
# ---------------------------------------------------------------------------


def _bolt_with_mountain(t: Table, seat: int, mountain, bolt, at) -> None:
    t.act(seat, mountain, then=[taps(mountain)], note="the mana ability resolves at once, off the stack")
    t.act(seat, bolt, choices=[at], then=[moves(bolt, Zone.STACK)], note="its mana pays for Burst Lightning")


class TestManaAbility:
    def test_resolves_at_once_without_the_stack(self):
        mountain, bolt = card(Mountain), card(BurstLightning)
        t = _main(Side(hand=[bolt], battlefield=[mountain]))
        _bolt_with_mountain(t, 0, mountain, bolt, player(1))
        _resolve(t, 0, moves(bolt, Zone.GRAVEYARD), life(1, 18))
        t.run()

    def test_activated_in_combat(self):
        mountain, bolt = card(Mountain), card(BurstLightning)
        game = create_game(Side(hand=[bolt], battlefield=[mountain]), Side(), start=(Step.BEGIN_COMBAT, 0))
        t = Table(game)
        _bolt_with_mountain(t, 0, mountain, bolt, player(1))
        _resolve(t, 0, moves(bolt, Zone.GRAVEYARD), life(1, 18))
        t.run()

    def test_activated_by_the_non_active_player(self):
        mountain, bolt = card(Mountain), card(BurstLightning)
        t = _main(Side(), Side(hand=[bolt], battlefield=[mountain]))
        t.pass_(0)
        _bolt_with_mountain(t, 1, mountain, bolt, player(0))
        _resolve(t, 1, moves(bolt, Zone.GRAVEYARD), life(0, 18))
        t.run()

    def test_tapped_land_cannot_tap_for_mana(self):
        mountain = card(Mountain, tapped=True)
        t = _main(Side(battlefield=[mountain]))
        t.act_illegal(0, mountain)
        t.pass_(0)
        t.pass_(1)
        t.run()


# ---------------------------------------------------------------------------
# Other activated abilities use the stack, at instant speed
# ---------------------------------------------------------------------------


class TestActivatedAbilityOnTheStack:
    def test_waits_on_the_stack_until_it_resolves(self):
        krenko = card(KrenkoMobBoss)
        t = _main(Side(battlefield=[krenko]))
        t.act(0, KrenkoMobBossAbility1, then=[taps(krenko), on_stack(KrenkoMobBossAbility1, 0)])
        t.pass_(0, note="no Goblin yet: the ability has not resolved")
        t.pass_(1, then=[off_stack(KrenkoMobBossAbility1), appears(0)], note="it resolves, making a Goblin")
        t.run()

    def test_activated_in_combat(self):
        krenko = card(KrenkoMobBoss)
        game = create_game(Side(battlefield=[krenko]), Side(), start=(Step.BEGIN_COMBAT, 0))
        t = Table(game)
        t.act(0, KrenkoMobBossAbility1, then=[taps(krenko), on_stack(KrenkoMobBossAbility1, 0)])
        _resolve(t, 0, off_stack(KrenkoMobBossAbility1), appears(0))
        t.run()

    def test_activated_with_a_spell_on_the_stack(self):
        krenko, mountain, bolt = card(KrenkoMobBoss), card(Mountain), card(BurstLightning)
        t = _main(Side(hand=[bolt], battlefield=[krenko, mountain]))
        _bolt_with_mountain(t, 0, mountain, bolt, player(1))
        t.act(0, KrenkoMobBossAbility1, then=[taps(krenko), on_stack(KrenkoMobBossAbility1, 0)])
        _resolve(t, 0, off_stack(KrenkoMobBossAbility1), appears(0))
        _resolve(t, 0, moves(bolt, Zone.GRAVEYARD), life(1, 18))
        t.run()

    def test_activated_by_the_non_active_player(self):
        krenko = card(KrenkoMobBoss)
        t = _main(Side(), Side(battlefield=[krenko]))
        t.pass_(0)
        t.act(1, KrenkoMobBossAbility1, then=[taps(krenko), on_stack(KrenkoMobBossAbility1, 1)])
        _resolve(t, 1, off_stack(KrenkoMobBossAbility1), appears(1))
        t.run()

    def test_activated_in_the_end_step(self):
        krenko = card(KrenkoMobBoss)
        game = create_game(Side(battlefield=[krenko]), Side(), start=(Step.END, 0))
        t = Table(game)
        t.act(0, KrenkoMobBossAbility1, then=[taps(krenko), on_stack(KrenkoMobBossAbility1, 0)])
        _resolve(t, 0, off_stack(KrenkoMobBossAbility1), appears(0))
        t.run()


class TestTwoAbilitiesOfOnePermanent:
    def test_both_need_the_same_tap(self):
        passage, lions = card(RoguesPassage), card(SavannahLions)
        mountains = [card(Mountain) for _ in range(4)]
        t = _main(Side(battlefield=[passage, lions, *mountains]))
        t.act(0, RoguesPassageAbility1, then=[taps(passage)])
        for mountain in mountains:
            t.act(0, mountain, then=[taps(mountain)])
        t.act_illegal(
            0, RoguesPassageAbility2, choices=[lions], note="the {4} is there, but Rogue's Passage is tapped"
        )
        t.pass_(0)
        t.pass_(1)
        t.run()


# ---------------------------------------------------------------------------
# Loyalty abilities
# ---------------------------------------------------------------------------


def _ajani(*, hand=(), battlefield=(), p0_library=1) -> Table:
    """Player 0's turn 1 with Ajani (loyalty 4); each player has enough
    library for the next few turns."""
    ajani = card(AjaniCallerOfThePride)
    game = create_game(
        Side(hand=list(hand), battlefield=[ajani, *battlefield], library=[card(Plains) for _ in range(p0_library)]),
        Side(library=[card(Plains) for _ in range(p0_library)]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    return Table(game)


def _loyalty(t: Table, ability, *, choices=(), then=(), note="") -> None:
    """Player 0 activates the loyalty ability ``ability``, and it resolves."""
    t.act(0, ability, choices=list(choices), then=[on_stack(ability, 0)], note=note)
    _resolve(t, 0, off_stack(ability), *then)


class TestLoyaltyCost:
    def test_plus_ability_adds_loyalty_that_a_minus_may_spend_to_zero(self):
        kaito = card(KaitoCunningInfiltrator)
        library = [card(Plains) for _ in range(3)]
        game = create_game(
            Side(battlefield=[kaito], library=library),
            Side(library=[card(Plains) for _ in range(2)]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        plus, minus = KaitoCunningInfiltratorAbility2, KaitoCunningInfiltratorAbility3
        _loyalty(t, plus, then=[moves(library[0], Zone.GRAVEYARD)], note="+1 from 3: draw a card, then discard it")
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        _loyalty(t, minus, then=[appears(0)], note="−2 from 4")
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        t.act(
            0,
            minus,
            then=[on_stack(minus, 0), moves(kaito, Zone.GRAVEYARD)],
            note="−2 from exactly 2 is legal, as it is only because the +1 added one; Kaito is left with none",
        )
        _resolve(t, 0, off_stack(minus), appears(0))
        t.run()

    def test_minus_ability_removes_loyalty(self):
        lions = card(SavannahLions)
        t = _ajani(battlefield=[lions])
        _loyalty(t, AjaniCallerOfThePrideAbility2, choices=[lions], note="−3 from 4")
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        t.act_illegal(0, AjaniCallerOfThePrideAbility2, choices=[lions], note="−3 from 1")
        _loyalty(t, AjaniCallerOfThePrideAbility1)
        t.run()

    def test_cost_larger_than_loyalty_is_illegal_and_changes_nothing(self):
        lions = card(SavannahLions)
        t = _ajani(battlefield=[lions])
        t.act_illegal(0, AjaniCallerOfThePrideAbility3, note="−8 from 4")
        _loyalty(
            t,
            AjaniCallerOfThePrideAbility1,
            note="the refused −8 never happened, so Ajani may still activate this turn",
        )
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        _loyalty(t, AjaniCallerOfThePrideAbility2, choices=[lions], note="−3 from 5")
        t.run()


class TestLoyaltyOncePerTurn:
    def test_second_activation_in_a_turn_is_illegal(self):
        ajani, lions = card(AjaniCallerOfThePride), card(SavannahLions)
        t = _main(Side(battlefield=[ajani, lions]))
        t.act(0, AjaniCallerOfThePrideAbility1, then=[on_stack(AjaniCallerOfThePrideAbility1, 0)])
        _resolve(t, 0, off_stack(AjaniCallerOfThePrideAbility1))
        t.act_illegal(0, AjaniCallerOfThePrideAbility1)
        t.act_illegal(0, AjaniCallerOfThePrideAbility2, choices=[lions])
        t.pass_(0)
        t.pass_(1)
        t.run()

    def test_allowed_again_on_the_next_turn(self):
        ajani = card(AjaniCallerOfThePride)
        game = create_game(
            Side(battlefield=[ajani], library=[card(Plains)]),
            Side(library=[card(Plains)]),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        t = Table(game)
        t.act(0, AjaniCallerOfThePrideAbility1, then=[on_stack(AjaniCallerOfThePrideAbility1, 0)])
        _resolve(t, 0, off_stack(AjaniCallerOfThePrideAbility1))
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        t.act(0, AjaniCallerOfThePrideAbility1, then=[on_stack(AjaniCallerOfThePrideAbility1, 0)])
        _resolve(t, 0, off_stack(AjaniCallerOfThePrideAbility1))
        t.run()

    def test_each_planeswalker_activates_once(self):
        ajani, liliana = card(AjaniCallerOfThePride), card(LilianaDreadhordeGeneral)
        t = _main(Side(battlefield=[ajani, liliana]))
        t.act(0, AjaniCallerOfThePrideAbility1, then=[on_stack(AjaniCallerOfThePrideAbility1, 0)])
        _resolve(t, 0, off_stack(AjaniCallerOfThePrideAbility1))
        t.act(0, LilianaDreadhordeGeneralAbility2, then=[on_stack(LilianaDreadhordeGeneralAbility2, 0)])
        _resolve(t, 0, off_stack(LilianaDreadhordeGeneralAbility2), appears(0))
        t.run()


class TestLoyaltyTiming:
    def test_illegal_in_combat(self):
        ajani = card(AjaniCallerOfThePride)
        game = create_game(Side(battlefield=[ajani]), Side(), start=(Step.BEGIN_COMBAT, 0))
        t = Table(game)
        t.act_illegal(0, AjaniCallerOfThePrideAbility1)
        t.pass_(0)
        t.pass_(1)
        t.run()

    def test_illegal_with_a_spell_on_the_stack(self):
        ajani, mountain, bolt = card(AjaniCallerOfThePride), card(Mountain), card(BurstLightning)
        t = _main(Side(hand=[bolt], battlefield=[ajani, mountain]))
        _bolt_with_mountain(t, 0, mountain, bolt, player(1))
        t.act_illegal(0, AjaniCallerOfThePrideAbility1)
        _resolve(t, 0, moves(bolt, Zone.GRAVEYARD), life(1, 18))
        t.run()

    def test_illegal_for_the_non_active_player(self):
        ajani = card(AjaniCallerOfThePride)
        t = _main(Side(), Side(battlefield=[ajani]))
        t.pass_(0)
        t.act_illegal(1, AjaniCallerOfThePrideAbility1)
        t.pass_(1)
        t.run()

    def test_illegal_for_a_player_who_does_not_control_it(self):
        ajani = card(AjaniCallerOfThePride)
        t = _main(Side(battlefield=[ajani]), Side(), active=1)
        t.act_illegal(1, AjaniCallerOfThePrideAbility1, note="player 1's own main phase, but player 0's Ajani")
        t.pass_(1)
        t.pass_(0)
        t.run()


class TestLoyaltyAbilityOnTheStack:
    def test_resolves_for_its_controller(self):
        liliana = card(LilianaDreadhordeGeneral)
        t = _main(Side(battlefield=[liliana]))
        t.act(0, LilianaDreadhordeGeneralAbility2, then=[on_stack(LilianaDreadhordeGeneralAbility2, 0)])
        t.pass_(0, note="no Zombie yet: the ability has not resolved")
        t.pass_(1, then=[off_stack(LilianaDreadhordeGeneralAbility2), appears(0)])
        t.run()


class TestLoyaltyTargets:
    def test_target_receives_the_effect(self):
        ajani, lions = card(AjaniCallerOfThePride), card(SavannahLions)
        t = _main(Side(battlefield=[ajani, lions]), Side(library=[card(Plains)]))
        t.act(0, AjaniCallerOfThePrideAbility1, choices=[lions], then=[on_stack(AjaniCallerOfThePrideAbility1, 0)])
        _resolve(t, 0, off_stack(AjaniCallerOfThePrideAbility1))
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, lions, then=[taps(lions)])
        t.pass_(0)
        t.pass_(1)
        t.pass_(1)  # declares no blockers
        t.pass_(0)
        t.pass_(1, then=[life(1, 17)], note="the Lions, with its +1/+1 counter, deals 3")
        t.run()

    def test_needing_a_target_is_illegal_without_one(self):
        lions, plains = card(SavannahLions), card(Plains)
        t = _ajani(hand=[lions], battlefield=[plains])
        t.act_illegal(0, AjaniCallerOfThePrideAbility2, note="−3 needs a target creature; there is none")
        _loyalty(t, AjaniCallerOfThePrideAbility1)
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        t.act(0, plains, then=[taps(plains)])
        t.act(0, lions, then=[moves(lions, Zone.STACK)])
        _resolve(t, 0, moves(lions, Zone.BATTLEFIELD))
        _loyalty(
            t,
            AjaniCallerOfThePrideAbility2,
            choices=[lions],
            note="−3 from 5: no loyalty was spent on the refused −3",
        )
        t.run()

    def test_up_to_one_target_may_choose_none(self):
        lions = card(SavannahLions)
        t = _ajani(battlefield=[lions])
        _loyalty(t, AjaniCallerOfThePrideAbility1, note="+1 with no target")
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, lions, then=[taps(lions)])
        t.pass_(0)
        t.pass_(1)
        t.pass_(1)  # declares no blockers
        t.pass_(0)
        t.pass_(1, then=[life(1, 18)], note="the Lions got no counter: it deals 2")
        t.run()
