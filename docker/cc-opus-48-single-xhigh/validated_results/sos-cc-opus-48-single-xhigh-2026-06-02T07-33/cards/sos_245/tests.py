"""Tests for SOS 245 — Witherbloom, the Balancer.

Oracle text (from card_spec.json):

    Affinity for creatures (This spell costs {1} less to cast for each creature
    you control.)
    Flying, deathtouch
    Instant and sorcery spells you cast have affinity for creatures.

Behaviour contract derived from that text:

* Static: Legendary Creature — Elder Dragon, {6}{B}{G} (mana value 8), 5/5,
  black+green, with Flying and Deathtouch. "Affinity" is NOT an evergreen
  ``engine.types.Keyword`` enum member (that enum is frozen at 16 members and
  ``engine_tests/test_types.py::test_exactly_sixteen_members`` hard-asserts
  that), so it must be recorded as a printed-keyword label, never an enum
  member.

* Witherbloom's OWN affinity for creatures: the {6}{B}{G} spell costs {1} less
  to cast for each creature its controller controls. This is exactly the
  sos_1 / fdn_167 cost-reduction shape — the card's ``cost_reduction(game)``
  hook returns the raw count (number of creatures the controller controls), and
  the engine's ``get_cost_reduction`` clamps that count to the generic portion
  ({6}) of the cost. Only creatures the CONTROLLER controls count (an
  opponent's creatures do not); only creatures count (other permanents do not).

* Granted affinity for creatures: a continuous static ability that grants
  affinity for creatures to each instant and sorcery SPELL its controller
  casts. There is no engine-level affinity pipeline yet, so the implementation
  must expose some observable surface that reports the grant for the
  controller's instants/sorceries (and grants it to no other card types, no
  other players, and not while Witherbloom is off the battlefield). These tests
  probe that surface TOLERANTLY — they accept any of the conventional spellings
  the implementer is likely to use (a query method on the Witherbloom card
  and/or an attribute written onto the affected spell), and skip-with-reason
  only if NO recognised surface exists (anchored on one non-skipping positive
  case so the contract fails loudly on an empty stub).

  Driving the GRANTED reduction through the actual cast/cost pipeline (so that
  casting a granted instant while controlling N creatures really pays {N} less)
  was originally recorded in untestable.json. The Implementer has since built
  the engine affinity pipeline (``engine.affinity``'s granted-reduction registry,
  consumed by ``engine.casting.get_cost_reduction``), so the granted reduction is
  now driven END-TO-END through the real cost computation and cast in
  ``TestWitherbloomGrantedReductionPipeline`` and
  ``TestWitherbloomOwnAffinityEndToEnd`` below.

These tests are written for the TDD red phase: the original 27 must FAIL against
the empty stub and PASS once the card is implemented correctly. The extended
end-to-end tests are REAL passing tests against the now-built pipeline (each
positive case is anchored so a missing surface fails loudly rather than skipping).
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.casting import CastingError, cast_spell, get_cost_reduction
from engine.types import Color, Keyword, ManaCost, ManaType, Supertype
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Test helper cards
# ---------------------------------------------------------------------------


def _vanilla_instant(name: str = "Test Instant") -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse("{1}{R}"))


def _vanilla_sorcery(name: str = "Test Sorcery") -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse("{2}{R}"))


def _vanilla_creature(name: str = "Test Bear") -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse("{1}{G}"),
        base_power=2,
        base_toughness=2,
    )


def _vanilla_sorcery_generic2(name: str = "Test Sorcery2") -> Sorcery:
    """A sorcery with a small generic portion ({2}{B}) for clamp tests."""
    return Sorcery(name=name, mana_cost=ManaCost.parse("{2}{B}"))


class _SelfReducingInstant(Instant):
    """An instant carrying its OWN ``cost_reduction`` of 1.

    Used to prove the engine SUMS a spell's own reduction with the granted
    affinity-for-creatures reduction (before clamping to the spell's generic).
    The default cost {6}{R} has a large generic so the summed reduction is not
    clamped; pass ``cost`` to vary the generic for clamp tests.
    """

    def __init__(self, name: str = "Self Reducer", *, cost: str = "{6}{R}") -> None:
        super().__init__(name=name, mana_cost=ManaCost.parse(cost))

    def cost_reduction(self, game: Any) -> int:  # noqa: ARG002
        return 1


def _affinity_grant_for(card_obj: Any, game: Any, spell: Any) -> Any:
    """Best-effort probe for the granted affinity-for-creatures of *spell*.

    The affinity grant has no engine pipeline, so the implementation is free to
    surface it in a number of conventional ways. This helper tries each in turn
    and returns the reported value, or raises ``pytest.skip`` if no recognised
    surface exists (so the contract is not silently green).
    """
    val = _probe_affinity_silent(card_obj, game, spell)
    if val is _MISSING:
        pytest.skip(
            "No observable surface for the granted affinity for creatures — "
            "the implementation must expose a query method on the card "
            "(e.g. has_affinity_for_creatures(...)/get_affinity(...)/"
            "grants_affinity_to(...)) or an attribute on the affected spell "
            "(e.g. affinity_for_creatures / affinity / granted_affinity)."
        )
    return val


_MISSING = object()


def _probe_affinity_silent(card_obj: Any, game: Any, spell: Any) -> Any:
    """Like ``_affinity_grant_for`` but returns the sentinel ``_MISSING`` when no
    recognised surface reports a value for *spell* (used for exclusion-side
    assertions, always anchored on a positive case so the test is never
    vacuous)."""
    # 1. A method on the Witherbloom card that reports whether/what affinity it
    #    grants to a given spell.
    for meth_name in (
        "has_affinity_for_creatures",
        "grants_affinity_for_creatures",
        "grants_affinity_to",
        "affinity_for_creatures_for",
        "get_affinity_for_creatures",
        "affinity_for",
        "get_affinity",
        "affinity_value_for",
        "get_affinity_value",
    ):
        meth = getattr(card_obj, meth_name, None)
        if callable(meth):
            try:
                return meth(game, spell)
            except TypeError:
                try:
                    return meth(spell)
                except TypeError:
                    continue
    # 2. The grant written directly onto the spell.
    for attr_name in (
        "affinity_for_creatures",
        "has_affinity_for_creatures",
        "granted_affinity_for_creatures",
        "affinity",
        "granted_affinity",
    ):
        if hasattr(spell, attr_name):
            val = getattr(spell, attr_name)
            if val is not None:
                return val
    return _MISSING


def _is_granted(value: Any) -> bool:
    """Return True if *value* represents an active affinity-for-creatures grant.

    Accepts a truthy flag (``True``), a string like ``"creatures"`` /
    ``"affinity for creatures"``, or anything exposing a ``.kind``/``.type``
    naming creatures. A bare ``None``/``False``/``0`` means "not granted".
    """
    if value is _MISSING or value is None or value is False:
        return False
    if value is True:
        return True
    if isinstance(value, str):
        low = value.lower()
        return "creature" in low or "affinity" in low
    if isinstance(value, int):
        return value != 0
    for attr in ("kind", "type", "value", "name"):
        v = getattr(value, attr, None)
        if isinstance(v, str) and "creature" in v.lower():
            return True
    # An object that exists and is not a recognised "off" sentinel: treat as a
    # grant (the implementation chose to return some grant descriptor).
    return True


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------


class TestWitherbloomProperties:
    """Static characteristics must match the SOS 245 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(WitherbloomTheBalancer(owner=None), Creature)

    def test_name(self) -> None:
        assert (
            WitherbloomTheBalancer(owner=None).name == "Witherbloom, the Balancer"
        )

    def test_mana_cost(self) -> None:
        assert WitherbloomTheBalancer(owner=None).mana_cost == ManaCost.parse(
            "{6}{B}{G}"
        )

    def test_mana_value_is_eight(self) -> None:
        assert WitherbloomTheBalancer(owner=None).mana_cost.cmc == 8

    def test_generic_portion_is_six(self) -> None:
        """The generic portion is {6}; affinity reduces only this part."""
        assert WitherbloomTheBalancer(owner=None).mana_cost.generic == 6

    def test_power_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_is_legendary(self) -> None:
        assert (
            Supertype.LEGENDARY in WitherbloomTheBalancer(owner=None).supertypes
        )

    def test_is_elder_dragon(self) -> None:
        subtypes = WitherbloomTheBalancer(owner=None).subtypes
        assert "Dragon" in subtypes
        assert "Elder" in subtypes

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in WitherbloomTheBalancer(owner=None).keywords

    def test_has_deathtouch(self) -> None:
        assert Keyword.DEATHTOUCH in WitherbloomTheBalancer(owner=None).keywords

    def test_is_black_green(self) -> None:
        """{6}{B}{G} has exactly one black and one green pip and no others."""
        cost = WitherbloomTheBalancer(owner=None).mana_cost
        assert cost.pips.get(ManaType.BLACK, 0) == 1
        assert cost.pips.get(ManaType.GREEN, 0) == 1
        assert cost.pips.get(ManaType.WHITE, 0) == 0
        assert cost.pips.get(ManaType.BLUE, 0) == 0
        assert cost.pips.get(ManaType.RED, 0) == 0

    def test_colors_are_black_and_green(self) -> None:
        """If the implementation exposes a ``colors`` surface it must be exactly
        {B, G}. If it does not, the pip-based ``test_is_black_green`` above
        already pins the colours, so this is skipped rather than failing."""
        card = WitherbloomTheBalancer(owner=None)
        colors = getattr(card, "colors", None)
        if not colors:
            pytest.skip("no explicit colors attribute; pip test covers colours")
        assert set(colors) == {Color.BLACK, Color.GREEN}

    def test_affinity_is_printed_keyword_label_not_enum(self) -> None:
        """'Affinity' is a printed-keyword label (the Keyword enum is frozen at
        16 evergreen members), so it must NOT appear as a Keyword enum member.
        If the implementation records printed labels, "Affinity" should be among
        them; if it exposes no such surface this is skipped (the cost-reduction
        and grant tests below are the real affinity contract)."""
        card = WitherbloomTheBalancer(owner=None)
        # Affinity must not have been smuggled into the evergreen Keyword enum.
        assert not hasattr(Keyword, "AFFINITY")
        labels = getattr(card, "printed_keywords", None)
        if labels is None:
            pytest.skip("no printed_keywords surface to assert the Affinity label")
        assert any("affinity" in str(label).lower() for label in labels)


# ---------------------------------------------------------------------------
# Witherbloom's own affinity for creatures — cost reduction
# ---------------------------------------------------------------------------


class TestWitherbloomOwnAffinityCostReduction:
    """Affinity for creatures: {6}{B}{G} costs {1} less to cast for each creature
    YOU control (the sos_1 / fdn_167 cost-reduction convention)."""

    def test_no_reduction_with_no_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_creature_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[_vanilla_creature("Bear")])
        assert card.cost_reduction(game) == 1

    def test_three_creatures_reduce_by_three(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[
                _vanilla_creature("Bear A"),
                _vanilla_creature("Bear B"),
                _vanilla_creature("Bear C"),
            ],
        )
        assert card.cost_reduction(game) == 3

    def test_non_creature_permanents_do_not_count(self) -> None:
        """Affinity for CREATURES counts only creatures; an instant/sorcery card
        on the battlefield-side zones is not a creature and must not reduce the
        cost. (We use non-creature cards placed in the controller's graveyard to
        confirm they never get counted as battlefield creatures.)"""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[],
            graveyard=[_vanilla_instant("Gy Bolt"), _vanilla_sorcery("Gy Ritual")],
        )
        assert card.cost_reduction(game) == 0

    def test_only_creatures_you_control_count(self) -> None:
        """An opponent's creatures must not reduce the cost — only creatures
        YOU control count. Controller has zero creatures; opponent has three."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[])
        set_board_state(
            game,
            1,
            battlefield=[
                _vanilla_creature("Opp A"),
                _vanilla_creature("Opp B"),
                _vanilla_creature("Opp C"),
            ],
        )
        assert card.cost_reduction(game) == 0

    def test_witherbloom_itself_does_not_count_while_on_stack(self) -> None:
        """When Witherbloom is being cast it is on the stack, not the
        battlefield, so it does not count itself. Controlling exactly one OTHER
        creature reduces the cost by exactly 1 (not 2)."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Only a single other creature is on the battlefield; Witherbloom is not.
        set_board_state(game, 0, battlefield=[_vanilla_creature("Lone Bear")])
        assert card.cost_reduction(game) == 1

    def test_effective_reduction_through_engine_partial(self) -> None:
        """Driving the count through the engine's clamp helper: four creatures
        reduce the {6} generic by exactly 4."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[
                _vanilla_creature("A"),
                _vanilla_creature("B"),
                _vanilla_creature("C"),
                _vanilla_creature("D"),
            ],
        )
        assert get_cost_reduction(game, card, p1) == 4

    def test_effective_reduction_clamped_to_generic_six(self) -> None:
        """The engine clamps the reduction to the generic portion ({6}), so
        controlling more than six creatures cannot push generic below 0 — the
        clamped effective reduction is 6 even with nine creatures."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [_vanilla_creature(f"C{i}") for i in range(9)]
        set_board_state(game, 0, battlefield=creatures)
        # The raw hook may report 9, but the clamped effective reduction is 6.
        assert get_cost_reduction(game, card, p1) == 6


