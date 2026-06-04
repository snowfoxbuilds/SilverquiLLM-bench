"""Tests for SOS 226 — Silverquill, the Disputant.

Oracle text (from card_spec.json):

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1. (As you cast that
    spell, you may sacrifice a creature with power 1 or greater. When you do,
    copy the spell and you may choose new targets for the copy.)

Behaviour contract derived from that text:

* Static: Legendary Creature — Elder Dragon, {2}{W}{B}, 4/4, black+white, with
  Flying and Vigilance.
* Casualty-granting static ability: while Silverquill is on the battlefield,
  every instant and sorcery SPELL its controller casts "has casualty 1"
  (CR 702.153). Casualty 1 means: as an additional cost you MAY sacrifice a
  creature with power 1 or greater; when you do, copy the spell and may choose
  new targets for the copy.

  There is no engine-level casualty pipeline, so the implementation must expose
  some observable surface that reports the casualty value (1) for an
  instant/sorcery the controller casts (and grants it to no other card types /
  no other players). These tests probe that surface TOLERANTLY: they accept any
  of the conventional spellings the implementer is likely to use (a query method
  on the Silverquill card and/or an attribute written onto the affected spell),
  and skip-with-reason only if NO recognised surface exists (so the contract is
  never silently green).

  The copy/sacrifice RESOLUTION mechanic (paying the casualty cost by
  sacrificing a power>=1 creature, then producing a copy with optional new
  targets) is recorded in untestable.json: no engine casualty pipeline exists to
  assert it against yet.

These tests are written for the TDD red phase: they must FAIL against the empty
stub and PASS once the card is implemented correctly.
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.events import SpellCastTriggeredEvent
from engine.stack import StackObject
from engine.types import Color, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Test helper cards
# ---------------------------------------------------------------------------


def _vanilla_instant(name: str = "Test Instant") -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse("{1}{R}"))


def _vanilla_sorcery(name: str = "Test Sorcery") -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse("{2}{G}"))


def _vanilla_creature(name: str = "Test Bear") -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse("{1}{G}"),
        base_power=2,
        base_toughness=2,
    )


def _casualty_value_for(card_obj: Any, game: Any, spell: Any) -> Any:
    """Best-effort probe for the granted casualty value of *spell*.

    The casualty mechanic has no engine pipeline, so the implementation is free
    to surface the grant in a number of conventional ways. This helper tries
    each in turn and returns the reported value, or raises ``pytest.skip`` if no
    recognised surface exists (so the contract is not silently green).
    """
    # 1. A method on the Silverquill card that reports the casualty value it
    #    grants to a given spell.
    for meth_name in (
        "casualty_value_for",
        "get_casualty_value",
        "casualty_for",
        "get_casualty",
        "casualty_value",
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
    for attr_name in ("casualty_value", "casualty", "granted_casualty"):
        val = getattr(spell, attr_name, None)
        if val is not None:
            return val
    pytest.skip(
        "No observable surface for the granted casualty value — implementation "
        "must expose casualty_value_for(...)/get_casualty_value(...) on the "
        "card or a casualty_value attribute on the affected spell."
    )


def _probe_casualty_silent(card_obj: Any, game: Any, spell: Any) -> Any:
    """Like ``_casualty_value_for`` but returns None instead of skipping when no
    recognised surface reports a value for *spell* (used for the exclusion-side
    assertions, anchored on a positive case so the test is never vacuous)."""
    for meth_name in (
        "casualty_value_for",
        "get_casualty_value",
        "casualty_for",
        "get_casualty",
        "casualty_value",
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
    for attr_name in ("casualty_value", "casualty", "granted_casualty"):
        val = getattr(spell, attr_name, None)
        if val is not None:
            return val
    return None


def _coerce_to_one(value: Any) -> bool:
    """Return True if *value* represents casualty N == 1.

    Accepts an int (1), a bool True coerced via int, a string spelling like
    "1" or "casualty 1", or anything exposing ``.cmc``/``.value``/``.n`` == 1.
    """
    if value is None or value is False:
        return False
    if value is True:
        # A bare True flag means "has casualty" but does not encode N; treat as
        # NOT a confirmation of the specific value 1.
        return False
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        digits = "".join(ch for ch in value if ch.isdigit())
        return digits == "1"
    for attr in ("value", "n", "amount", "cmc"):
        v = getattr(value, attr, None)
        if isinstance(v, int):
            return v == 1
    return False


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------


class TestSilverquillProperties:
    """Static characteristics must match the SOS 226 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(SilverquillTheDisputant(owner=None), Creature)

    def test_name(self) -> None:
        assert SilverquillTheDisputant(owner=None).name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        assert SilverquillTheDisputant(owner=None).mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_mana_value_is_four(self) -> None:
        assert SilverquillTheDisputant(owner=None).mana_cost.cmc == 4

    def test_power_toughness(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in SilverquillTheDisputant(owner=None).supertypes

    def test_is_elder_dragon(self) -> None:
        subtypes = SilverquillTheDisputant(owner=None).subtypes
        assert "Dragon" in subtypes
        assert "Elder" in subtypes

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in SilverquillTheDisputant(owner=None).keywords

    def test_has_vigilance(self) -> None:
        assert Keyword.VIGILANCE in SilverquillTheDisputant(owner=None).keywords

    def test_is_white_black(self) -> None:
        """{2}{W}{B} has exactly one white and one black pip and no others."""
        cost = SilverquillTheDisputant(owner=None).mana_cost
        assert cost.pips.get(ManaType.WHITE, 0) == 1
        assert cost.pips.get(ManaType.BLACK, 0) == 1
        assert cost.pips.get(ManaType.RED, 0) == 0
        assert cost.pips.get(ManaType.BLUE, 0) == 0
        assert cost.pips.get(ManaType.GREEN, 0) == 0

    def test_colors_are_black_and_white(self) -> None:
        """If the implementation exposes a ``colors`` surface it must be exactly
        {B, W}. If it does not, the pip-based ``test_is_white_black`` above
        already pins the colours, so this is skipped rather than failing."""
        card = SilverquillTheDisputant(owner=None)
        colors = getattr(card, "colors", None)
        if not colors:
            pytest.skip("no explicit colors attribute; pip test covers colours")
        color_set = set(colors)
        assert color_set == {Color.WHITE, Color.BLACK}

    def test_casualty_is_printed_keyword_label_not_enum(self) -> None:
        """'Casualty' is a printed-keyword label (the Keyword enum is frozen at
        16 evergreen members), so it must NOT appear as a Keyword enum member.
        If the implementation records printed labels, "Casualty" should be among
        them; if it exposes no such surface this is skipped (the grant-surface
        tests below are the real contract)."""
        card = SilverquillTheDisputant(owner=None)
        # Casualty must not have been smuggled into the evergreen Keyword enum.
        assert not hasattr(Keyword, "CASUALTY")
        labels = getattr(card, "printed_keywords", None)
        if labels is None:
            pytest.skip("no printed_keywords surface to assert the Casualty label")
        assert any("casualty" in str(label).lower() for label in labels)


# ---------------------------------------------------------------------------
# Casualty-granting static ability — queryable / observable grant surface
# ---------------------------------------------------------------------------


class TestSilverquillCasualtyGrant:
    """While on the battlefield, Silverquill grants casualty 1 to each instant
    and sorcery SPELL its controller casts."""

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
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        if on_battlefield:
            set_board_state(game, 0, battlefield=[card], hand=controller_spells)
        else:
            # Silverquill in hand, not on the battlefield: the grant must be off.
            set_board_state(game, 0, hand=[card] + controller_spells)
        if opp_spells is not None:
            set_board_state(game, 1, hand=opp_spells)
        # Apply continuous effects if the engine maintains them, so a
        # layer-based implementation has a chance to write its grant.
        if hasattr(game, "effect_manager"):
            try:
                card.register_replacement_effects(game)
                card.register_triggers(game)
            except Exception:
                pass
            try:
                game.effect_manager.apply_all(game)
            except Exception:
                pass
        return game, p1, p2, card

    def test_instant_gets_casualty_one(self) -> None:
        spell = _vanilla_instant("My Bolt")
        game, p1, p2, card = self._setup([spell])
        value = _casualty_value_for(card, game, spell)
        assert _coerce_to_one(value)

    def test_sorcery_gets_casualty_one(self) -> None:
        spell = _vanilla_sorcery("My Ritual")
        game, p1, p2, card = self._setup([spell])
        value = _casualty_value_for(card, game, spell)
        assert _coerce_to_one(value)

    def test_creature_spell_does_not_get_casualty(self) -> None:
        """Casualty is granted only to instant/sorcery spells. A creature spell
        is neither, so it must not be granted casualty. We anchor on a real
        instant first (via the probe, which skips if no surface exists) so this
        fails on an empty stub rather than passing vacuously."""
        anchor = _vanilla_instant("Anchor Bolt")
        bear = _vanilla_creature("Hand Bear")
        game, p1, p2, card = self._setup([anchor, bear])
        # Anchor: confirm the grant surface exists and reports 1 for the instant.
        assert _coerce_to_one(_casualty_value_for(card, game, anchor))
        # The creature spell must NOT be granted casualty 1.
        assert not _coerce_to_one(_probe_casualty_silent(card, game, bear))

    def test_opponents_instant_does_not_get_casualty(self) -> None:
        """Only spells YOU cast get casualty — an opponent's instant is
        unaffected. Anchored on a controller-side instant so the test fails on
        an empty stub rather than passing vacuously."""
        my_spell = _vanilla_instant("My Instant")
        opp_spell = _vanilla_instant("Opp Instant")
        game, p1, p2, card = self._setup([my_spell], opp_spells=[opp_spell])
        # Anchor: my own instant gets casualty 1 (skips if no surface exists).
        assert _coerce_to_one(_casualty_value_for(card, game, my_spell))
        # The opponent's instant must NOT be granted casualty.
        assert not _coerce_to_one(_probe_casualty_silent(card, game, opp_spell))

    def test_no_grant_while_off_battlefield(self) -> None:
        """A static ability of a permanent functions only while that permanent
        is on the battlefield (CR 113.6 / 604.x). With Silverquill in hand (not
        on the battlefield), an instant must NOT be granted casualty.

        This anchors on the positive case from ``test_instant_gets_casualty_one``
        (which skips if no surface exists), so a stub that always returns a value
        is caught, while genuinely-absent surfaces skip rather than pass."""
        # Positive anchor: a parallel on-battlefield setup must grant casualty.
        anchor_spell = _vanilla_instant("Anchor While On Field")
        a_game, _, _, a_card = self._setup([anchor_spell])
        assert _coerce_to_one(_casualty_value_for(a_card, a_game, anchor_spell))

        # Now Silverquill is in hand, not on the battlefield: no grant.
        spell = _vanilla_instant("Off Field Instant")
        game, p1, p2, card = self._setup([spell], on_battlefield=False)
        assert not _coerce_to_one(_probe_casualty_silent(card, game, spell))


# ---------------------------------------------------------------------------
# Casualty grant wiring — the card must install its continuous grant
# ---------------------------------------------------------------------------


class TestSilverquillGrantWiring:
    """The casualty grant is a continuous static ability, so the card must wire
    it through one of the engine's continuous/effect/trigger hooks rather than
    doing nothing. We assert the card actually installs something observable."""

    def test_card_exposes_a_casualty_grant_surface(self) -> None:
        """The implementation must expose at least one recognised casualty-grant
        surface (a query method on the card, or an attribute it writes onto an
        affected spell). An empty stub exposes none and fails here."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        spell = _vanilla_instant("Probe Instant")
        set_board_state(game, 0, battlefield=[card], hand=[spell])
        if hasattr(game, "effect_manager"):
            try:
                card.register_replacement_effects(game)
                card.register_triggers(game)
                game.effect_manager.apply_all(game)
            except Exception:
                pass

        has_method = any(
            callable(getattr(card, m, None))
            for m in (
                "casualty_value_for",
                "get_casualty_value",
                "casualty_for",
                "get_casualty",
                "casualty_value",
            )
        )
        has_attr = any(
            getattr(spell, a, None) is not None
            for a in ("casualty_value", "casualty", "granted_casualty")
        )
        assert has_method or has_attr, (
            "Silverquill must expose an observable casualty-grant surface "
            "(a query method on the card or an attribute on the affected spell)."
        )


# ===========================================================================
# Extended coverage — casualty RESOLUTION mechanic (CR 702.153a/c)
#
# These tests were previously deferred to untestable.json (no engine casualty
# pipeline). The Implementer has since built the additive engine.casualty
# framework and wired it into the card, so the three deferred requirements are
# now testable as REAL passing tests:
#
#   1. Pay-by-sacrifice records the payment and moves the creature to the GY.
#   2. The power>=1 legality boundary (power 0 illegal, power 1 legal).
#   3. Copy-on-payment puts a copy on the stack with optional new targets.
#   4. Declining is a clean no-op (no sacrifice, no copy).
#   5. Scope: opponents' / creature spells get no casualty offer.
#
# The framework API (confirmed in engine/casualty.py and impl-rationale.md):
#   is_legal_casualty_sacrifice(creature, value) -> bool
#   legal_casualty_sacrifices(game, player, value) -> list
#   pay_casualty(game, player, spell, creature, value=None) -> bool
#   was_casualty_paid(spell) -> bool        # reads spell.casualty_paid
#   copy_spell_on_casualty(game, player, spell, new_targets=None) -> StackObject|None
#   offer_casualty(game, player, spell, value=None) -> StackObject|None
#   set_casualty_value(card, value) / get_casualty_value(card)
# ===========================================================================


def _power_creature(name: str, power: int, toughness: int = 1) -> Creature:
    """A creature with an explicit printed power (for the legality boundary)."""
    return Creature(
        name=name,
        mana_cost=ManaCost.parse("{1}{R}"),
        base_power=power,
        base_toughness=toughness,
    )


def _put_spell_on_stack(game: Any, player: Any, spell: Any, targets: list[Any] | None = None) -> StackObject:
    """Push *spell* onto the stack as a StackObject under *player*'s control.

    ``copy_spell_on_casualty`` locates the original on the stack by identity
    (``so.source is spell``), so the casualty copy needs the spell to be a live
    stack object. ``set_board_state`` only fills zones, so this models the
    "spell on the stack" state directly.
    """
    spell.controller = player
    spell.owner = player
    stack_obj = StackObject(source=spell, controller=player, targets=list(targets or []))
    game.stack.push(stack_obj)
    return stack_obj


def _grant_value_on(spell: Any) -> int:
    """Set casualty 1 on *spell* via the framework and return the value."""
    from engine.casualty import CASUALTY_ONE, set_casualty_value

    set_casualty_value(spell, CASUALTY_ONE)
    return CASUALTY_ONE


class TestCasualtyPayBySacrifice:
    """CR 702.153a — paying casualty sacrifices a power>=1 creature and records
    the payment on the spell."""

    def test_pay_casualty_sacrifices_creature_to_graveyard(self) -> None:
        """Paying casualty by sacrificing a power>=1 creature moves it from the
        battlefield to the owner's graveyard."""
        from engine.casualty import pay_casualty

        game = create_game()
        p1 = game.players[0]
        bear = _power_creature("Sac Bear", power=2)
        spell = _vanilla_instant("Paid Bolt")
        set_board_state(game, 0, battlefield=[bear])
        _put_spell_on_stack(game, p1, spell)
        _grant_value_on(spell)

        paid = pay_casualty(game, p1, spell, bear)

        assert paid is True
        assert not game.get_battlefield(p1).contains(bear), (
            "the sacrificed creature must leave the battlefield"
        )
        assert game.get_graveyard(p1).contains(bear), (
            "the sacrificed creature must be put into its owner's graveyard"
        )

    def test_pay_casualty_records_payment_on_spell(self) -> None:
        """A paid casualty cost is recorded so the copy trigger can observe it
        (``spell.casualty_paid == True`` / ``was_casualty_paid``)."""
        from engine.casualty import pay_casualty, was_casualty_paid

        game = create_game()
        p1 = game.players[0]
        bear = _power_creature("Sac Bear", power=2)
        spell = _vanilla_instant("Recorded Bolt")
        set_board_state(game, 0, battlefield=[bear])
        _put_spell_on_stack(game, p1, spell)
        _grant_value_on(spell)

        # Before payment, nothing is recorded.
        assert was_casualty_paid(spell) is False
        assert getattr(spell, "casualty_paid", False) is False

        pay_casualty(game, p1, spell, bear)

        assert was_casualty_paid(spell) is True
        assert spell.casualty_paid is True

    def test_pay_casualty_rejects_creature_not_controlled(self) -> None:
        """A creature the caster does not control is not a legal casualty
        sacrifice: nothing is sacrificed and no payment is recorded."""
        from engine.casualty import pay_casualty, was_casualty_paid

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        opp_bear = _power_creature("Their Bear", power=3)
        spell = _vanilla_instant("Bad Bolt")
        set_board_state(game, 0, battlefield=[])
        set_board_state(game, 1, battlefield=[opp_bear])
        _put_spell_on_stack(game, p1, spell)
        _grant_value_on(spell)

        paid = pay_casualty(game, p1, spell, opp_bear)

        assert paid is False
        assert game.get_battlefield(p2).contains(opp_bear), (
            "an opponent's creature must not be sacrificed by the caster's casualty"
        )
        assert was_casualty_paid(spell) is False


class TestCasualtyPowerThreshold:
    """CR 702.153a — the casualty 1 legality boundary: power 0 is illegal, power
    1 (or greater) is legal."""

    def test_power_zero_creature_is_not_a_legal_sacrifice(self) -> None:
        from engine.casualty import is_legal_casualty_sacrifice

        wall = _power_creature("Power Zero Wall", power=0, toughness=4)
        assert is_legal_casualty_sacrifice(wall, 1) is False

    def test_power_one_creature_is_a_legal_sacrifice(self) -> None:
        from engine.casualty import is_legal_casualty_sacrifice

        goblin = _power_creature("Power One Goblin", power=1)
        assert is_legal_casualty_sacrifice(goblin, 1) is True

    def test_higher_power_creature_is_a_legal_sacrifice(self) -> None:
        """Power strictly greater than the threshold is also legal (>= boundary)."""
        from engine.casualty import is_legal_casualty_sacrifice

        ogre = _power_creature("Big Ogre", power=5)
        assert is_legal_casualty_sacrifice(ogre, 1) is True

    def test_legal_candidate_set_excludes_power_zero_includes_power_one(self) -> None:
        """The observable candidate set for casualty 1 excludes a power-0 creature
        and includes a power-1 creature controlled by the caster."""
        from engine.casualty import legal_casualty_sacrifices

        game = create_game()
        p1 = game.players[0]
        wall = _power_creature("Boundary Wall", power=0, toughness=4)
        goblin = _power_creature("Boundary Goblin", power=1)
        set_board_state(game, 0, battlefield=[wall, goblin])

        candidates = legal_casualty_sacrifices(game, p1, 1)

        assert goblin in candidates, "a power-1 creature is a legal casualty 1 sacrifice"
        assert wall not in candidates, "a power-0 creature is NOT a legal casualty 1 sacrifice"

    def test_pay_casualty_with_power_zero_creature_fails(self) -> None:
        """Trying to pay casualty 1 with a power-0 creature is rejected: no
        sacrifice, no recorded payment (the boundary enforced at payment time)."""
        from engine.casualty import pay_casualty, was_casualty_paid

        game = create_game()
        p1 = game.players[0]
        wall = _power_creature("Pay Wall Zero", power=0, toughness=4)
        spell = _vanilla_instant("Boundary Bolt")
        set_board_state(game, 0, battlefield=[wall])
        _put_spell_on_stack(game, p1, spell)
        _grant_value_on(spell)

        paid = pay_casualty(game, p1, spell, wall)

        assert paid is False
        assert game.get_battlefield(p1).contains(wall), (
            "a power-0 creature must not be sacrificed for casualty 1"
        )
        assert was_casualty_paid(spell) is False


class TestCasualtyCopyOnPayment:
    """CR 702.153c — when the casualty cost is paid, a copy of the spell is put
    onto the stack under the caster's control, with optional new targets."""

    def test_copy_is_put_on_the_stack_under_controller_control(self) -> None:
        from engine.casualty import copy_spell_on_casualty, pay_casualty

        game = create_game()
        p1 = game.players[0]
        bear = _power_creature("Copy Bear", power=2)
        spell = _vanilla_instant("Copied Bolt")
        set_board_state(game, 0, battlefield=[bear])
        original = _put_spell_on_stack(game, p1, spell)
        _grant_value_on(spell)
        pay_casualty(game, p1, spell, bear)

        stack_before = len(game.stack)
        copy_obj = copy_spell_on_casualty(game, p1, spell)

        assert copy_obj is not None, "paying casualty must produce a copy"
        assert len(game.stack) == stack_before + 1, (
            "the copy must be put onto the stack in addition to the original"
        )
        assert game.stack.peek() is copy_obj, "the copy is the top of the stack"
        assert copy_obj.controller is p1, "the copy is controlled by the caster"
        assert copy_obj.source is not spell, (
            "the copy is a distinct object, not the original spell"
        )
        assert getattr(copy_obj.source, "name", None) == spell.name, (
            "the copy shares the original's identity (same name)"
        )
        # The original spell remains its own stack object.
        assert original.source is spell

    def test_copy_may_take_new_targets(self) -> None:
        """The caster may choose new targets for the copy; the original spell's
        targets are unchanged (independent state)."""
        from engine.casualty import copy_spell_on_casualty, pay_casualty

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bear = _power_creature("Retarget Bear", power=2)
        spell = _vanilla_instant("Retarget Bolt")
        set_board_state(game, 0, battlefield=[bear])
        original = _put_spell_on_stack(game, p1, spell, targets=[p2])
        _grant_value_on(spell)
        pay_casualty(game, p1, spell, bear)

        copy_obj = copy_spell_on_casualty(game, p1, spell, new_targets=[p1])

        assert copy_obj is not None
        assert copy_obj.targets == [p1], "the copy uses the chosen new targets"
        assert original.targets == [p2], (
            "choosing new targets for the copy must not mutate the original's targets"
        )

    def test_copy_defaults_to_original_targets_when_not_retargeted(self) -> None:
        """Declining to choose new targets keeps the original targets on the copy
        (CR 702.153a: 'you MAY choose new targets')."""
        from engine.casualty import copy_spell_on_casualty, pay_casualty

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bear = _power_creature("Keep Bear", power=2)
        spell = _vanilla_instant("Keep Bolt")
        set_board_state(game, 0, battlefield=[bear])
        _put_spell_on_stack(game, p1, spell, targets=[p2])
        _grant_value_on(spell)
        pay_casualty(game, p1, spell, bear)

        copy_obj = copy_spell_on_casualty(game, p1, spell)

        assert copy_obj is not None
        assert copy_obj.targets == [p2], (
            "with no new targets chosen, the copy keeps the original's targets"
        )

    def test_no_copy_when_spell_not_on_stack(self) -> None:
        """If the spell is not on the stack there is nothing to copy (a guard, so
        a stray call cannot fabricate a copy out of nothing)."""
        from engine.casualty import copy_spell_on_casualty

        game = create_game()
        p1 = game.players[0]
        spell = _vanilla_instant("Offstack Bolt")
        # Spell deliberately NOT pushed onto the stack.
        set_board_state(game, 0, hand=[spell])

        assert copy_spell_on_casualty(game, p1, spell) is None
        assert game.stack.is_empty()


class TestCasualtyOptionalDeclineAndOfferFlow:
    """CR 702.153a — casualty is OPTIONAL: the controller may decline, in which
    case nothing is sacrificed and no copy is produced. ``offer_casualty`` wires
    the whole yes/no -> choose-sacrifice -> pay -> copy flow."""

    def test_offer_accept_pays_and_copies(self) -> None:
        """Accepting the offer (scripted yes, then choosing the sacrifice)
        sacrifices the creature, records the payment, and puts a copy on the
        stack."""
        from engine.casualty import offer_casualty, was_casualty_paid

        game = create_game()
        p1 = game.players[0]
        bear = _power_creature("Offer Bear", power=2)
        spell = _vanilla_instant("Offer Bolt")
        set_board_state(game, 0, battlefield=[bear])
        _put_spell_on_stack(game, p1, spell)
        _grant_value_on(spell)
        # Script: choose_yes_no -> True (pay), choose_card -> bear.
        p1._script.clear()
        p1._script.append(True)
        p1._script.append(bear)

        result = offer_casualty(game, p1, spell)

        assert result is not None, "accepting the casualty offer produces the copy"
        assert was_casualty_paid(spell) is True
        assert game.get_graveyard(p1).contains(bear)
        assert game.stack.peek() is result, "the copy is on top of the stack"

    def test_offer_decline_is_a_clean_noop(self) -> None:
        """Declining the offer (scripted no) sacrifices nothing, records no
        payment, and produces no copy — the original spell is untouched."""
        from engine.casualty import offer_casualty, was_casualty_paid

        game = create_game()
        p1 = game.players[0]
        bear = _power_creature("Decline Bear", power=2)
        spell = _vanilla_instant("Decline Bolt")
        set_board_state(game, 0, battlefield=[bear])
        original = _put_spell_on_stack(game, p1, spell)
        _grant_value_on(spell)
        stack_before = len(game.stack)
        # Script: choose_yes_no -> False (decline).
        p1._script.clear()
        p1._script.append(False)

        result = offer_casualty(game, p1, spell)

        assert result is None, "declining the casualty offer produces no copy"
        assert was_casualty_paid(spell) is False
        assert game.get_battlefield(p1).contains(bear), (
            "declining sacrifices nothing"
        )
        assert len(game.stack) == stack_before, "no copy was put on the stack"
        assert game.stack.peek() is original, "only the original spell remains"

    def test_offer_with_no_legal_sacrifice_is_a_noop(self) -> None:
        """With no power>=1 creature available the offer cannot be paid; it is a
        no-op even before asking the controller (CR 702.153a: the additional cost
        cannot be paid)."""
        from engine.casualty import offer_casualty, was_casualty_paid

        game = create_game()
        p1 = game.players[0]
        wall = _power_creature("Only Wall", power=0, toughness=4)
        spell = _vanilla_instant("No Sac Bolt")
        set_board_state(game, 0, battlefield=[wall])
        _put_spell_on_stack(game, p1, spell)
        _grant_value_on(spell)
        stack_before = len(game.stack)

        result = offer_casualty(game, p1, spell)

        assert result is None
        assert was_casualty_paid(spell) is False
        assert game.get_battlefield(p1).contains(wall)
        assert len(game.stack) == stack_before


class TestCasualtyCastHookScope:
    """The card's cast hook (SpellCastTriggeredEvent) offers casualty ONLY for
    the controller's instants/sorceries — not opponents' spells, not creature
    spells (CR 702.153a is granted only to 'each instant and sorcery spell you
    cast')."""

    def _silverquill_game(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        game.active_player_index = 0
        silver = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silver])
        silver.register_triggers(game)
        return game, p1, p2, silver

    def test_controllers_instant_offers_casualty(self) -> None:
        """A positive anchor: casting the controller's instant fires exactly one
        casualty trigger onto the stack (so the exclusion tests below are not
        vacuous)."""
        game, p1, p2, silver = self._silverquill_game()
        spell = _vanilla_instant("Mine Bolt")
        spell.controller = p1
        before = len(game.stack)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=spell, player=p1, controller=p1, card=spell),
        )

        assert len(game.stack) == before + 1, (
            "casting the controller's instant must push the casualty offer trigger"
        )

    def test_opponents_instant_offers_no_casualty(self) -> None:
        """An opponent's instant must not get a casualty offer (only spells YOU
        cast). Anchored against the positive case above."""
        game, p1, p2, silver = self._silverquill_game()
        opp_spell = _vanilla_instant("Theirs Bolt")
        opp_spell.controller = p2
        before = len(game.stack)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=opp_spell, player=p2, controller=p2, card=opp_spell),
        )

        assert len(game.stack) == before, (
            "an opponent's instant must not push a casualty offer trigger"
        )

    def test_creature_spell_offers_no_casualty(self) -> None:
        """A creature spell is neither instant nor sorcery, so casting it must
        not get a casualty offer."""
        game, p1, p2, silver = self._silverquill_game()
        creature_spell = _power_creature("Spell Bear", power=2)
        creature_spell.controller = p1
        before = len(game.stack)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=creature_spell, player=p1, controller=p1, card=creature_spell
            ),
        )

        assert len(game.stack) == before, (
            "a creature spell must not push a casualty offer trigger"
        )
