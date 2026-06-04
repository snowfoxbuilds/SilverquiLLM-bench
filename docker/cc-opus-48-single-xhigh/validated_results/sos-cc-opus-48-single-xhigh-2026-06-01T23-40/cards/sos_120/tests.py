"""Tests for SOS 120 — Improvisation Capstone.

Improvisation Capstone is a ``{5}{R}{R}`` Sorcery — Lesson with the
**Paradigm** keyword:

    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater. You may cast any number of spells from
    among them without paying their mana costs.
    Paradigm (Then exile this spell. After you first resolve a spell with
    this name, you may cast a copy of it from exile without paying its mana
    cost at the beginning of each of your first main phases.)

The card breaks into three distinct behaviours:

1.  **Exile-until-MV-4** — exile cards one at a time off the top of the
    library, stopping as soon as the cumulative mana value of the exiled
    pile is 4 or greater (CR 614-style "until" loop). A library with fewer
    than 4 total mana value just empties; an empty library is a safe no-op.
2.  **Free-cast from among the exiled pile** — the controller *may* cast any
    number of the exiled *spells* (nonland cards) without paying their mana
    costs. Lands cannot be cast. Declining leaves the cards in exile.
3.  **Paradigm** — the spell exiles itself on resolution (instead of going to
    the graveyard), and after the controller first resolves a spell with this
    name a delayed effect lets them cast a free copy from exile at the
    beginning of each of their first (precombat) main phases.

These tests pin the spec-mandated, observable behaviour. They are written
against the public contract (``on_resolve``, the player decision interface,
and the deferred main-phase mechanism documented in KEY_DECISIONS), not
against private implementation details.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Land, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, ManaCost, ManaType
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _instant(name: str, cost: str, owner=None) -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse(cost), owner=owner)


def _sorcery(name: str, cost: str, owner=None) -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse(cost), owner=owner)


def _creature(name: str, cost: str, power: int = 2, toughness: int = 2, owner=None) -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse(cost),
        base_power=power,
        base_toughness=toughness,
        owner=owner,
    )


def _land(name: str, owner=None) -> Land:
    return Land(name=name, owner=owner)


def _set_library(game, player, cards: list) -> None:
    """Replace *player*'s library with *cards* (index -1 == top of library)."""
    library = game.get_library(player)
    for obj in library.get_all():
        library.remove(obj)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)  # appends to top


def _exiled(game, player) -> list:
    return game.get_exile(player).get_all()