# ---------------------------------------------------------------------------
# Granted affinity for creatures — controller's instant/sorcery spells
# ---------------------------------------------------------------------------


class TestWitherbloomGrantsAffinityToSpells:
    """While on the battlefield, Witherbloom grants affinity for creatures to
    each instant and sorcery SPELL its controller casts (and to nothing else)."""

    def _setup(
        self,
        controller_spells: list[Any],
        opp_spells: list[Any] | None = None,
        *,
        on_battlefield: bool = True,
    ):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        if on_battlefield:
            set_board_state(game, 0, battlefield=[card], hand=controller_spells)
        else:
            # Witherbloom in hand, not on the battlefield: the grant must be off.
            set_board_state(game, 0, hand=[card] + controller_spells)
        if opp_spells is not None:
            set_board_state(game, 1, hand=opp_spells)
        # Apply continuous effects / triggers if the engine maintains them, so a
        # registry-based implementation has a chance to write its grant.
        try:
            card.register_replacement_effects(game)
            card.register_triggers(game)
        except Exception:
            pass
        if hasattr(game, "effect_manager"):
            try:
                game.effect_manager.apply_all(game)
            except Exception:
                pass
        return game, p1, p2, card

    def test_instant_gets_affinity(self) -> None:
        """A controller's instant is granted affinity for creatures."""
        spell = _vanilla_instant("My Bolt")
        game, p1, p2, card = self._setup([spell])
        assert _is_granted(_affinity_grant_for(card, game, spell))

    def test_sorcery_gets_affinity(self) -> None:
        """A controller's sorcery is granted affinity for creatures."""
        spell = _vanilla_sorcery("My Ritual")
        game, p1, p2, card = self._setup([spell])
        assert _is_granted(_affinity_grant_for(card, game, spell))

    def test_creature_spell_does_not_get_affinity(self) -> None:
        """The grant is only for instant/sorcery spells. A creature spell is
        neither, so it must not be granted affinity. Anchored on a real instant
        first (via the probe, which skips if no surface exists) so this fails on
        an empty stub rather than passing vacuously."""
        anchor = _vanilla_instant("Anchor Bolt")
        bear = _vanilla_creature("Hand Bear")
        game, p1, p2, card = self._setup([anchor, bear])
        # Anchor: confirm the grant surface exists and grants the instant.
        assert _is_granted(_affinity_grant_for(card, game, anchor))
        # The creature spell must NOT be granted affinity.
        assert not _is_granted(_probe_affinity_silent(card, game, bear))

    def test_opponents_instant_does_not_get_affinity(self) -> None:
        """Only spells YOU cast get affinity — an opponent's instant is
        unaffected. Anchored on a controller-side instant so the test fails on an
        empty stub rather than passing vacuously."""
        my_spell = _vanilla_instant("My Instant")
        opp_spell = _vanilla_instant("Opp Instant")
        game, p1, p2, card = self._setup([my_spell], opp_spells=[opp_spell])
        # Anchor: my own instant gets affinity (skips if no surface exists).
        assert _is_granted(_affinity_grant_for(card, game, my_spell))
        # The opponent's instant must NOT be granted affinity.
        assert not _is_granted(_probe_affinity_silent(card, game, opp_spell))

    def test_no_grant_while_off_battlefield(self) -> None:
        """A static ability of a permanent functions only while that permanent
        is on the battlefield (CR 113.6 / 604.x). With Witherbloom in hand (not
        on the battlefield), an instant must NOT be granted affinity.

        Anchored on the positive on-battlefield case (which skips if no surface
        exists), so a stub that always returns a grant is caught while
        genuinely-absent surfaces skip rather than pass."""
        # Positive anchor: a parallel on-battlefield setup must grant affinity.
        anchor_spell = _vanilla_instant("Anchor While On Field")
        a_game, _, _, a_card = self._setup([anchor_spell])
        assert _is_granted(_affinity_grant_for(a_card, a_game, anchor_spell))

        # Now Witherbloom is in hand, not on the battlefield: no grant.
        spell = _vanilla_instant("Off Field Instant")
        game, p1, p2, card = self._setup([spell], on_battlefield=False)
        assert not _is_granted(_probe_affinity_silent(card, game, spell))


