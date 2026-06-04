"""Tests for SOS 97 — Ral Zarek, Guest Lecturer.

Ral Zarek, Guest Lecturer — {1}{B}{B} Legendary Planeswalker — Ral — loyalty 3:

    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X
        is the number of coins that came up heads.

Contract derived from the oracle text and the engine's planeswalker
plumbing (``engine/card.py`` ``Planeswalker`` / ``LoyaltyAbility``, the FDN
reference walkers ``cards/fdn/fdn_44`` (Kaito), ``cards/fdn/fdn_134``
(Ajani), ``cards/fdn/fdn_81`` (Chandra)) plus the engine helpers in
``engine/game.py`` (``discard``, ``move_to_zone``) and the established
surveil convention in ``cards/fdn/fdn_157`` (Lightshell Duo) which uses
``controller.choose_yes_no(...)`` per top card, processed top-card-first.

Conventions exercised here (mirroring the FDN reference walkers):

* ``get_loyalty_abilities()`` returns one :class:`LoyaltyAbility` per
  printed ability, with ``loyalty_cost`` equal to the printed loyalty
  adjustment (+1, −1, −2, −7).  Each ability's ``effect`` is a callable
  taking only ``game`` — at resolution the engine invokes
  ``ability.effect(game)`` (see ``engine/abilities.py``
  ``_activate_loyalty_ability``).
* Targets chosen for a loyalty ability are stashed on the planeswalker
  before the effect runs: a single target on ``pw._resolve_target`` and a
  variable number of targets on ``pw._resolve_targets`` (the idiom used by
  Kaito / Ajani / Chandra).
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.types import (
    CardType,
    ManaCost,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _vanilla(name: str, owner: Any = None, *, mv: int = 2) -> Creature:
    """A vanilla creature whose mana value is *mv* (generic-only cost)."""
    return Creature(
        name=name,
        owner=owner,
        controller=owner,
        mana_cost=ManaCost.parse(f"{{{mv}}}") if mv > 0 else ManaCost(),
        base_power=2,
        base_toughness=2,
    )


def _filler(name: str, owner: Any = None) -> Creature:
    """A plain card object usable to fill a library/hand zone."""
    return Creature(
        name=name,
        owner=owner,
        controller=owner,
        base_power=1,
        base_toughness=1,
    )


def _ability_by_cost(pw: RalZarekGuestLecturer, cost: int) -> LoyaltyAbility:
    """Return the loyalty ability whose loyalty_cost equals *cost*."""
    matches = [a for a in pw.get_loyalty_abilities() if a.loyalty_cost == cost]
    assert matches, f"no loyalty ability with cost {cost:+d}"
    return matches[0]


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestRalZarekProperties:
    """Static card data should match the SOS 97 spec."""

    def test_name(self) -> None:
        assert RalZarekGuestLecturer(owner=None).name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        assert RalZarekGuestLecturer(owner=None).mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_is_planeswalker(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert isinstance(card, Planeswalker)
        assert CardType.PLANESWALKER in card.card_types

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in RalZarekGuestLecturer(owner=None).supertypes

    def test_has_ral_subtype(self) -> None:
        assert "Ral" in RalZarekGuestLecturer(owner=None).subtypes

    def test_starting_loyalty_is_three(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.starting_loyalty == 3
        assert card.loyalty == 3


# ---------------------------------------------------------------------------
# Loyalty ability roster
# ---------------------------------------------------------------------------


class TestRalZarekLoyaltyRoster:
    """get_loyalty_abilities() declares the four printed abilities."""

    def test_returns_four_abilities(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        assert len(abilities) == 4

    def test_each_is_loyalty_ability(self) -> None:
        for a in RalZarekGuestLecturer(owner=None).get_loyalty_abilities():
            assert isinstance(a, LoyaltyAbility)

    def test_loyalty_costs_match_spec(self) -> None:
        costs = sorted(
            a.loyalty_cost for a in RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        )
        assert costs == [-7, -2, -1, 1]


# ---------------------------------------------------------------------------
# +1: Surveil 2
# ---------------------------------------------------------------------------


class TestRalZarekSurveil:
    """+1 surveils 2 — top two cards may be put into the graveyard.

    Asserted against the engine's surveil convention (``choose_yes_no`` per
    top card, processed top-card-first; see ``cards/fdn/fdn_157``).  The
    robust invariants (card conservation, no leakage to other zones) hold
    regardless of the exact choice plumbing.
    """

    def _surveil(self, game: Any, controller: Any) -> RalZarekGuestLecturer:
        pw = RalZarekGuestLecturer(owner=controller, controller=controller)
        _ability_by_cost(pw, +1).effect(game)
        return pw

    def test_keeping_both_leaves_library_untouched(self) -> None:
        game = create_game()
        p1 = game.players[0]
        top2 = [_filler("Card A", p1), _filler("Card B", p1)]
        # Library bottom->top: [A, B] so B is the top card, A second.
        p1.zones[Zone.LIBRARY]._objects = list(top2)
        # Script "no" to every "put into graveyard?" prompt.
        p1._script.extend([False, False])

        self._surveil(game, p1)

        # Nothing moved to the graveyard; library still holds both cards.
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == 0
        assert all(p1.zones[Zone.LIBRARY].contains(c) for c in top2)

    def test_putting_both_into_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        top2 = [_filler("Card A", p1), _filler("Card B", p1)]
        p1.zones[Zone.LIBRARY]._objects = list(top2)
        # Script "yes" to both prompts.
        p1._script.extend([True, True])

        self._surveil(game, p1)

        gy = p1.zones[Zone.GRAVEYARD]
        assert all(gy.contains(c) for c in top2)
        assert len(p1.zones[Zone.LIBRARY].get_all()) == 0

    def test_card_count_is_conserved(self) -> None:
        """Surveil never creates or destroys cards: library+graveyard total
        is invariant whatever the player chooses."""
        game = create_game()
        p1 = game.players[0]
        deck = [_filler(f"Card {i}", p1) for i in range(5)]
        p1.zones[Zone.LIBRARY]._objects = list(deck)
        # Mixed choices for the (up to) two prompts.
        p1._script.extend([True, False])

        before = len(p1.zones[Zone.LIBRARY].get_all()) + len(
            p1.zones[Zone.GRAVEYARD].get_all()
        )
        self._surveil(game, p1)
        after = len(p1.zones[Zone.LIBRARY].get_all()) + len(
            p1.zones[Zone.GRAVEYARD].get_all()
        )
        assert after == before

    def test_surveil_does_not_leak_cards_to_other_zones(self) -> None:
        """Surveilled cards only ever stay on the library or go to graveyard."""
        game = create_game()
        p1 = game.players[0]
        deck = [_filler(f"Card {i}", p1) for i in range(3)]
        p1.zones[Zone.LIBRARY]._objects = list(deck)
        p1._script.extend([True, True])

        self._surveil(game, p1)

        for c in deck:
            in_lib = p1.zones[Zone.LIBRARY].contains(c)
            in_gy = p1.zones[Zone.GRAVEYARD].contains(c)
            assert in_lib != in_gy  # exactly one of the two
            assert not p1.zones[Zone.HAND].contains(c)
            assert not p1.zones[Zone.EXILE].contains(c)
            assert not p1.zones[Zone.BATTLEFIELD].contains(c)

    def test_empty_library_is_a_noop(self) -> None:
        """Surveil 2 with an empty library does nothing and does not raise."""
        game = create_game()
        p1 = game.players[0]
        assert len(p1.zones[Zone.LIBRARY].get_all()) == 0
        # No choices should be requested for an empty library.
        self._surveil(game, p1)
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == 0


# ---------------------------------------------------------------------------
# −1: Any number of target players each discard a card
# ---------------------------------------------------------------------------


class TestRalZarekDiscard:
    """−1 makes each targeted player discard a card."""

    def test_single_targeted_player_discards(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = _filler("Doomed Hand Card", p2)
        set_board_state(game, 1, hand=[card])

        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_targets = [p2]
        _ability_by_cost(pw, -1).effect(game)

        # The targeted player has discarded their (only) card.
        assert len(p2.zones[Zone.HAND].get_all()) == 0
        assert p2.zones[Zone.GRAVEYARD].contains(card)

    def test_multiple_targets_each_discard_one(self) -> None:
        game = create_game()
        p1, p2 = game.players
        c1 = _filler("P1 Card", p1)
        c2 = _filler("P2 Card", p2)
        set_board_state(game, 0, hand=[c1, _filler("P1 Extra", p1)])
        set_board_state(game, 1, hand=[c2, _filler("P2 Extra", p2)])

        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_targets = [p1, p2]
        _ability_by_cost(pw, -1).effect(game)

        # Each targeted player discarded exactly one card.
        assert len(p1.zones[Zone.HAND].get_all()) == 1
        assert len(p2.zones[Zone.HAND].get_all()) == 1
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == 1
        assert len(p2.zones[Zone.GRAVEYARD].get_all()) == 1

    def test_no_targets_is_a_noop(self) -> None:
        """"Any number of target players" allows zero — nobody discards."""
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, hand=[_filler("Safe Card", p2)])

        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_targets = []
        _ability_by_cost(pw, -1).effect(game)

        assert len(p2.zones[Zone.HAND].get_all()) == 1
        assert len(p2.zones[Zone.GRAVEYARD].get_all()) == 0

    def test_targeted_player_with_empty_hand_does_not_crash(self) -> None:
        """A targeted player with no cards simply discards nothing."""
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, hand=[])

        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_targets = [p2]
        _ability_by_cost(pw, -1).effect(game)

        assert len(p2.zones[Zone.GRAVEYARD].get_all()) == 0


# ---------------------------------------------------------------------------
# −2: Return a creature card with mana value 3 or less from your graveyard
# ---------------------------------------------------------------------------


class TestRalZarekReanimate:
    """−2 returns a low-cost creature from *your* graveyard to the battlefield."""

    def test_returns_targeted_creature_to_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = _vanilla("Reanimation Target", p1, mv=3)
        set_board_state(game, 0, graveyard=[creature])

        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = creature
        _ability_by_cost(pw, -2).effect(game)

        # Creature moved from graveyard onto the controller's battlefield.
        assert game.get_battlefield(p1).contains(creature)
        assert not p1.zones[Zone.GRAVEYARD].contains(creature)

    def test_returned_creature_is_controlled_by_you(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = _vanilla("Reanimation Target", p1, mv=1)
        set_board_state(game, 0, graveyard=[creature])

        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = creature
        _ability_by_cost(pw, -2).effect(game)

        assert creature.controller is p1
        assert game.get_battlefield(p1).contains(creature)

    def test_no_target_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        leftover = _vanilla("Stays Dead", p1, mv=2)
        set_board_state(game, 0, graveyard=[leftover])

        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = None
        _ability_by_cost(pw, -2).effect(game)

        # No target — the creature stays in the graveyard.
        assert p1.zones[Zone.GRAVEYARD].contains(leftover)
        assert not game.get_battlefield(p1).contains(leftover)

    def test_target_filter_accepts_mana_value_three_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = _vanilla("MV3 Creature", p1, mv=3)
        set_board_state(game, 0, graveyard=[creature])

        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        reqs = pw.get_targets(game)
        # Find the requirement that scopes to the graveyard (the −2 ability).
        gy_reqs = [r for r in reqs if r.zone == Zone.GRAVEYARD]
        assert gy_reqs, "expected a graveyard-scoped target requirement"
        assert any(r.filter_fn(creature) for r in gy_reqs)

    def test_target_filter_rejects_high_mana_value_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        big = _vanilla("MV4 Creature", p1, mv=4)
        set_board_state(game, 0, graveyard=[big])

        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        gy_reqs = [r for r in pw.get_targets(game) if r.zone == Zone.GRAVEYARD]
        assert gy_reqs
        # A mana value 4 creature is NOT a legal target ("3 or less").
        assert all(not r.filter_fn(big) for r in gy_reqs)

    def test_target_filter_rejects_noncreature_card(self) -> None:
        from engine.card import Sorcery

        game = create_game()
        p1 = game.players[0]
        sorcery = Sorcery(
            name="Cheap Sorcery",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}"),
        )
        set_board_state(game, 0, graveyard=[sorcery])

        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        gy_reqs = [r for r in pw.get_targets(game) if r.zone == Zone.GRAVEYARD]
        assert gy_reqs
        # Non-creature card in the graveyard is not a legal target.
        assert all(not r.filter_fn(sorcery) for r in gy_reqs)


# ---------------------------------------------------------------------------
# −7: Flip five coins; target opponent skips their next X turns
# ---------------------------------------------------------------------------


class TestRalZarekUltimate:
    """−7 flips five coins and makes a target opponent skip X turns.

    Coin flips are random, so the exact value of X is not asserted here
    (see ``untestable.json``).  What is asserted: the ability exists at the
    −7 loyalty cost and resolving it against a target opponent does not
    raise and records a non-negative, at-most-five turn skip somewhere the
    engine can observe.
    """

    def test_ultimate_exists_at_minus_seven(self) -> None:
        pw = RalZarekGuestLecturer(owner=None)
        ult = _ability_by_cost(pw, -7)
        assert ult.loyalty_cost == -7

    def test_ultimate_resolves_against_target_opponent(self) -> None:
        game = create_game()
        p1, p2 = game.players
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = p2
        # Resolving the ultimate must not raise even though the precise
        # number of skipped turns depends on the (random) coin flips.
        _ability_by_cost(pw, -7).effect(game)


# ---------------------------------------------------------------------------
# −7 (deterministic): seeded coin flips + skip-turn mechanism
# ---------------------------------------------------------------------------


def _heads_for_seed(seed: Any) -> int:
    """Ground truth: number of heads ``flip_coins(game, 5)`` yields for *seed*.

    Computed on a throwaway game seeded the same way the −7 ability seeds the
    real game (``engine.game.seed_rng`` → ``flip_coins(game, 5)``).  This keeps
    the deterministic −7 tests self-documenting and robust to RNG-internals
    changes: each test asserts against the head count this helper observes for
    the same seed rather than a hard-coded magic number.
    """
    from engine.game import flip_coins, seed_rng

    probe = create_game()
    seed_rng(probe, seed)
    return flip_coins(probe, 5)


def _end_turn(game: Any) -> None:
    """Fast-forward to CLEANUP and advance, simulating end-of-turn.

    Mirrors ``engine_tests/test_extra_turns.py::_end_turn`` so the skip-turn
    rotation is driven through the exact public API the engine documents
    (set ``Phase.ENDING`` / ``Step.CLEANUP`` then ``advance_phase``).
    """
    from engine.types import Phase, Step

    game.phase = Phase.ENDING
    game.step = Step.CLEANUP
    game.advance_phase()


class TestRalZarekUltimateDeterministic:
    """−7 under a seeded RNG: heads → skipped turns, and turns actually skip.

    The Implementer added a seedable per-game RNG (``engine.game.seed_rng`` /
    ``flip_coins``) and a per-player ``skipped_turns`` counter consumed during
    turn rotation (``GameState._pick_next_active_index`` via ``advance_phase``).
    These tests make the previously-deferred −7 requirements observable.
    """

    def test_heads_count_added_to_target_opponent_skipped_turns(self) -> None:
        """Seed the game, resolve −7 against the opponent, and assert the
        opponent's ``skipped_turns`` equals the number of heads that seed
        produces for five coin flips."""
        from engine.game import seed_rng

        seed = 0  # ground-truth head count established below for this seed.
        expected_heads = _heads_for_seed(seed)
        # Sanity: this seed must actually exercise X > 0 so the assertion is
        # meaningful (X = 0 is covered separately).
        assert expected_heads > 0

        game = create_game()
        p1, p2 = game.players
        seed_rng(game, seed)

        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = p2
        _ability_by_cost(pw, -7).effect(game)

        assert p2.skipped_turns == expected_heads

    def test_all_heads_seed_skips_five_turns(self) -> None:
        """An all-heads seed (X = 5) makes the opponent skip the maximum of
        five turns — the upper bound of the ability."""
        from engine.game import seed_rng

        seed = 4  # ground-truth: five heads for this seed.
        assert _heads_for_seed(seed) == 5

        game = create_game()
        p1, p2 = game.players
        seed_rng(game, seed)

        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = p2
        _ability_by_cost(pw, -7).effect(game)

        assert p2.skipped_turns == 5

    def test_zero_heads_seed_adds_no_skipped_turns(self) -> None:
        """A seed whose five flips yield zero heads (X = 0) adds no skipped
        turns — the opponent is not made to skip anything."""
        from engine.game import seed_rng

        seed = 5  # ground-truth: zero heads for this seed.
        assert _heads_for_seed(seed) == 0

        game = create_game()
        p1, p2 = game.players
        seed_rng(game, seed)

        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = p2
        _ability_by_cost(pw, -7).effect(game)

        assert p2.skipped_turns == 0

    def test_skipped_turns_added_to_opponent_not_controller(self) -> None:
        """The −7 adds skipped turns to the *targeted opponent*, never to the
        planeswalker's controller."""
        from engine.game import seed_rng

        seed = 0
        expected_heads = _heads_for_seed(seed)
        assert expected_heads > 0

        game = create_game()
        p1, p2 = game.players
        seed_rng(game, seed)

        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = p2
        _ability_by_cost(pw, -7).effect(game)

        # The opponent accrues the skips; the controller is untouched.
        assert p2.skipped_turns == expected_heads
        assert p1.skipped_turns == 0

    def test_ultimate_drives_opponent_to_skip_its_next_turns(self) -> None:
        """End-to-end: after the seeded −7, drive turn rotation and confirm the
        opponent's next X turns are actually skipped (it never becomes active)
        and the counter decrements back to 0.

        Controller is seat 0 (active). With normal alternation the opponent
        (seat 1) would take the very next turn; instead each of its X due turns
        is consumed by the skip counter and bounced back to the controller.
        """
        from engine.game import seed_rng

        seed = 0
        expected_heads = _heads_for_seed(seed)
        assert 0 < expected_heads <= 5

        game = create_game()
        p1, p2 = game.players
        assert game.active_player_index == 0
        seed_rng(game, seed)

        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = p2
        _ability_by_cost(pw, -7).effect(game)
        assert p2.skipped_turns == expected_heads

        # Drive the opponent's X due turns; each should be skipped, so seat 1
        # never becomes active while the counter is being burned down.
        for _ in range(expected_heads):
            _end_turn(game)
            assert game.active_player_index == 0, (
                "opponent's turn should have been skipped"
            )

        # All skips consumed; the counter is back to zero.
        assert p2.skipped_turns == 0

        # Normal alternation resumes: the opponent finally takes a turn.
        _end_turn(game)
        assert game.active_player_index == 1

    def test_skip_counter_decrements_one_per_skipped_turn(self) -> None:
        """The skip counter is consumed exactly one-per-skipped-turn (not all
        at once), so it decreases monotonically by 1 each rotation."""
        from engine.game import seed_rng

        seed = 9  # ground-truth: four heads for this seed.
        expected_heads = _heads_for_seed(seed)
        assert expected_heads >= 2  # need >1 to observe the gradual decrement.

        game = create_game()
        p1, p2 = game.players
        seed_rng(game, seed)

        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = p2
        _ability_by_cost(pw, -7).effect(game)
        assert p2.skipped_turns == expected_heads

        for remaining in range(expected_heads - 1, -1, -1):
            _end_turn(game)
            assert p2.skipped_turns == remaining

    def test_zero_heads_ultimate_does_not_skip_any_turn(self) -> None:
        """End-to-end for X = 0: with no skipped turns the opponent takes its
        normal next turn immediately."""
        from engine.game import seed_rng

        seed = 5  # zero heads.
        assert _heads_for_seed(seed) == 0

        game = create_game()
        p1, p2 = game.players
        assert game.active_player_index == 0
        seed_rng(game, seed)

        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = p2
        _ability_by_cost(pw, -7).effect(game)
        assert p2.skipped_turns == 0

        # No skip queued — normal alternation hands the next turn to seat 1.
        _end_turn(game)
        assert game.active_player_index == 1

    def test_no_target_ultimate_adds_no_skips_to_either_player(self) -> None:
        """With no target stashed the −7 is a no-op: neither player accrues
        skipped turns even under a seed that would otherwise yield heads."""
        from engine.game import seed_rng

        seed = 4  # would be five heads if a target were set.
        assert _heads_for_seed(seed) == 5

        game = create_game()
        p1, p2 = game.players
        seed_rng(game, seed)

        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = None
        _ability_by_cost(pw, -7).effect(game)

        assert p1.skipped_turns == 0
        assert p2.skipped_turns == 0

    def test_seeded_resolution_matches_standalone_flip_coins(self) -> None:
        """Cross-check: resolving the seeded −7 consumes the RNG identically to
        a standalone ``flip_coins(game, 5)`` on a same-seeded game, proving the
        ability draws its X from the documented coin-flip API."""
        from engine.game import flip_coins, seed_rng

        seed = 6
        # Ground truth via the standalone API.
        standalone = create_game()
        seed_rng(standalone, seed)
        standalone_heads = flip_coins(standalone, 5)

        game = create_game()
        p1, p2 = game.players
        seed_rng(game, seed)
        pw = RalZarekGuestLecturer(owner=p1, controller=p1)
        pw._resolve_target = p2
        _ability_by_cost(pw, -7).effect(game)

        assert p2.skipped_turns == standalone_heads