def _decline_free_casts(player, n: int = 12) -> None:
    """Pre-script *player* to decline every "you may cast?" offer.

    The "you may cast any number of spells" clause asks the controller whether
    to cast each eligible exiled spell. A DeterministicPlayer raises when its
    script is exhausted, so the exile-focused tests pre-load a generous run of
    ``False`` answers to decline the free-cast offers and keep the focus on the
    exile-until-MV-4 behaviour.
    """
    player._script.extend([False] * n)


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneProperties:
    """Static card data should match the SOS 120 spec."""

    def test_name(self) -> None:
        assert ImprovisationCapstone(owner=None).name == "Improvisation Capstone"

    def test_is_sorcery(self) -> None:
        assert isinstance(ImprovisationCapstone(owner=None), Sorcery)
        assert CardType.SORCERY in ImprovisationCapstone(owner=None).card_types

    def test_mana_cost(self) -> None:
        assert ImprovisationCapstone(owner=None).mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_has_lesson_subtype(self) -> None:
        assert "Lesson" in ImprovisationCapstone(owner=None).subtypes

    def test_has_paradigm_keyword_or_marker(self) -> None:
        """The card advertises Paradigm. Paradigm is not an evergreen
        :class:`Keyword` flag, so it is exposed either via a card-level
        marker attribute or its rules text."""
        card = ImprovisationCapstone(owner=None)
        rules = (getattr(card, "rules_text", "") or "").lower()
        has_marker = (
            getattr(card, "paradigm", False)
            or getattr(card, "has_paradigm", False)
            or "paradigm" in rules
        )
        assert has_marker

    def test_is_red(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert "R" in getattr(card, "colors", [])

    def test_not_a_permanent_type(self) -> None:
        """A sorcery is not a permanent — it must not carry permanent types."""
        types = ImprovisationCapstone(owner=None).card_types
        assert CardType.CREATURE not in types
        assert CardType.ENCHANTMENT not in types
        assert CardType.ARTIFACT not in types


# ---------------------------------------------------------------------------
# Clause 1 — Exile cards until total mana value >= 4
# ---------------------------------------------------------------------------

class TestExileUntilManaValueFour:
    """Exile top cards one at a time until cumulative MV >= 4."""

    def test_exiles_until_total_mana_value_reaches_four(self) -> None:
        """Three 2-MV cards on top: exile the first two (total 4), stop."""
        game = create_game()
        p1 = game.players[0]
        # Library bottom -> top: deep, b (2), a (2). Top is `a`.
        deep = _creature("Deep Filler", "{9}")
        a = _instant("Top A", "{1}{R}")   # MV 2
        b = _sorcery("Top B", "{1}{R}")   # MV 2
        _set_library(game, p1, [deep, b, a])

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        _decline_free_casts(p1)
        spell.on_resolve(game)

        exiled = _exiled(game, p1)
        assert a in exiled and b in exiled
        assert deep not in exiled
        # Stops once total MV is 4 — does not over-exile beyond the boundary.
        assert deep in game.get_library(p1).get_all()

    def test_single_high_value_card_stops_immediately(self) -> None:
        """A single MV-4 card on top is enough; only it is exiled."""
        game = create_game()
        p1 = game.players[0]
        big = _creature("Behemoth", "{4}")     # MV 4
        rest = _instant("Untouched", "{1}")
        _set_library(game, p1, [rest, big])    # big is on top

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        _decline_free_casts(p1)
        spell.on_resolve(game)

        exiled = _exiled(game, p1)
        assert big in exiled
        assert rest not in exiled
        # The second card was never exiled — the loop stopped after the MV-4 card.
        assert rest in game.get_library(p1).get_all()

    def test_total_mana_value_can_exceed_four(self) -> None:
        """If the boundary card pushes the total past 4, that is fine —
        the loop only stops *after* reaching >= 4."""
        game = create_game()
        p1 = game.players[0]
        a = _instant("A", "{2}")   # MV 2
        b = _creature("B", "{5}")  # MV 5 -> total 7 >= 4
        rest = _instant("Rest", "{1}")
        _set_library(game, p1, [rest, b, a])   # top is `a`

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        _decline_free_casts(p1)
        spell.on_resolve(game)

        exiled = _exiled(game, p1)
        assert a in exiled and b in exiled
        assert rest not in exiled
        assert rest in game.get_library(p1).get_all()

    def test_exact_three_one_drops_take_four_cards(self) -> None:
        """Four MV-1 cards: must exile exactly four to reach total MV 4."""
        game = create_game()
        p1 = game.players[0]
        ones = [_instant(f"One{i}", "{1}") for i in range(4)]
        spare = _instant("Spare", "{1}")
        # Library bottom->top: spare, One3, One2, One1, One0 (One0 on top)
        _set_library(game, p1, [spare] + list(reversed(ones)))

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        _decline_free_casts(p1)
        spell.on_resolve(game)

        exiled = _exiled(game, p1)
        for card in ones:
            assert card in exiled
        assert spare not in exiled
        # The fifth card stays in the library — four MV-1 cards already total 4.
        assert spare in game.get_library(p1).get_all()

    def test_small_library_below_four_is_emptied(self) -> None:
        """If the whole library totals < 4 MV, every card is exiled and the
        loop terminates without error."""
        game = create_game()
        p1 = game.players[0]
        a = _instant("A", "{1}")   # MV 1
        b = _instant("B", "{1}")   # MV 1 -> total 2, never reaches 4
        _set_library(game, p1, [b, a])

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        _decline_free_casts(p1)
        spell.on_resolve(game)

        exiled = _exiled(game, p1)
        assert a in exiled and b in exiled
        assert len(game.get_library(p1).get_all()) == 0

    def test_empty_library_is_safe_noop(self) -> None:
        """An empty library exiles nothing and does not raise."""
        game = create_game()
        p1 = game.players[0]
        _set_library(game, p1, [])

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)  # must not raise

        assert len(_exiled(game, p1)) == 0

    def test_zero_mana_value_card_does_not_stop_the_loop(self) -> None:
        """A {0} card adds 0 to the total — the loop must keep exiling until
        the cumulative MV actually reaches 4."""
        game = create_game()
        p1 = game.players[0]
        zero = _instant("Free Spell", "{0}")  # MV 0
        four = _creature("Four Drop", "{4}")  # MV 4
        rest = _instant("Rest", "{1}")
        _set_library(game, p1, [rest, four, zero])  # zero on top

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        _decline_free_casts(p1)
        spell.on_resolve(game)

        exiled = _exiled(game, p1)
        assert zero in exiled and four in exiled
        assert rest not in exiled
        assert rest in game.get_library(p1).get_all()

    def test_exiled_cards_leave_the_library(self) -> None:
        """Cards moved to exile must no longer be in the library."""
        game = create_game()
        p1 = game.players[0]
        a = _creature("A", "{4}")
        rest = _instant("Rest", "{2}")
        _set_library(game, p1, [rest, a])

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        _decline_free_casts(p1)
        spell.on_resolve(game)

        assert not game.get_library(p1).contains(a)
        assert game.get_library(p1).contains(rest)