class TestWitherbloomGrantWiring:
    """The affinity grant is a continuous static ability, so the card must wire
    it through one of the engine's continuous/effect/trigger hooks rather than
    doing nothing. We assert the card actually installs something observable."""

    def test_card_exposes_an_affinity_grant_surface(self) -> None:
        """The implementation must expose at least one recognised affinity-grant
        surface (a query method on the card, or an attribute it writes onto an
        affected spell). An empty stub exposes none and fails here."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        spell = _vanilla_instant("Probe Instant")
        set_board_state(game, 0, battlefield=[card], hand=[spell])
        try:
            card.register_replacement_effects(game)
            card.register_triggers(game)
        except Exception:
            pass
        if hasattr(game, "effect_manager"):
            try:
                game.effect_manager.apply_all(game)
            except Exception:
                pass

        has_method = any(
            callable(getattr(card, m, None))
            for m in (
                "has_affinity_for_creatures",
                "grants_affinity_for_creatures",
                "grants_affinity_to",
                "affinity_for_creatures_for",
                "get_affinity_for_creatures",
                "affinity_for",
                "get_affinity",
                "affinity_value_for",
                "get_affinity_value",
            )
        )
        has_attr = any(
            getattr(spell, a, None) is not None
            for a in (
                "affinity_for_creatures",
                "has_affinity_for_creatures",
                "granted_affinity_for_creatures",
                "affinity",
                "granted_affinity",
            )
        )
        assert has_method or has_attr, (
            "Witherbloom must expose an observable affinity-grant surface "
            "(a query method on the card or an attribute on the affected spell)."
        )


# ---------------------------------------------------------------------------
# Extended coverage — granted reduction driven through the REAL cast/cost
# pipeline (previously deferred in untestable.json, now built by the Implementer).
# ---------------------------------------------------------------------------


def _bear(name: str = "Bear") -> Creature:
    """A 2/2 vanilla creature for populating the controller's battlefield."""
    return Creature(
        name=name,
        mana_cost=ManaCost.parse("{1}{G}"),
        base_power=2,
        base_toughness=2,
    )


