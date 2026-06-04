"""Tests for SOS 120 — Improvisation Capstone.

Oracle text (from card_spec.json):

    Exile cards from the top of your library until you exile cards with total
    mana value 4 or greater. You may cast any number of spells from among them
    without paying their mana costs.
    Paradigm (Then exile this spell. After you first resolve a spell with this
    name, you may cast a copy of it from exile without paying its mana cost at
    the beginning of each of your first main phases.)

Static data:

    Improvisation Capstone
    {5}{R}{R}
    Sorcery — Lesson
    red, mythic, keyword "Paradigm".

Behaviour contract derived from the spec
----------------------------------------

Main effect (on_resolve):

* Exile cards from the **top** of the controller's library one at a time,
  summing their mana value, and stop as soon as the running total of mana
  value reaches 4 or greater (the card that crosses the threshold is exiled
  too).  All exiled cards go to the controller's exile zone.
* A single card whose mana value is already >= 4 stops the process after that
  one card.
* Mana-value-0 cards (e.g. lands) keep the process going — they add nothing to
  the running total — until a card with nonzero mana value pushes the total to
  4 or greater.
* If the library runs out before reaching total mana value 4, every remaining
  card is exiled and the process stops (no crash / infinite loop).
* From among the cards exiled this way the controller "may cast any number of
  spells ... without paying their mana costs".  A spell cast this way is cast
  from the exile zone for free (it leaves exile and goes on the stack).  Lands
  among the exiled cards are not spells and cannot be cast this way.

Paradigm (keyword, CR 702.192):

* The card has the "Paradigm" keyword designation.
* "Then exile this spell." — after Improvisation Capstone finishes resolving
  it is exiled rather than put into the graveyard.
* "After you first resolve a spell with this name, ... cast a copy of it from
  exile ... at the beginning of each of your first main phases." — the
  implementation exposes a way to create / cast a free copy of the spell from
  exile.  The exact engine surface for this brand-new mechanic is probed
  tolerantly (a copy factory and/or a cast helper).

These tests are written for the TDD red phase: they FAIL against the empty
stub and PASS once the card is implemented correctly.
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Land, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.paradigm import (
    has_paradigm_resolved,
    register_paradigm,
)
from engine.protection import get_colors
from engine.types import CardType, Color, ManaCost, Zone
from test_utils import create_game, set_board_state

CAPSTONE_NAME = "Improvisation Capstone"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sorcery(name: str, cost: str) -> Sorcery:
    """A plain sorcery with the given mana cost (no effect)."""
    return Sorcery(name=name, mana_cost=ManaCost.parse(cost))


def _instant(name: str, cost: str) -> Instant:
    """A plain instant with the given mana cost (no effect)."""
    return Instant(name=name, mana_cost=ManaCost.parse(cost))


def _creature(name: str, cost: str, *, power: int = 2, toughness: int = 2) -> Creature:
    """A plain vanilla creature with the given mana cost."""
    return Creature(
        name=name,
        mana_cost=ManaCost.parse(cost),
        base_power=power,
        base_toughness=toughness,
    )


def _land(name: str = "Wastes") -> Land:
    """A basic land (mana value 0, not a spell)."""
    return Land(name=name)


def _set_library(game: Any, player_index: int, cards: list[Any]) -> None:
    """Replace *player_index*'s library with *cards*.

    ``cards[-1]`` becomes the *top* of the library (the internal list stores
    the top at the end), so the cards are exiled in reverse-list order:
    ``cards[-1]`` first.  Ownership/control is assigned to the player.
    """
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for obj in library.get_all():
        library.remove(obj)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


def _resolve_capstone(game: Any, card: ImprovisationCapstone) -> None:
    """Run the card's main resolution and any spells it puts on the stack.

    ``on_resolve`` does the exile-and-(optionally)-cast work; if it free-casts
    spells they land on the stack, so we drain the stack afterwards to settle
    a stable end state.
    """
    card.on_resolve(game)
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


def _capstone_on_battlefield_owner(game: Any, player_index: int) -> ImprovisationCapstone:
    """An Improvisation Capstone owned/controlled by *player_index*."""
    p = game.players[player_index]
    card = ImprovisationCapstone(owner=p, controller=p)
    return card


def _fire_main_phase_begin(
    game: Any, player: Any, *, precombat: bool = True, drain: bool = True
) -> None:
    """Fire ``BeginningOfMainPhaseTriggeredEvent`` for *player*.

    Drives the engine exactly as ``engine/turn.py`` does at the start of a main
    phase: the event is fired via :meth:`TriggerManager.fire_event`, which pushes
    any matching trigger's effect onto the stack as a :class:`StackObject`.  When
    *drain* is ``True`` the stack is then resolved (LIFO) so the trigger's body
    (``offer_paradigm_copy``) actually runs — mirroring the real ``priority_loop``
    resolution that follows the fired event.

    APNAP ordering in ``fire_event`` keys off ``game.active_player``; the active
    player is set to *player* so a trigger they control is pushed normally.
    """
    game.active_player_index = game.players.index(player)
    game.trigger_manager.fire_event(
        game,
        BeginningOfMainPhaseTriggeredEvent(player=player, precombat=precombat),
    )
    if not drain:
        return
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


def _capstone_copies_in_exile(player: Any) -> list[ImprovisationCapstone]:
    """All Improvisation Capstone copies currently in *player*'s exile zone."""
    return [
        c
        for c in player.zones[Zone.EXILE].get_all()
        if isinstance(c, ImprovisationCapstone)
    ]


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneProperties:
    """Static card data should match the SOS 120 spec."""

    def test_name(self) -> None:
        assert ImprovisationCapstone(owner=None).name == "Improvisation Capstone"

    def test_mana_cost(self) -> None:
        assert ImprovisationCapstone(owner=None).mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_is_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery)
        assert CardType.SORCERY in card.card_types

    def test_not_a_creature(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert CardType.CREATURE not in card.card_types

    def test_is_red(self) -> None:
        assert get_colors(ImprovisationCapstone(owner=None)) == {Color.RED}

    def test_is_a_lesson(self) -> None:
        assert "Lesson" in ImprovisationCapstone(owner=None).subtypes

    def test_mana_value_is_seven(self) -> None:
        assert ImprovisationCapstone(owner=None).mana_cost.cmc == 7

    def test_has_paradigm_keyword(self) -> None:
        """The card carries the 'Paradigm' designation.

        Paradigm is not an evergreen ``Keyword`` enum member, so the
        implementation records it as a printed-keyword label.  Probe the
        common spellings tolerantly.
        """
        card = ImprovisationCapstone(owner=None)
        found = False
        for attr in ("printed_keywords", "keyword_labels", "ability_words"):
            val = getattr(card, attr, None)
            if val and any("Paradigm" in str(k) for k in val):
                found = True
        rules = getattr(card, "rules_text", "") or ""
        if "Paradigm" in rules:
            found = True
        assert found, "no 'Paradigm' designation found on the card"


# ---------------------------------------------------------------------------
# Main effect — exile from library until total mana value >= 4
# ---------------------------------------------------------------------------


class TestExileThreshold:
    """Exile cards from the top of your library until total mana value >= 4."""

    def test_exiles_until_total_mana_value_reaches_four(self) -> None:
        """Three 2-MV cards: the first two (total 4) cross the threshold.

        Top-of-library cards are exiled first; once the running total reaches
        4 the process stops, so the third card stays in the library.
        """
        game = create_game()
        p1 = game.players[0]
        card = _capstone_on_battlefield_owner(game, 0)
        a = _sorcery("A", "{2}")  # mv 2
        b = _sorcery("B", "{2}")  # mv 2
        c = _sorcery("C", "{2}")  # mv 2
        # top -> a, then b, then c
        _set_library(game, 0, [c, b, a])

        card.on_resolve(game)

        exile = p1.zones[Zone.EXILE]
        assert exile.contains(a)
        assert exile.contains(b)
        # The third card is untouched in the library — threshold already met.
        assert not exile.contains(c)
        assert p1.zones[Zone.LIBRARY].contains(c)

    def test_single_high_mana_value_card_stops_immediately(self) -> None:
        """A single card whose mana value is already >= 4 ends the process."""
        game = create_game()
        p1 = game.players[0]
        card = _capstone_on_battlefield_owner(game, 0)
        big = _sorcery("Big Spell", "{4}")  # mv 4
        rest = _sorcery("Untouched", "{1}")
        _set_library(game, 0, [rest, big])  # top -> big

        card.on_resolve(game)

        exile = p1.zones[Zone.EXILE]
        assert exile.contains(big)
        # Only the one card was exiled; the second never gets reached.
        assert not exile.contains(rest)
        assert p1.zones[Zone.LIBRARY].contains(rest)

    def test_threshold_is_inclusive_of_exactly_four(self) -> None:
        """Reaching exactly mana value 4 stops the process (>= 4, not > 4)."""
        game = create_game()
        p1 = game.players[0]
        card = _capstone_on_battlefield_owner(game, 0)
        four = _sorcery("Exactly Four", "{4}")
        extra = _sorcery("Extra", "{1}")
        _set_library(game, 0, [extra, four])  # top -> four

        card.on_resolve(game)

        exile = p1.zones[Zone.EXILE]
        assert exile.contains(four)
        assert not exile.contains(extra)

    def test_zero_mana_value_cards_do_not_stop_the_process(self) -> None:
        """Lands (mana value 0) keep the process going until a nonzero card
        pushes the running total to 4 or greater."""
        game = create_game()
        p1 = game.players[0]
        card = _capstone_on_battlefield_owner(game, 0)
        land1 = _land("Wastes 1")  # mv 0
        land2 = _land("Wastes 2")  # mv 0
        payoff = _sorcery("Payoff", "{4}")  # mv 4 -> crosses threshold
        beyond = _sorcery("Beyond", "{1}")
        # top -> land1, land2, payoff, beyond
        _set_library(game, 0, [beyond, payoff, land2, land1])

        card.on_resolve(game)

        exile = p1.zones[Zone.EXILE]
        assert exile.contains(land1)
        assert exile.contains(land2)
        assert exile.contains(payoff)
        # The card after the threshold-crosser is left in the library.
        assert not exile.contains(beyond)
        assert p1.zones[Zone.LIBRARY].contains(beyond)

    def test_exiled_cards_leave_the_library(self) -> None:
        """Exiled cards are removed from the library (no duplication)."""
        game = create_game()
        p1 = game.players[0]
        card = _capstone_on_battlefield_owner(game, 0)
        a = _sorcery("A", "{3}")
        b = _sorcery("B", "{3}")  # total 6 -> stops after b
        _set_library(game, 0, [b, a])  # top -> a

        card.on_resolve(game)

        library = p1.zones[Zone.LIBRARY]
        assert not library.contains(a)
        assert not library.contains(b)

    def test_empty_library_exiles_nothing_and_does_not_crash(self) -> None:
        """With an empty library, the effect exiles nothing and is a no-op."""
        game = create_game()
        p1 = game.players[0]
        card = _capstone_on_battlefield_owner(game, 0)
        _set_library(game, 0, [])

        card.on_resolve(game)  # must not raise / infinite-loop

        assert len(p1.zones[Zone.EXILE].get_all()) == 0

    def test_library_smaller_than_threshold_exiles_all_remaining(self) -> None:
        """If the library runs dry before total mana value 4, every card is
        exiled and the process stops (no infinite loop)."""
        game = create_game()
        p1 = game.players[0]
        card = _capstone_on_battlefield_owner(game, 0)
        a = _sorcery("A", "{1}")  # mv 1
        b = _sorcery("B", "{1}")  # mv 1 -> total 2, library exhausted
        _set_library(game, 0, [b, a])

        card.on_resolve(game)

        exile = p1.zones[Zone.EXILE]
        assert exile.contains(a)
        assert exile.contains(b)
        assert len(p1.zones[Zone.LIBRARY].get_all()) == 0

    def test_only_controllers_library_is_used(self) -> None:
        """Cards come from *your* (the controller's) library, not an opponent's."""
        game = create_game()
        p1, p2 = game.players
        card = _capstone_on_battlefield_owner(game, 0)
        mine = _sorcery("Mine", "{4}")
        _set_library(game, 0, [mine])
        opp = _sorcery("Opp", "{4}")
        _set_library(game, 1, [opp])

        card.on_resolve(game)

        # The controller's card is exiled; the opponent's library is untouched.
        assert p1.zones[Zone.EXILE].contains(mine)
        assert p2.zones[Zone.LIBRARY].contains(opp)
        assert not p2.zones[Zone.EXILE].contains(opp)


# ---------------------------------------------------------------------------
# Main effect — cast any number of spells from among them for free
# ---------------------------------------------------------------------------


class TestCastFromAmongExiled:
    """You may cast any number of spells from among the exiled cards for free."""

    def test_chosen_spell_is_cast_for_free(self) -> None:
        """A spell chosen from the exiled cards is put on the stack from exile
        without paying mana (the controller's empty pool is irrelevant)."""
        spell = _sorcery("Free Spell", "{4}")
        # Script: yes (cast a spell), choose the spell, then no (stop).
        game = create_game(scripts=([True, spell, False], []))
        p1 = game.players[0]
        card = _capstone_on_battlefield_owner(game, 0)
        _set_library(game, 0, [spell])
        set_board_state(game, 0, mana={})  # no mana available

        card.on_resolve(game)

        # The chosen spell left exile and is now on the stack (cast for free).
        assert not p1.zones[Zone.EXILE].contains(spell)
        assert not game.stack.is_empty()
        sources = [obj.source for obj in game.stack.objects()]
        assert spell in sources

    def test_declining_leaves_spells_in_exile(self) -> None:
        """Casting is optional ("may"); declining leaves the cards in exile."""
        spell = _sorcery("Stays Exiled", "{4}")
        game = create_game(scripts=([False], []))  # decline to cast anything
        p1 = game.players[0]
        card = _capstone_on_battlefield_owner(game, 0)
        _set_library(game, 0, [spell])

        card.on_resolve(game)

        # Nothing was cast; the spell remains in exile.
        assert p1.zones[Zone.EXILE].contains(spell)
        assert game.stack.is_empty()

    def test_can_cast_multiple_spells(self) -> None:
        """"any number of spells" — more than one exiled spell may be cast."""
        s1 = _sorcery("First", "{2}")
        s2 = _sorcery("Second", "{2}")  # total mv 4 -> both exiled
        # yes, cast s1; yes, cast s2; no (stop).
        game = create_game(scripts=([True, s1, True, s2, False], []))
        p1 = game.players[0]
        card = _capstone_on_battlefield_owner(game, 0)
        _set_library(game, 0, [s2, s1])  # top -> s1

        card.on_resolve(game)

        assert not p1.zones[Zone.EXILE].contains(s1)
        assert not p1.zones[Zone.EXILE].contains(s2)
        sources = [obj.source for obj in game.stack.objects()]
        assert s1 in sources
        assert s2 in sources

    def test_lands_among_exiled_cards_are_not_castable(self) -> None:
        """Lands are not spells; they cannot be cast and stay in exile."""
        land = _land("Exiled Land")  # mv 0, not a spell
        payoff = _sorcery("Payoff", "{4}")
        # Decline casting any spell; verify the land never leaves exile.
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        card = _capstone_on_battlefield_owner(game, 0)
        _set_library(game, 0, [payoff, land])  # top -> land

        card.on_resolve(game)

        # Both cards were exiled; the land remains in exile regardless.
        assert p1.zones[Zone.EXILE].contains(land)
        assert p1.zones[Zone.EXILE].contains(payoff)

    def test_resolved_free_cast_spell_does_not_require_payment(self) -> None:
        """The free-cast spell resolves even with the controller holding no
        mana — confirming it was genuinely cast without paying."""
        spell = _instant("Cheap Instant", "{6}{R}")  # expensive; no mana available
        game = create_game(scripts=([True, spell, False], []))
        p1 = game.players[0]
        card = _capstone_on_battlefield_owner(game, 0)
        _set_library(game, 0, [spell])
        set_board_state(game, 0, mana={})

        _resolve_capstone(game, card)

        # It must have actually been exiled and then cast — not left in the
        # library (which would mean the effect never ran).  An empty pool means
        # the only way it could have been cast is for free.
        assert not p1.zones[Zone.LIBRARY].contains(spell)
        # Having been cast and resolved, the non-permanent spell is no longer
        # on the stack nor still in exile — it went to the graveyard.
        assert game.stack.is_empty()
        assert not p1.zones[Zone.EXILE].contains(spell)
        assert p1.zones[Zone.GRAVEYARD].contains(spell)


# ---------------------------------------------------------------------------
# Paradigm — "Then exile this spell."
# ---------------------------------------------------------------------------


class TestParadigmExileThisSpell:
    """Paradigm: after resolving, the spell is exiled rather than going to the
    graveyard."""

    def test_capstone_is_exiled_after_resolving_via_cast_pipeline(self) -> None:
        """When cast and resolved through the real pipeline, Improvisation
        Capstone ends up in exile, not the graveyard ("Then exile this
        spell.")."""
        from engine.casting import cast_spell

        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        # A target/free-cast-free run: empty library so the main effect is a
        # no-op, isolating the "exile this spell" clause.
        _set_library(game, 0, [])
        set_board_state(game, 0, hand=[capstone], mana={})
        # Pay nothing — set the pool to exactly the cost so cast_spell succeeds.
        from engine.types import ManaType

        set_board_state(
            game,
            0,
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )
        # Sorcery-speed timing.
        from engine.types import Phase

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        cast_spell(game, p1, capstone)
        # Resolve the spell.
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert p1.zones[Zone.EXILE].contains(capstone)
        assert not p1.zones[Zone.GRAVEYARD].contains(capstone)


# ---------------------------------------------------------------------------
# Paradigm — copy-cast-from-exile mechanism
# ---------------------------------------------------------------------------


class TestParadigmCopyMechanism:
    """Paradigm: after first resolving, a free copy can be cast from exile at
    the beginning of each of your first main phases.

    The exact engine API for this brand-new mechanic is unknown at red-phase
    time, so these probe the observable surface tolerantly: the card should
    expose a way to materialise a copy of itself (a factory and/or a copy that
    lands in exile and is castable for free).
    """

    def test_card_exposes_a_paradigm_copy_factory(self) -> None:
        """The card advertises ``make_paradigm_copy`` for the Paradigm delayed
        ability — a callable returning a fresh same-named copy."""
        card = ImprovisationCapstone(owner=None)
        factory = card.make_paradigm_copy
        assert callable(factory)
        copy = factory()
        assert isinstance(copy, ImprovisationCapstone)
        assert copy is not card
        assert copy.name == card.name

    def test_paradigm_copy_can_be_cast_for_free_from_exile(self) -> None:
        """A Paradigm copy placed in exile can be cast for free (it leaves
        exile and goes on the stack without paying mana)."""
        from engine.casting import cast_spell_free

        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        copy = card.make_paradigm_copy()
        copy.owner = p1
        copy.controller = p1
        p1.zones[Zone.EXILE].add(copy)
        set_board_state(game, 0, mana={})  # no mana — free cast only

        cast_spell_free(game, p1, copy, Zone.EXILE)

        assert not p1.zones[Zone.EXILE].contains(copy)
        assert not game.stack.is_empty()
        assert game.stack.peek().source is copy


# ---------------------------------------------------------------------------
# Paradigm — recurring per-main-phase copy delivery + first-resolution gate
# ---------------------------------------------------------------------------


class TestParadigmFirstResolutionGate:
    """Paradigm: "After you *first* resolve a spell with this name, ..."

    The recurring per-main-phase copy is gated on the first resolution of a
    spell with this name.  Before that first resolution, the controller's
    precombat main-phase event must produce no copy and the gate must read as
    closed.
    """

    def test_gate_closed_before_capstone_resolves(self) -> None:
        """Before any Capstone resolves, the gate reads as closed for the
        controller."""
        game = create_game()
        p1 = game.players[0]
        assert has_paradigm_resolved(game, p1, CAPSTONE_NAME) is False

    def test_no_copy_before_first_resolution(self) -> None:
        """Firing the controller's precombat main-phase event BEFORE the
        Capstone has ever resolved creates no copy in exile (the gate is
        closed, and no recurring trigger has been wired)."""
        game = create_game()
        p1 = game.players[0]

        _fire_main_phase_begin(game, p1, precombat=True)

        assert _capstone_copies_in_exile(p1) == []
        assert game.stack.is_empty()
        assert has_paradigm_resolved(game, p1, CAPSTONE_NAME) is False

    def test_resolving_capstone_opens_the_gate(self) -> None:
        """Resolving an Improvisation Capstone marks the first resolution so the
        gate reads as open for the controller afterwards."""
        game = create_game()
        p1 = game.players[0]
        card = _capstone_on_battlefield_owner(game, 0)
        _set_library(game, 0, [])

        assert has_paradigm_resolved(game, p1, CAPSTONE_NAME) is False
        card.on_resolve(game)

        assert has_paradigm_resolved(game, p1, CAPSTONE_NAME) is True


class TestParadigmRecurringCopyDelivery:
    """Paradigm: "... at the beginning of *each* of your first main phases."

    After the first resolution wires the recurring trigger, every one of the
    controller's precombat main phases produces a fresh free copy in exile.
    These tests script the copy offer to DECLINE (``choose_yes_no`` -> False) so
    the copy stays in exile to be observed.
    """

    def _wired_game(self, *, decline_count: int = 4) -> tuple[Any, Any]:
        """A game whose controller has resolved a Capstone (gate open, trigger
        wired) and whose script declines every paradigm copy offer.

        ``decline_count`` provides enough scripted ``False`` answers for the
        number of times the test will fire the main-phase event.
        """
        game = create_game(scripts=([False] * decline_count, []))
        p1 = game.players[0]
        card = _capstone_on_battlefield_owner(game, 0)
        _set_library(game, 0, [])
        card.on_resolve(game)
        return game, p1

    def test_one_copy_appears_on_first_main_phase_after_resolution(self) -> None:
        """After resolution, the controller's first precombat main phase creates
        exactly one new Capstone copy in exile (offer declined)."""
        game, p1 = self._wired_game()
        # The resolved Capstone itself is redirected to exile only through the
        # full cast pipeline; here on_resolve was called directly, so exile
        # holds no Capstone copy yet.
        assert _capstone_copies_in_exile(p1) == []

        _fire_main_phase_begin(game, p1, precombat=True)

        copies = _capstone_copies_in_exile(p1)
        assert len(copies) == 1
        # The delivered copy is a genuine Improvisation Capstone copy, distinct
        # from the original spell object.
        assert copies[0] is not None
        assert copies[0].name == CAPSTONE_NAME

    def test_recurs_a_second_copy_on_the_next_main_phase(self) -> None:
        """Firing the precombat main-phase event AGAIN yields a SECOND copy —
        proving the ability recurs (contrast the sos_57 one-shot delayed
        trigger, which fires exactly once)."""
        game, p1 = self._wired_game()

        _fire_main_phase_begin(game, p1, precombat=True)
        assert len(_capstone_copies_in_exile(p1)) == 1

        _fire_main_phase_begin(game, p1, precombat=True)
        assert len(_capstone_copies_in_exile(p1)) == 2

    def test_recurring_trigger_is_not_consumed(self) -> None:
        """The recurring trigger remains registered after it fires (it is NOT a
        one-shot delayed trigger)."""
        game, p1 = self._wired_game()

        capstone_triggers_before = [
            t
            for t in game.trigger_manager.get_triggers()
            if t.controller is p1
        ]
        assert len(capstone_triggers_before) == 1

        _fire_main_phase_begin(game, p1, precombat=True)

        capstone_triggers_after = [
            t
            for t in game.trigger_manager.get_triggers()
            if t.controller is p1
        ]
        # Still exactly one — the recurring trigger survives firing.
        assert len(capstone_triggers_after) == 1


class TestParadigmCopyGating:
    """The recurring copy is gated by player and by phase."""

    def _wired_game(self, *, decline_count: int = 4) -> tuple[Any, Any, Any]:
        game = create_game(scripts=([False] * decline_count, [False] * decline_count))
        p1, p2 = game.players
        card = _capstone_on_battlefield_owner(game, 0)
        _set_library(game, 0, [])
        card.on_resolve(game)
        return game, p1, p2

    def test_postcombat_main_phase_creates_no_copy(self) -> None:
        """"your *first* main phases" — the postcombat main (``precombat=False``)
        does not deliver a copy."""
        game, p1, _p2 = self._wired_game()

        _fire_main_phase_begin(game, p1, precombat=False)

        assert _capstone_copies_in_exile(p1) == []

    def test_opponents_main_phase_creates_no_copy_for_controller(self) -> None:
        """"*your* first main phases" — the opponent's precombat main phase does
        not deliver a copy to either player."""
        game, p1, p2 = self._wired_game()

        _fire_main_phase_begin(game, p2, precombat=True)

        assert _capstone_copies_in_exile(p1) == []
        assert _capstone_copies_in_exile(p2) == []

    def test_opponent_phase_then_controller_phase_delivers_once(self) -> None:
        """The opponent's main phase is inert; the controller's then delivers
        exactly one copy."""
        game, p1, p2 = self._wired_game()

        _fire_main_phase_begin(game, p2, precombat=True)
        assert _capstone_copies_in_exile(p1) == []

        _fire_main_phase_begin(game, p1, precombat=True)
        assert len(_capstone_copies_in_exile(p1)) == 1


class TestParadigmCopyAcceptCast:
    """The per-main-phase copy may be cast for free from exile (accept path)."""

    def test_accepting_casts_the_copy_for_free_from_exile(self) -> None:
        """When the controller accepts (``choose_yes_no`` -> True), the copy is
        cast for free: it leaves exile and lands on the stack.

        The stack is inspected BEFORE draining so the freshly-cast copy is
        observed on the stack (resolving it would run the copy's own effect and
        move it onward)."""
        # Accept the paradigm copy offer.
        game = create_game(scripts=([True], []))
        p1 = game.players[0]
        card = _capstone_on_battlefield_owner(game, 0)
        _set_library(game, 0, [])
        card.on_resolve(game)
        set_board_state(game, 0, mana={})  # no mana — free cast only

        # Fire the event but do not drain: the trigger body runs when its
        # StackObject resolves, so resolve only the trigger and then inspect.
        _fire_main_phase_begin(game, p1, precombat=True, drain=False)
        # Resolve the trigger itself (its effect calls offer_paradigm_copy,
        # which creates the copy and free-casts it onto the stack).
        assert not game.stack.is_empty()
        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        # The accepted copy is now on the stack (cast for free) and no longer in
        # exile.
        assert not game.stack.is_empty()
        cast_copy = game.stack.peek().source
        assert isinstance(cast_copy, ImprovisationCapstone)
        assert not p1.zones[Zone.EXILE].contains(cast_copy)

    def test_declining_leaves_the_copy_in_exile(self) -> None:
        """When the controller declines, the copy stays in exile (nothing is put
        on the stack by the offer)."""
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        card = _capstone_on_battlefield_owner(game, 0)
        _set_library(game, 0, [])
        card.on_resolve(game)

        _fire_main_phase_begin(game, p1, precombat=True)

        copies = _capstone_copies_in_exile(p1)
        assert len(copies) == 1
        # Declined — the copy remains in exile, nothing on the stack.
        assert p1.zones[Zone.EXILE].contains(copies[0])
        assert game.stack.is_empty()


class TestParadigmRegisterDirectly:
    """``register_paradigm`` is the public hook the card wires; driving it
    directly mirrors the recurring delivery without the full on_resolve path."""

    def test_register_paradigm_opens_gate_and_delivers_recurring_copies(self) -> None:
        """Calling ``register_paradigm`` opens the gate and installs the
        recurring trigger; firing the controller's precombat main phase then
        delivers copies repeatedly."""
        game = create_game(scripts=([False, False], []))
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        register_paradigm(
            game,
            source=card,
            controller=p1,
            factory=card.make_paradigm_copy,
            name=CAPSTONE_NAME,
        )

        assert has_paradigm_resolved(game, p1, CAPSTONE_NAME) is True

        _fire_main_phase_begin(game, p1, precombat=True)
        assert len(_capstone_copies_in_exile(p1)) == 1

        _fire_main_phase_begin(game, p1, precombat=True)
        assert len(_capstone_copies_in_exile(p1)) == 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
