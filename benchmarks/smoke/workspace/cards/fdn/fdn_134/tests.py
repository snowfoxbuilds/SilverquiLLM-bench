"""Reference test for FDN 134 — Ajani, Caller of the Pride.

Demonstrates **Pattern 4 — loyalty ability with targeting** (Phase D):

* ``+1`` — "Put a +1/+1 counter on *up to one* target creature": an **optional**
  loyalty target (``targeting`` may return ``[]``; the ability still activates
  with nothing chosen).
* ``−3`` — "Target creature gains flying and double strike until end of turn":
  a **required** loyalty target (``targeting`` returns ``None`` when there is no
  legal creature, so no loyalty is spent), applied as an until-end-of-turn
  continuous effect.
* ``−8`` — untargeted (create X 2/2 Cat tokens).

Targets are chosen at activation via a Player Query answered by an Intent
(pattern = the walker's name), captured on the stack object, and applied at
resolution — never re-selected. This is the loyalty analogue of the fdn_95
activated-ability exemplar.
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_134.card_impl import AjaniCallerOfThePride
from engine.abilities import AbilityError, clear_loyalty_tracking
from engine.card import Creature
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.types import CardType, Keyword, ManaCost, Phase, Supertype, Zone
from test_utils import (
    activate_loyalty_ability,
    create_game,
    resolve_stack,
    set_board_state,
)


@pytest.fixture(autouse=True)
def _reset_loyalty_tracker():
    """The once-per-turn tracker is module-level — reset around every test."""
    clear_loyalty_tracking()
    yield
    clear_loyalty_tracking()


def _bear(p, name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


def _activate_targeting(game, player, walker, index, target):
    """Drive a loyalty ability through the real activate → stack path, choosing
    *target* at activation via an Intent on *player* (pattern = walker name)."""
    player.start_intent("ajani", Intent(
        pattern=GameRef(card=frozenset({("name", walker.name)})),
        preferences=(Decision.obj(instance=target.instance_id),),
    ))
    try:
        activate_loyalty_ability(game, player, walker, index)
    finally:
        player.end_intent("ajani")


class TestAjaniProperties:
    def test_static_data(self):
        ajani = AjaniCallerOfThePride(owner=None)
        assert ajani.name == "Ajani, Caller of the Pride"
        assert ajani.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert ajani.starting_loyalty == 4
        assert ajani.loyalty == 4
        assert Supertype.LEGENDARY in ajani.supertypes
        assert "Ajani" in ajani.subtypes
        assert CardType.PLANESWALKER in ajani.card_types

    def test_loyalty_ability_targeting_shape(self):
        ajani = AjaniCallerOfThePride(owner=None)
        abilities = ajani.get_loyalty_abilities()
        assert len(abilities) == 3
        # +1 and −3 are targeted; −8 is untargeted.
        assert abilities[0].targeting is not None  # +1 (up to one)
        assert abilities[1].targeting is not None  # −3 (required)
        assert abilities[2].targeting is None      # −8
        assert [a.loyalty_cost for a in abilities] == [1, -3, -8]


class TestAjaniPlusOne:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        ajani = AjaniCallerOfThePride(owner=p1, controller=p1)
        bear = _bear(p1, "Bear")
        set_board_state(game, 0, battlefield=[ajani, bear])
        game.phase = Phase.PRECOMBAT_MAIN
        return game, p1, p2, ajani, bear

    def test_plus_one_counter_lands_on_target(self):
        game, p1, p2, ajani, bear = self._setup()
        _activate_targeting(game, p1, ajani, 0, bear)
        assert ajani.loyalty == 5                    # +1 paid
        assert not game.stack.is_empty()
        resolve_stack(game)
        assert bear.plus_one_counters == 1
        assert bear.counters.get("+1/+1") == 1

    def test_target_captured_on_stack(self):
        game, p1, p2, ajani, bear = self._setup()
        _activate_targeting(game, p1, ajani, 0, bear)
        top = game.stack.peek()
        assert top.targets == [bear]
        assert top.controller is p1

    def test_up_to_one_activates_with_no_target(self):
        """"Up to one target" is optional: with no legal creature the ability
        still activates (targeting returns []) and loyalty still changes."""
        game = create_game()
        p1, p2 = game.players
        ajani = AjaniCallerOfThePride(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ajani])   # no creatures at all
        game.phase = Phase.PRECOMBAT_MAIN
        activate_loyalty_ability(game, p1, ajani, 0)
        assert ajani.loyalty == 5                    # activated, +1 paid
        top = game.stack.peek()
        assert top.targets == []                     # nothing targeted
        resolve_stack(game)                          # resolves cleanly

    def test_once_per_turn(self):
        game, p1, p2, ajani, bear = self._setup()
        _activate_targeting(game, p1, ajani, 0, bear)
        resolve_stack(game)                          # clear the stack (sorcery speed)
        with pytest.raises(AbilityError):
            _activate_targeting(game, p1, ajani, 0, bear)
        assert ajani.loyalty == 5                     # second activation spent nothing
        # A fresh turn (tracker cleared) allows reactivation.
        clear_loyalty_tracking()
        _activate_targeting(game, p1, ajani, 0, bear)
        assert ajani.loyalty == 6


class TestAjaniMinusThree:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        ajani = AjaniCallerOfThePride(owner=p1, controller=p1)
        bear = _bear(p2, "Their Bear")
        set_board_state(game, 0, battlefield=[ajani])
        set_board_state(game, 1, battlefield=[bear])
        game.phase = Phase.PRECOMBAT_MAIN
        return game, p1, p2, ajani, bear

    def test_grants_flying_and_double_strike(self):
        game, p1, p2, ajani, bear = self._setup()
        assert Keyword.FLYING not in bear.keywords
        _activate_targeting(game, p1, ajani, 1, bear)
        assert ajani.loyalty == 1                     # 4 − 3
        resolve_stack(game)
        assert Keyword.FLYING in bear.keywords
        assert Keyword.DOUBLE_STRIKE in bear.keywords
        # The grant is a continuous effect — survives a re-derivation pass.
        game.effect_manager.apply_all(game)
        assert Keyword.FLYING in bear.keywords
        assert Keyword.DOUBLE_STRIKE in bear.keywords

    def test_required_target_no_creature_rejected_before_cost(self):
        """Required target: with no legal creature, the ability cannot be
        activated and no loyalty is spent (targeting returns None)."""
        game = create_game()
        p1, p2 = game.players
        ajani = AjaniCallerOfThePride(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ajani])   # no creatures anywhere
        game.phase = Phase.PRECOMBAT_MAIN
        with pytest.raises(AbilityError):
            activate_loyalty_ability(game, p1, ajani, 1)
        assert ajani.loyalty == 4                     # unchanged


class TestAjaniMinusEight:
    def test_creates_x_cat_tokens_equal_to_life(self):
        game = create_game()
        p1, p2 = game.players
        ajani = AjaniCallerOfThePride(owner=p1, controller=p1)
        ajani.loyalty = 8                             # enough to pay −8
        set_board_state(game, 0, battlefield=[ajani], life=3)
        game.phase = Phase.PRECOMBAT_MAIN
        activate_loyalty_ability(game, p1, ajani, 2)  # untargeted
        assert ajani.loyalty == 0
        resolve_stack(game)
        cats = [
            obj
            for obj in game.get_battlefield(p1).get_all()
            if obj.name == "Cat"
        ]
        assert len(cats) == 3
        assert all((c.base_power, c.base_toughness) == (2, 2) for c in cats)

    def test_minus_eight_rejected_when_insufficient_loyalty(self):
        game = create_game()
        p1, p2 = game.players
        ajani = AjaniCallerOfThePride(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ajani], life=5)
        game.phase = Phase.PRECOMBAT_MAIN
        with pytest.raises(AbilityError):
            activate_loyalty_ability(game, p1, ajani, 2)  # 4 − 8 < 0
        assert ajani.loyalty == 4