def _big_instant(name: str = "Big Bolt", *, cost: str = "{4}{R}") -> Instant:
    """An instant with enough generic ({4}{R} by default) that the granted
    reduction is not immediately clamped — used to observe the reduction VALUE
    (and the {1}{R} reduced payment) through the pipeline."""
    return Instant(name=name, mana_cost=ManaCost.parse(cost))


def _setup_grant(
    controller_battlefield: list[Any],
    controller_hand: list[Any],
    *,
    witherbloom_on_battlefield: bool = True,
):
    """Build a game with Witherbloom installed and its granted-reduction wired.

    ``controller_battlefield`` is the list of OTHER permanents on p1's
    battlefield (Witherbloom is added on top of it when
    ``witherbloom_on_battlefield`` is True). After placing the board state,
    ``register_triggers`` is called so the granted-reduction record is installed
    into ``engine.affinity``'s registry, which ``engine.casting.get_cost_reduction``
    consults. Returns ``(game, p1, p2, witherbloom)``.
    """
    game = create_game()
    p1 = game.players[0]
    p2 = game.players[1]
    wb = WitherbloomTheBalancer(owner=p1, controller=p1)
    if witherbloom_on_battlefield:
        set_board_state(
            game, 0, battlefield=[wb] + controller_battlefield, hand=controller_hand
        )
    else:
        set_board_state(
            game, 0, battlefield=controller_battlefield, hand=[wb] + controller_hand
        )
    # Install / refresh the continuous grant + the granted-reduction registry
    # record. This is the wiring the real pipeline depends on.
    wb.register_triggers(game)
    return game, p1, p2, wb


