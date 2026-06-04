"""Tests for SOS 97 — Ral Zarek, Guest Lecturer.

Ral Zarek, Guest Lecturer is a Legendary Planeswalker — Ral with starting
loyalty 3 and four loyalty abilities:

  +1: Surveil 2.
  -1: Any number of target players each discard a card.
  -2: Return target creature card with mana value 3 or less from your
      graveyard to the battlefield.
  -7: Flip five coins. Target opponent skips their next X turns, where X is
      the number of coins that came up heads.

These tests follow the planeswalker reference convention in
``cards/fdn/fdn_134`` (loyalty abilities are obtained via
``get_loyalty_abilities()`` and resolved by calling ``ability.effect(game)``;
the per-ability target is supplied on the planeswalker via ``_resolve_target``
/ a chosen-targets attribute the Implementer reads).

TDD red phase — the implementation stub is empty, so these are expected to
fail until the card is implemented.
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pw(owner: Any = None, controller: Any = None) -> RalZarekGuestLecturer:
    return RalZarekGuestLecturer(owner=owner, controller=controller)


def _abilities(pw: RalZarekGuestLecturer) -> list[LoyaltyAbility]:
    return pw.get_loyalty_abilities()


def _ability_with_cost(pw: RalZarekGuestLecturer, cost: int) -> LoyaltyAbility:
    for ab in _abilities(pw):
        if ab.loyalty_cost == cost:
            return ab
    raise AssertionError(f"No loyalty ability with cost {cost}")


def _set_target(pw: RalZarekGuestLecturer, target: Any) -> None:
    """Supply the single-target a loyalty ability reads.

    The fdn_134 reference reads ``_resolve_target``; some sos cards use
    ``chosen_targets``. Set both so the test stays robust to whichever the
    Implementer follows.
    """
    pw._resolve_target = target
    pw.chosen_targets = [target] if target is not None else []


def _set_targets(pw: RalZarekGuestLecturer, targets: list[Any]) -> None:
    """Supply a multi-target list (for the −1 'any number of players')."""
    pw._resolve_targets = list(targets)
    pw.chosen_targets = list(targets)
    pw._resolve_target = targets[0] if targets else None


def _bear(name: str = "Grizzly Bears", power: int = 2, toughness: int = 2,
          cost: str = "{1}{G}") -> Creature:
    return Creature(
        name=name,
        base_power=power,
        base_toughness=toughness,
        mana_cost=ManaCost.parse(cost),
    )


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------

class TestRalZarekProperties:
    def test_is_planeswalker_subclass(self) -> None:
        assert isinstance(_make_pw(), Planeswalker)

    def test_name(self) -> None:
        assert _make_pw().name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        assert _make_pw().mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_is_planeswalker_card_type(self) -> None:
        assert CardType.PLANESWALKER in _make_pw().card_types

    def test_is_legendary(self) -> None:
        pw = _make_pw()
        # Legendary may be modelled via supertypes or card_types.
        legendary = (
            Supertype.LEGENDARY in getattr(pw, "supertypes", set())
            or CardType.LEGENDARY in pw.card_types
        )
        assert legendary

    def test_subtype_ral(self) -> None:
        assert "Ral" in _make_pw().subtypes

    def test_starting_loyalty_is_three(self) -> None:
        pw = _make_pw()
        assert pw.starting_loyalty == 3
        assert pw.loyalty == 3


# ---------------------------------------------------------------------------
# Loyalty ability declaration
# ---------------------------------------------------------------------------

class TestRalZarekLoyaltyAbilities:
    def test_declares_four_abilities(self) -> None:
        assert len(_abilities(_make_pw())) == 4

    def test_loyalty_costs(self) -> None:
        costs = sorted(ab.loyalty_cost for ab in _abilities(_make_pw()))
        assert costs == [-7, -2, -1, +1]

    def test_each_is_loyalty_ability(self) -> None:
        for ab in _abilities(_make_pw()):
            assert isinstance(ab, LoyaltyAbility)


# ---------------------------------------------------------------------------
# +1: Surveil 2
# ---------------------------------------------------------------------------

class TestRalZarekPlusOneSurveil:
    def _setup(self):
        game = create_game()
        controller = game.players[0]
        pw = _make_pw(owner=controller, controller=controller)
        set_board_state(game, 0, battlefield=[pw])
        return game, controller, pw

    def test_surveil_keeps_top_cards_on_top(self) -> None:
        """With a yes/keep script, top two stay on top of the library and
        none are milled to the graveyard."""
        game, controller, pw = self._setup()
        lib = game.get_library(controller)
        top = _bear("Top Card")
        second = _bear("Second Card")
        third = _bear("Third Card")
        # add() pushes to top, so add third first to keep top/second on top.
        for c in (third, second, top):
            c.owner = controller
            lib.add(c)
        controller._script.extend([True, True])  # keep both on top

        _ability_with_cost(pw, +1).effect(game)

        gy = game.get_graveyard(controller)
        assert gy.contains(top) is False
        assert gy.contains(second) is False
        assert lib.contains(top)
        assert lib.contains(second)

    def test_surveil_can_mill_cards_to_graveyard(self) -> None:
        """Surveil 2 lets the controller put looked-at cards into the
        graveyard; a 'put to graveyard' choice moves them there."""
        game, controller, pw = self._setup()
        lib = game.get_library(controller)
        a = _bear("Card A")
        b = _bear("Card B")
        for c in (b, a):
            c.owner = controller
            lib.add(c)
        # Script both surveil decisions as "to graveyard".
        controller._script.extend([False, False])

        _ability_with_cost(pw, +1).effect(game)

        gy = game.get_graveyard(controller)
        assert gy.contains(a)
        assert gy.contains(b)

    def test_surveil_looks_at_only_top_two(self) -> None:
        """Surveil 2 never touches the third card from the top."""
        game, controller, pw = self._setup()
        lib = game.get_library(controller)
        a = _bear("Card A")
        b = _bear("Card B")
        c = _bear("Card C")
        for card in (c, b, a):
            card.owner = controller
            lib.add(card)
        controller._script.extend([False, False])  # mill both looked at

        _ability_with_cost(pw, +1).effect(game)

        # Third card is untouched — still in library, not graveyard.
        assert lib.contains(c)
        assert game.get_graveyard(controller).contains(c) is False


# ---------------------------------------------------------------------------
# -1: Any number of target players each discard a card
# ---------------------------------------------------------------------------

class TestRalZarekMinusOneDiscard:
    def _setup(self):
        game = create_game()
        controller, opponent = game.players[0], game.players[1]
        pw = _make_pw(owner=controller, controller=controller)
        set_board_state(game, 0, battlefield=[pw])
        return game, controller, opponent, pw

    def test_targeted_opponent_discards_a_card(self) -> None:
        game, controller, opponent, pw = self._setup()
        card = _bear("Discardable")
        set_board_state(game, 1, hand=[card])
        # opponent chooses which card to discard
        opponent._script.append(card)
        _set_targets(pw, [opponent])

        _ability_with_cost(pw, -1).effect(game)

        assert game.get_hand(opponent).contains(card) is False
        assert game.get_graveyard(opponent).contains(card)

    def test_multiple_targets_each_discard(self) -> None:
        game, controller, opponent, pw = self._setup()
        c1 = _bear("C1")
        c2 = _bear("C2")
        set_board_state(game, 0, battlefield=[pw], hand=[c1])
        set_board_state(game, 1, hand=[c2])
        controller._script.append(c1)
        opponent._script.append(c2)
        _set_targets(pw, [controller, opponent])

        _ability_with_cost(pw, -1).effect(game)

        assert game.get_hand(controller).contains(c1) is False
        assert game.get_graveyard(controller).contains(c1)
        assert game.get_hand(opponent).contains(c2) is False
        assert game.get_graveyard(opponent).contains(c2)

    def test_zero_targets_is_a_no_op(self) -> None:
        """'Any number' allows choosing zero players — nothing is discarded."""
        game, controller, opponent, pw = self._setup()
        card = _bear("Stays")
        set_board_state(game, 1, hand=[card])
        _set_targets(pw, [])

        _ability_with_cost(pw, -1).effect(game)

        assert game.get_hand(opponent).contains(card)

    def test_targeted_player_with_empty_hand_does_not_crash(self) -> None:
        game, controller, opponent, pw = self._setup()
        set_board_state(game, 1, hand=[])
        _set_targets(pw, [opponent])

        # Should not raise even though there's nothing to discard.
        _ability_with_cost(pw, -1).effect(game)

        assert len(game.get_hand(opponent).get_all()) == 0


# ---------------------------------------------------------------------------
# -2: Return target creature (mv <= 3) from your graveyard to battlefield
# ---------------------------------------------------------------------------

class TestRalZarekMinusTwoReanimate:
    def _setup(self):
        game = create_game()
        controller, opponent = game.players[0], game.players[1]
        pw = _make_pw(owner=controller, controller=controller)
        set_board_state(game, 0, battlefield=[pw])
        return game, controller, opponent, pw

    def test_returns_low_mv_creature_to_battlefield(self) -> None:
        game, controller, opponent, pw = self._setup()
        creature = _bear("Cheap Beast", cost="{1}{G}")  # mv 2
        set_board_state(game, 0, battlefield=[pw], graveyard=[creature])
        _set_target(pw, creature)

        _ability_with_cost(pw, -2).effect(game)

        assert game.get_battlefield(controller).contains(creature)
        assert game.get_graveyard(controller).contains(creature) is False

    def test_mv_exactly_three_is_eligible(self) -> None:
        game, controller, opponent, pw = self._setup()
        creature = _bear("Three Drop", cost="{1}{G}{G}")  # mv 3
        set_board_state(game, 0, battlefield=[pw], graveyard=[creature])
        _set_target(pw, creature)

        _ability_with_cost(pw, -2).effect(game)

        assert game.get_battlefield(controller).contains(creature)

    def test_no_target_is_a_no_op(self) -> None:
        game, controller, opponent, pw = self._setup()
        creature = _bear("Stays Dead", cost="{1}{G}")
        set_board_state(game, 0, battlefield=[pw], graveyard=[creature])
        _set_target(pw, None)

        _ability_with_cost(pw, -2).effect(game)

        # Not returned because no target was chosen.
        assert game.get_graveyard(controller).contains(creature)
        assert game.get_battlefield(controller).contains(creature) is False


# ---------------------------------------------------------------------------
# -7: Flip five coins; opponent skips next X turns (X = heads).
# ---------------------------------------------------------------------------

class TestRalZarekUltimate:
    def _setup(self):
        game = create_game()
        controller, opponent = game.players[0], game.players[1]
        pw = _make_pw(owner=controller, controller=controller)
        set_board_state(game, 0, battlefield=[pw])
        pw.loyalty = 7
        return game, controller, opponent, pw

    def _patch_coins(self, monkeypatch, heads_count: int) -> None:
        """Force exactly five coin flips with ``heads_count`` heads.

        Patches random.random/randint/choice so the result is deterministic
        regardless of which the Implementer uses to flip coins.
        """
        import random as _random

        results = [True] * heads_count + [False] * (5 - heads_count)
        seq = list(results)

        def fake_choice(opts):
            return seq.pop(0) if seq else False

        def fake_randint(a, b):
            return 1 if (seq.pop(0) if seq else False) else 0

        def fake_random():
            return 0.0 if (seq.pop(0) if seq else False) else 0.9

        monkeypatch.setattr(_random, "choice", fake_choice, raising=False)
        monkeypatch.setattr(_random, "randint", fake_randint, raising=False)
        monkeypatch.setattr(_random, "random", fake_random, raising=False)

    def test_three_heads_skips_three_turns(self, monkeypatch) -> None:
        game, controller, opponent, pw = self._setup()
        self._patch_coins(monkeypatch, heads_count=3)
        _set_target(pw, opponent)

        _ability_with_cost(pw, -7).effect(game)

        opp_index = game.players.index(opponent)
        skips = getattr(opponent, "skipped_turns", None)
        if skips is None:
            skips = getattr(game, "skipped_turns", {}).get(opp_index)
        assert skips == 3

    def test_zero_heads_skips_no_turns(self, monkeypatch) -> None:
        game, controller, opponent, pw = self._setup()
        self._patch_coins(monkeypatch, heads_count=0)
        _set_target(pw, opponent)

        _ability_with_cost(pw, -7).effect(game)

        opp_index = game.players.index(opponent)
        skips = getattr(opponent, "skipped_turns", None)
        if skips is None:
            skips = getattr(game, "skipped_turns", {}).get(opp_index, 0)
        assert (skips or 0) == 0

    def test_five_heads_skips_five_turns(self, monkeypatch) -> None:
        game, controller, opponent, pw = self._setup()
        self._patch_coins(monkeypatch, heads_count=5)
        _set_target(pw, opponent)

        _ability_with_cost(pw, -7).effect(game)

        opp_index = game.players.index(opponent)
        skips = getattr(opponent, "skipped_turns", None)
        if skips is None:
            skips = getattr(game, "skipped_turns", {}).get(opp_index)
        assert skips == 5

    def test_ultimate_targets_an_opponent(self, monkeypatch) -> None:
        """The skip count must be applied to the targeted opponent, not the
        controller."""
        game, controller, opponent, pw = self._setup()
        self._patch_coins(monkeypatch, heads_count=2)
        _set_target(pw, opponent)

        _ability_with_cost(pw, -7).effect(game)

        ctrl_index = game.players.index(controller)
        ctrl_skips = getattr(controller, "skipped_turns", None)
        if ctrl_skips is None:
            ctrl_skips = getattr(game, "skipped_turns", {}).get(ctrl_index, 0)
        assert (ctrl_skips or 0) == 0


# ---------------------------------------------------------------------------
# Loyalty cost payment via the activation pipeline
# ---------------------------------------------------------------------------

class TestRalZarekLoyaltyCosts:
    def test_plus_one_raises_loyalty(self) -> None:
        """Activating +1 through the engine pipeline raises loyalty 3 -> 4."""
        from engine.abilities import (
            LoyaltyAbilityInstance,
            activate_ability,
            clear_loyalty_tracking,
        )
        from engine.types import Phase

        game = create_game()
        controller = game.players[0]
        pw = _make_pw(owner=controller, controller=controller)
        set_board_state(game, 0, battlefield=[pw])
        # Give the controller library cards so Surveil 2 has something to look at.
        lib = game.get_library(controller)
        for c in (_bear("L2"), _bear("L1")):
            c.owner = controller
            lib.add(c)
        controller._script.extend([True, True])  # keep both on top
        clear_loyalty_tracking()
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.priority_player_index = 0

        plus = _ability_with_cost(pw, +1)
        inst = LoyaltyAbilityInstance(
            source=pw,
            controller=controller,
            loyalty_cost=plus.loyalty_cost,
            effect=plus.effect,
        )
        activate_ability(game, controller, inst)
        assert pw.loyalty == 4

    def test_minus_seven_requires_seven_loyalty(self) -> None:
        """At starting loyalty 3 the ultimate cannot be paid; the engine's
        loyalty-cost guard should reject it."""
        from engine.abilities import (
            AbilityError,
            LoyaltyAbilityInstance,
            activate_ability,
            clear_loyalty_tracking,
        )
        from engine.types import Phase, Step

        game = create_game()
        controller = game.players[0]
        pw = _make_pw(owner=controller, controller=controller)
        set_board_state(game, 0, battlefield=[pw])
        clear_loyalty_tracking()
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.priority_player_index = 0
        ult = _ability_with_cost(pw, -7)
        inst = LoyaltyAbilityInstance(
            source=pw,
            controller=controller,
            loyalty_cost=ult.loyalty_cost,
            effect=ult.effect,
        )
        with pytest.raises(AbilityError):
            activate_ability(game, controller, inst)