# ---------------------------------------------------------------------------
# Clause 2 — Cast any number of the exiled spells for free
# ---------------------------------------------------------------------------

class TestFreeCastFromExile:
    """"You may cast any number of spells from among them without paying."""

    def test_declining_leaves_all_cards_in_exile(self) -> None:
        """Scripting "no" to every cast offer leaves the whole exiled pile
        in exile — nothing resolves, nothing is cast."""
        game = create_game()
        p1 = game.players[0]
        a = _instant("A", "{2}")
        b = _sorcery("B", "{2}")
        rest = _instant("Rest", "{1}")
        _set_library(game, p1, [rest, b, a])
        # Decline any/every "do you want to cast?" prompt.
        p1._script.extend([False, False, False, False])

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        exiled = _exiled(game, p1)
        assert a in exiled and b in exiled
        # No spell was put onto the stack to be cast.
        assert game.stack.is_empty()

    def test_lands_among_exiled_are_never_cast(self) -> None:
        """Lands are not spells — even if exiled, they cannot be cast and
        remain in exile regardless of player choices."""
        game = create_game()
        p1 = game.players[0]
        land = _land("Mountain")
        big = _creature("Big", "{4}")   # MV 4, paired with the land
        _set_library(game, p1, [big, land])  # land on top, then big
        # Accept everything the card might offer; the land must still not be cast.
        p1._script.extend([True, True, True, True, True, True])

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        # The land was exiled but never left exile (cannot be cast).
        assert game.get_exile(p1).contains(land)
        assert not game.get_battlefield(p1).contains(land)

    def test_casting_a_chosen_spell_moves_it_out_of_exile(self) -> None:
        """Accepting the offer for an exiled instant casts it for free: the
        card is first exiled by the "exile until MV 4" clause, then cast — so
        after resolution it is no longer in exile, but it HAS left the library
        (proving it was the exiled card that got cast, not an untouched one)."""
        game = create_game()
        p1 = game.players[0]
        bolt = _instant("Free Bolt", "{4}")  # MV 4 alone -> sole exiled card
        rest = _instant("Rest", "{1}")
        _set_library(game, p1, [rest, bolt])  # bolt on top
        # Say yes to cast Free Bolt, plus a couple of spare answers in case the
        # implementation asks a per-card selection question.
        p1._script.extend([True, bolt, True, bolt])

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        # The card was pulled off the library (exiled), then cast — so it is
        # neither in the library nor still sitting in exile.
        assert not game.get_library(p1).contains(bolt)
        assert not game.get_exile(p1).contains(bolt)

    def test_free_cast_does_not_require_mana(self) -> None:
        """Casting from among the exiled pile costs no mana — the controller
        with an empty pool can still cast the exiled spell. The card must
        first have been exiled (off the library) and then leave exile."""
        game = create_game()
        p1 = game.players[0]
        spell_card = _sorcery("Free Sorc", "{4}")
        rest = _instant("Rest", "{1}")
        _set_library(game, p1, [rest, spell_card])  # spell_card on top
        set_board_state(game, 0, mana={})  # empty pool
        p1._script.extend([True, spell_card, True, spell_card])

        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        capstone.on_resolve(game)

        # Free Sorc was exiled (left the library) and cast (left exile) despite
        # no available mana.
        assert not game.get_library(p1).contains(spell_card)
        assert not game.get_exile(p1).contains(spell_card)


# ---------------------------------------------------------------------------
# Clause 3 — Paradigm: exile this spell + delayed copy mechanism
# ---------------------------------------------------------------------------