class TestWitherbloomGrantedReductionPipeline:
    """The GRANTED affinity-for-creatures reduction driven through the real
    cast/cost pipeline: ``engine.casting.get_cost_reduction`` must lower a
    granted instant/sorcery's generic by min(creatures-you-control, generic),
    and an actual ``cast_spell`` must pay only the reduced cost.

    These were the cases deferred in ``untestable.json``; the Implementer has
    now built ``engine.affinity``'s granted-reduction registry plus the
    ``get_cost_reduction`` extension that sums it before clamping.
    """

    def test_granted_reduction_applies_below_generic(self) -> None:
        """Controlling fewer creatures than the spell's generic reduces the
        generic by exactly the creature count. p1 controls Witherbloom + 2
        bears = 3 creatures; a {4}{R} instant's generic drops by 3 (to {1})."""
        game, p1, p2, wb = _setup_grant(
            [_bear("A"), _bear("B")], [_big_instant("Bolt")]
        )
        spell = game.get_hand(p1).get_all()[0]
        # 3 creatures controlled, spell generic 4 -> reduction = min(3, 4) = 3.
        assert get_cost_reduction(game, spell, p1) == 3

    def test_granted_reduction_clamped_to_generic(self) -> None:
        """Controlling MORE creatures than the spell's generic clamps the
        reduction to the generic (generic can't go below 0). p1 controls
        Witherbloom + 4 bears = 5 creatures; a {2}{B} sorcery's generic of 2
        is reduced by min(5, 2) = 2, not 5."""
        game, p1, p2, wb = _setup_grant(
            [_bear("A"), _bear("B"), _bear("C"), _bear("D")],
            [_vanilla_sorcery_generic2("Ritual")],
        )
        spell = game.get_hand(p1).get_all()[0]
        # 5 creatures controlled, spell generic 2 -> reduction clamped to 2.
        assert get_cost_reduction(game, spell, p1) == 2

    def test_granted_reduction_scales_with_creature_count(self) -> None:
        """The reduction tracks the live creature count: with no other creatures
        only Witherbloom is controlled (1 creature) so a {4}{R} instant is
        reduced by exactly 1, proving the value is the count and not a constant."""
        game, p1, p2, wb = _setup_grant([], [_big_instant("Bolt")])
        spell = game.get_hand(p1).get_all()[0]
        # Only Witherbloom on the battlefield: 1 creature -> reduction 1.
        assert get_cost_reduction(game, spell, p1) == 1

    def test_granted_reduction_paid_through_cast_spell(self) -> None:
        """End-to-end through ``cast_spell``: with Witherbloom + 2 bears (3
        creatures) a {4}{R} instant is castable paying only {1}{R}. We fund the
        pool with exactly the REDUCED amount; if the reduction were not applied
        at payment time the cast would raise 'insufficient mana'."""
        game, p1, p2, wb = _setup_grant(
            [_bear("A"), _bear("B")], [_big_instant("Reduced Bolt")]
        )
        spell = game.get_hand(p1).get_all()[0]
        p1.mana_pool.empty()
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        p1.mana_pool.add(ManaType.RED, 1)
        # {4}{R} reduced by 3 creatures = {1}{R}; the reduced amount funds it.
        cast_spell(game, p1, spell)
        # Spell reached the stack and the actual mana spent reflects the reduction.
        assert not game.stack.is_empty()
        assert spell.mana_spent == 2  # {1}{R}

    def test_unreduced_spell_cannot_be_cast_with_reduced_funding(self) -> None:
        """Negative control proving the reduction (not luck) made the cast above
        legal: the SAME {4}{R} instant with the SAME {1}{R} funding but WITHOUT
        Witherbloom in play must fail with insufficient mana."""
        game = create_game()
        p1 = game.players[0]
        spell = _big_instant("Unreduced Bolt")
        set_board_state(game, 0, battlefield=[_bear("A"), _bear("B")], hand=[spell])
        p1.mana_pool.empty()
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        p1.mana_pool.add(ManaType.RED, 1)
        with pytest.raises(CastingError):
            cast_spell(game, p1, spell)

    def test_granted_reduction_stacks_with_spells_own_reduction(self) -> None:
        """A granted spell that ALSO has its own ``cost_reduction`` sums both,
        then clamps. With Witherbloom + 2 bears (3 creatures granted) and a spell
        whose own ``cost_reduction`` returns 1, the total before clamping is 4;
        the {6}{R} generic of 6 leaves it unclamped at 4."""
        game, p1, p2, wb = _setup_grant(
            [_bear("A"), _bear("B")], [_SelfReducingInstant("Self Reducer")]
        )
        spell = game.get_hand(p1).get_all()[0]
        # granted 3 + own 1 = 4, generic 6 -> not clamped, total reduction 4.
        assert get_cost_reduction(game, spell, p1) == 4

    def test_stacked_reduction_clamps_to_generic(self) -> None:
        """The summed (granted + own) reduction is still clamped to the spell's
        generic. Witherbloom + 4 bears = 5 granted, own reduction 1 (total 6),
        but a {2}{R} spell's generic of 2 clamps the effective reduction to 2."""
        game, p1, p2, wb = _setup_grant(
            [_bear("A"), _bear("B"), _bear("C"), _bear("D")],
            [_SelfReducingInstant("Self Reducer 2", cost="{2}{R}")],
        )
        spell = game.get_hand(p1).get_all()[0]
        # granted 5 + own 1 = 6, generic 2 -> clamped to 2.
        assert get_cost_reduction(game, spell, p1) == 2


