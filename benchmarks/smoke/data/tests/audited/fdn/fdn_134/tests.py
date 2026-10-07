"""Reference test for FDN 134 — Ajani, Caller of the Pride.

**Loyalty abilities with targeting**:

* ``+1`` — "Put a +1/+1 counter on *up to one* target creature": an **optional**
  loyalty target; the ability still activates with nothing chosen.
* ``−3`` — "Target creature gains flying and double strike until end of turn":
  a **required** loyalty target — with no legal creature the ability cannot be
  activated and no loyalty is spent.
* ``−8`` — untargeted (create X 2/2 Cat tokens).

Targets are chosen at activation and applied at resolution. Each effect shows
in play: a Savannah Lions (2/1) with the counter attacks for 3, and with
flying and double strike it flies over Aegis Turtle for 4.
"""

from __future__ import annotations

from cards.fdn.fdn_134.card_impl import (
    AjaniCallerOfThePride,
    AjaniCallerOfThePrideAbility1,
    AjaniCallerOfThePrideAbility2,
    AjaniCallerOfThePrideAbility3,
)
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_150.card_impl import AegisTurtle
from cards.fdn.fdn_280.card_impl import Forest
from engine.card import printed_class
from engine.types import CardType, ManaCost, Supertype
from test_interface import Phase, Side, Step, Zone, card, create_game, token

from table import (
    Table,
    appears,
    first_strike_damage,
    life,
    moves,
    off_stack,
    on_stack,
    taps,
)

PLUS, MINUS3, MINUS8 = AjaniCallerOfThePrideAbility1, AjaniCallerOfThePrideAbility2, AjaniCallerOfThePrideAbility3


def _table(battlefield=(), *, p1_battlefield=(), life0=20, turns=1):
    """Player 0's first main phase with Ajani (loyalty 4); each player can
    draw for ``turns`` more turns."""
    ajani = card(AjaniCallerOfThePride)
    game = create_game(
        Side(battlefield=[ajani, *battlefield], library=[Forest] * turns, life=life0),
        Side(battlefield=list(p1_battlefield), library=[Forest] * turns),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    return Table(game), ajani


def _loyalty(t, ability, *, choices=(), then=(), note=""):
    """Player 0 activates ``ability`` and it resolves with ``then``."""
    t.act(0, ability, choices=list(choices), then=[on_stack(ability, 0)], note=note)
    t.pass_(0)
    t.pass_(1, then=[off_stack(ability), *then])


def _attack(t, attacker, damage, *, illegal_block=None, double_strike=False):
    """``attacker`` attacks this turn and is not blocked; with double strike
    it deals ``damage`` in two halves, the first in a first-strike combat
    damage step (rule 510.4)."""
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, attacker, then=[taps(attacker)])
    t.pass_(0)
    t.pass_(1)
    if illegal_block is not None:
        t.act_illegal(1, illegal_block, scoped={illegal_block: attacker}, note="it flies")
    t.pass_(1, then=[first_strike_damage()] if double_strike else [])
    t.pass_(0)
    if double_strike:
        t.pass_(1, then=[life(1, 20 - damage // 2)])
        t.pass_(0)
    t.pass_(1, then=[life(1, 20 - damage)])


class TestAjaniProperties:
    def test_static_data(self):
        ajani = AjaniCallerOfThePride(owner=None)
        assert printed_class(ajani) is AjaniCallerOfThePride
        assert ajani.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert ajani.starting_loyalty == 4
        assert ajani.loyalty == 4
        assert Supertype.LEGENDARY in ajani.supertypes
        assert "Ajani" in ajani.subtypes
        assert CardType.PLANESWALKER in ajani.card_types


class TestAjaniPlusOne:
    def test_plus_one_counter_lands_on_target(self):
        lions = card(SavannahLions)
        t, _ajani = _table([lions])
        _loyalty(t, PLUS, choices=[lions])
        _attack(t, lions, 3)
        t.run()

    def test_target_captured_on_stack(self):
        """Of two Savannah Lions, the chosen one gets the counter and attacks
        for 3."""
        other, chosen = card(SavannahLions), card(SavannahLions)
        t, _ajani = _table([other, chosen])
        _loyalty(t, PLUS, choices=[chosen])
        _attack(t, chosen, 3)
        t.run()

    def test_up_to_one_activates_with_no_target(self):
        """ "Up to one target" is optional: with no creature at all the
        ability still activates and resolves, using Ajani's activation for the
        turn."""
        t, _ajani = _table()
        _loyalty(t, PLUS)
        t.act_illegal(0, PLUS, note="Ajani has activated this turn")
        t.run()

    def test_once_per_turn(self):
        lions = card(SavannahLions)
        t, _ajani = _table([lions])
        _loyalty(t, PLUS, choices=[lions])
        t.act_illegal(0, PLUS, choices=[lions], note="once per turn")
        t.act_illegal(0, MINUS3, choices=[lions], note="once per turn, whichever ability")
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        _loyalty(t, PLUS, choices=[lions], note="a new turn allows it again")
        t.run()


class TestAjaniMinusThree:
    def test_grants_flying_and_double_strike(self):
        """The Lions flies over Aegis Turtle and deals 2 twice."""
        lions, turtle = card(SavannahLions), card(AegisTurtle)
        t, _ajani = _table([lions], p1_battlefield=[turtle])
        _loyalty(t, MINUS3, choices=[lions])
        _attack(t, lions, 4, illegal_block=turtle, double_strike=True)
        t.run()

    def test_required_target_no_creature_rejected_before_cost(self):
        """Required target: with no creature anywhere, −3 cannot be activated
        and nothing is spent, so Ajani may still activate +1 this turn."""
        t, _ajani = _table()
        t.act_illegal(0, MINUS3, note="no creature to target")
        _loyalty(t, PLUS)
        t.run()


class TestAjaniMinusEight:
    def test_creates_x_cat_tokens_equal_to_life(self):
        """Four +1 activations on player 0's turns bring Ajani to 8; at 3 life
        −8 makes three Cats and leaves Ajani with no loyalty. A Cat attacks for
        2 on the next turn."""
        t, ajani = _table(life0=3, turns=5)
        for _ in range(4):
            _loyalty(t, PLUS)
            t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        t.act(0, MINUS8, then=[on_stack(MINUS8, 0), moves(ajani, Zone.GRAVEYARD)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(MINUS8), appears(0), appears(0), appears(0)])
        t.pass_to(Step.UPKEEP, 1)
        cat = token(1)
        _attack(t, cat, 2)
        t.run()

    def test_minus_eight_rejected_when_insufficient_loyalty(self):
        t, _ajani = _table()
        t.act_illegal(0, MINUS8, note="−8 from 4")
        _loyalty(t, PLUS, note="the refused −8 spent nothing")
        t.run()