class TestParadigmSelfExile:
    """"Then exile this spell." — the resolved Capstone goes to exile, not
    the graveyard."""

    def test_resolution_via_full_pipeline_exiles_the_spell(self) -> None:
        """Casting through the engine pipeline routes the resolved Capstone to
        exile rather than the graveyard (the Paradigm self-exile rider)."""
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        # Give it a small library so the exile-until clause is a quick no-op-ish.
        filler = _instant("Filler", "{4}")
        _set_library(game, p1, [filler])
        set_board_state(
            game, 0,
            hand=[capstone],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )
        # Decline the free-cast offers so the test stays focused on self-exile.
        p1._script.extend([False, False, False])

        from test_utils import cast_spell
        cast_spell(game, 0, "Improvisation Capstone")

        # Paradigm: "Then exile this spell."
        assert game.get_exile(p1).contains(capstone)
        assert not game.get_graveyard(p1).contains(capstone)


class TestParadigmDelayedCopy:
    """After the first Capstone resolves, a delayed effect lets the
    controller cast a free copy from exile at the beginning of each of their
    first (precombat) main phases."""

    def test_first_resolution_schedules_a_main_phase_effect(self) -> None:
        """Resolving the spell for the first time registers a deferred
        main-phase effect for its controller (the Paradigm delayed trigger)."""
        game = create_game()
        p1 = game.players[0]
        filler = _instant("Filler", "{4}")
        _set_library(game, p1, [filler])

        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        before = len(game.main_phase_deferred_effects)
        # Decline the free-cast prompts.
        p1._script.extend([False, False, False])
        capstone.on_resolve(game)

        after = len(game.main_phase_deferred_effects)
        assert after > before

    def test_scheduled_copy_effect_targets_the_precombat_main_phase(self) -> None:
        """The Paradigm delayed trigger is for the controller's *precombat*
        main phases, so the scheduled deferred effect must be registered for
        the controller with the precombat flag set."""
        game = create_game()
        p1 = game.players[0]
        filler = _instant("Filler", "{4}")
        _set_library(game, p1, [filler])

        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        p1._script.extend([False, False, False])
        capstone.on_resolve(game)

        entries = [
            e for e in game.main_phase_deferred_effects
            if e.get("controller") is p1
        ]
        assert entries, "first resolution must schedule a deferred effect for the controller"
        assert all(e.get("precombat", True) for e in entries)

    def test_precombat_main_phase_consults_player_for_a_copy(self) -> None:
        """When the controller's next precombat main phase begins after the
        first resolution, firing the main-phase event runs the scheduled
        Paradigm effect, which consults the controller ("you may cast a
        copy"). Declining must cast nothing onto the stack.

        This focuses on the delayed copy mechanism; the self-exile of the
        Capstone via resolution is covered separately by
        :class:`TestParadigmSelfExile`."""
        game = create_game()
        p1 = game.players[0]
        filler = _instant("Filler", "{4}")
        _set_library(game, p1, [filler])

        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        # First resolution: decline the immediate free-cast offers.
        _decline_free_casts(p1)
        capstone.on_resolve(game)
        # Ensure the Capstone is in exile for the copy mechanism, regardless of
        # whether the bare on_resolve path or the casting pipeline performs the
        # self-exile.
        if not game.get_exile(p1).contains(capstone):
            game.get_exile(p1).add(capstone)

        # At the next precombat main phase, the scheduled effect must consult
        # the controller. Provide a decline answer.
        before = p1.remaining_choices
        p1._script.append(False)
        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, controller=p1, precombat=True),
        )

        # The scheduled effect ran and consumed the player's "no" answer
        # (a one-shot deferred entry that never fired would leave it unused).
        assert p1.remaining_choices < before + 1
        # Declining the copy casts nothing onto the stack.
        assert game.stack.is_empty()

    def test_paradigm_copy_offer_recurs_each_precombat_main_phase(self) -> None:
        """Paradigm fires "at the beginning of EACH of your first main phases",
        so the deferred offer must persist after the first main phase — it is
        not a single-use one-shot effect. After firing one precombat main
        phase (and declining), a scheduled effect for the controller must
        still be present for the next one."""
        game = create_game()
        p1 = game.players[0]
        filler = _instant("Filler", "{4}")
        _set_library(game, p1, [filler])

        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        p1._script.extend([False, False, False])
        capstone.on_resolve(game)

        # First precombat main phase — decline the copy offer.
        p1._script.append(False)
        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, controller=p1, precombat=True),
        )

        # The recurring Paradigm offer must still be scheduled for the
        # controller's next precombat main phase (not consumed one-shot).
        remaining = [
            e for e in game.main_phase_deferred_effects
            if e.get("controller") is p1
        ]
        assert remaining, (
            "Paradigm is a recurring delayed trigger — the offer must persist "
            "for subsequent precombat main phases, not be removed after one"
        )