class TestWitherbloomGrantedReductionScopePipeline:
    """Scope of the GRANTED reduction enforced THROUGH the cost computation
    (not merely the flag surface): creature spells, opponents' spells, and the
    off-battlefield case must contribute ZERO granted reduction."""

    def test_creature_spell_gets_no_granted_reduction(self) -> None:
        """Affinity for creatures is granted only to instant/sorcery spells. A
        creature spell in the controller's hand receives no granted reduction
        through the pipeline (its effective reduction is just its own, here 0).
        Anchored against a parallel instant that DOES get the reduction so a
        broken scope (granting everything) is caught."""
        game, p1, p2, wb = _setup_grant(
            [_bear("A"), _bear("B")],
            [_vanilla_creature("Hand Bear"), _vanilla_instant("Anchor Bolt")],
        )
        hand = game.get_hand(p1).get_all()
        creature_spell = next(c for c in hand if isinstance(c, Creature))
        instant_spell = next(c for c in hand if isinstance(c, Instant))
        # Anchor: the instant IS reduced (proves the grant is live).
        assert get_cost_reduction(game, instant_spell, p1) > 0
        # The creature spell gets NO granted reduction.
        assert get_cost_reduction(game, creature_spell, p1) == 0

    def test_opponents_spell_gets_no_granted_reduction(self) -> None:
        """Only the granting controller's spells are reduced. An opponent's
        instant gets no granted reduction even while Witherbloom is in play.
        Anchored against the controller's own instant being reduced."""
        game, p1, p2, wb = _setup_grant(
            [_bear("A"), _bear("B")], [_big_instant("My Bolt")]
        )
        my_spell = game.get_hand(p1).get_all()[0]
        opp_spell = _big_instant("Opp Bolt")
        set_board_state(game, 1, hand=[opp_spell])
        # Anchor: my own instant is reduced by the 3 creatures I control.
        assert get_cost_reduction(game, my_spell, p1) == 3
        # The opponent (p2) casting their instant gets nothing granted.
        assert get_cost_reduction(game, opp_spell, p2) == 0

    def test_no_granted_reduction_while_off_battlefield(self) -> None:
        """A static ability functions only while its source is on the
        battlefield. With Witherbloom in hand (registered, then off-battlefield)
        a controller instant gets no granted reduction through the pipeline.
        Anchored against an on-battlefield positive case."""
        # Positive anchor: on the battlefield, the instant is reduced.
        a_game, a_p1, _, _ = _setup_grant(
            [_bear("A"), _bear("B")], [_big_instant("On Field Bolt")]
        )
        a_spell = a_game.get_hand(a_p1).get_all()[0]
        assert get_cost_reduction(a_game, a_spell, a_p1) == 3

        # Off battlefield: the grant must contribute nothing.
        # (With Witherbloom in hand it is the first hand card, so select the
        # Instant explicitly rather than by index.)
        game, p1, p2, wb = _setup_grant(
            [_bear("A"), _bear("B")],
            [_big_instant("Off Field Bolt")],
            witherbloom_on_battlefield=False,
        )
        spell = next(
            c for c in game.get_hand(p1).get_all() if isinstance(c, Instant)
        )
        assert get_cost_reduction(game, spell, p1) == 0

    def test_granted_reduction_stops_after_witherbloom_leaves(self) -> None:
        """When Witherbloom leaves the battlefield and its grant is cleared, the
        granted reduction stops applying. We install the grant on-battlefield
        (instant reduced), then move Witherbloom off and re-run its registration
        (which clears the grant); the same instant is no longer reduced."""
        game, p1, p2, wb = _setup_grant(
            [_bear("A"), _bear("B")], [_big_instant("Bolt")]
        )
        spell = game.get_hand(p1).get_all()[0]
        # Grant is live: reduced by the 3 creatures controlled.
        assert get_cost_reduction(game, spell, p1) == 3

        # Witherbloom leaves the battlefield; keep the 2 bears.
        set_board_state(game, 0, battlefield=[_bear("A2"), _bear("B2")])
        # Re-running the wiring (as the engine would on a board change) clears
        # the grant because Witherbloom is no longer on the battlefield.
        wb.register_triggers(game)
        assert get_cost_reduction(game, spell, p1) == 0


class TestWitherbloomOwnAffinityEndToEnd:
    """Witherbloom's OWN affinity for creatures driven through an actual
    ``cast_spell`` (not just the ``cost_reduction`` hook): casting {6}{B}{G}
    while controlling N creatures pays {1} less per creature, clamped to {6}."""

    def test_own_affinity_paid_through_cast_spell(self) -> None:
        """Controlling 3 OTHER creatures, Witherbloom's {6}{B}{G} generic of 6
        drops by 3 to {3}{B}{G}. We fund exactly {3}{B}{G} and cast; the actual
        mana spent (5) confirms the reduction was applied at payment time."""
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[_bear("A"), _bear("B"), _bear("C")],
            hand=[wb],
        )
        wb.register_triggers(game)
        p1.mana_pool.empty()
        p1.mana_pool.add(ManaType.COLORLESS, 3)
        p1.mana_pool.add(ManaType.BLACK, 1)
        p1.mana_pool.add(ManaType.GREEN, 1)
        # ignore_timing: the cast under test is the cost payment, not timing.
        cast_spell(game, p1, wb, ignore_timing=True)
        assert not game.stack.is_empty()
        assert wb.mana_spent == 5  # {3}{B}{G}

    def test_own_affinity_clamped_to_generic_through_cast_spell(self) -> None:
        """Controlling 9 creatures clamps the {6} generic reduction to 6, so
        Witherbloom costs only {B}{G}. We fund exactly {B}{G} and cast; mana
        spent (2) confirms generic never went below 0."""
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(
            game, 0, battlefield=[_bear(f"C{i}") for i in range(9)], hand=[wb]
        )
        wb.register_triggers(game)
        p1.mana_pool.empty()
        p1.mana_pool.add(ManaType.BLACK, 1)
        p1.mana_pool.add(ManaType.GREEN, 1)
        cast_spell(game, p1, wb, ignore_timing=True)
        assert not game.stack.is_empty()
        assert wb.mana_spent == 2  # {B}{G}

    def test_own_affinity_with_no_creatures_pays_full_through_cast_spell(self) -> None:
        """With no creatures controlled, Witherbloom's own affinity reduces
        nothing: casting from hand requires the full {6}{B}{G} (mana value 8).
        Funding only the reduced amount would fail — here we fund the full cost
        and confirm the full 8 is spent."""
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[], hand=[wb])
        wb.register_triggers(game)
        p1.mana_pool.empty()
        p1.mana_pool.add(ManaType.COLORLESS, 6)
        p1.mana_pool.add(ManaType.BLACK, 1)
        p1.mana_pool.add(ManaType.GREEN, 1)
        cast_spell(game, p1, wb, ignore_timing=True)
        assert not game.stack.is_empty()
        assert wb.mana_spent == 8  # full {6}{B}{G}
