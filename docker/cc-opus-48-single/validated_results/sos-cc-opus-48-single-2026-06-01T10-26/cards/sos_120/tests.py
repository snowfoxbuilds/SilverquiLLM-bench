"""Tests for SOS 120 — Improvisation Capstone.

Improvisation Capstone ({5}{R}{R} Sorcery — Lesson) has two pieces of
behaviour:

1. **Main effect** — "Exile cards from the top of your library until you
   exile cards with total mana value 4 or greater. You may cast any number
   of spells from among them without paying their mana costs."

2. **Paradigm** — "Then exile this spell. After you first resolve a spell
   with this name, you may cast a copy of it from exile without paying its
   mana cost at the beginning of each of your first main phases."

These are TDD red-phase tests: the stub at ``card_impl.py`` is empty, so
everything here is expected to fail until the card is implemented.

Contract assumptions (mirroring established SOS conventions in
``cards/sos/sos_1`` and ``cards/sos/sos_57``):

* The card exposes ``on_resolve(game)`` which reads its ``controller``.
* The main effect exiles cards off the top of the controller's library
  (``game.get_library`` — top is the last element) one at a time until the
  *total mana value* of the exiled cards reaches 4 or more.
* For each spell among the exiled cards, the controller is asked
  ``choose_yes_no`` whether to free-cast it (the "you may cast any number"
  clause).  Casting uses the engine free-cast pipeline (no mana paid).
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import CardImpl, Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _instant(name: str, cost: str) -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse(cost))


def _sorcery(name: str, cost: str) -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse(cost))


def _land(name: str = "Mountain") -> CardImpl:
    """A zero-mana-value 'card' used to test mana-value accumulation."""
    return CardImpl(name=name, mana_cost=ManaCost.parse("{0}"), card_types={CardType.LAND})


def _set_library_top_down(game: Any, player_index: int, top_down: list[Any]) -> None:
    """Place *top_down* into the player's library so that ``top_down[0]`` is the
    top card.  The library's internal order is bottom->top (top == last element),
    so we add cards in reversed order.
    """
    player = game.players[player_index]
    library = game.get_library(player)
    for obj in library.get_all():
        library.remove(obj)
    for obj in reversed(top_down):
        obj.owner = player
        obj.controller = player
        library.add(obj)  # default position="top" appends to end


def _capstone_on_battlefield_resolving(game: Any, controller: Any) -> ImprovisationCapstone:
    """Return a Capstone whose controller is set, ready to call on_resolve."""
    card = ImprovisationCapstone(owner=controller, controller=controller)
    return card


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneProperties:
    def test_name(self) -> None:
        assert ImprovisationCapstone(owner=None).name == "Improvisation Capstone"

    def test_is_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_mana_value_is_seven(self) -> None:
        assert ImprovisationCapstone(owner=None).mana_cost.cmc == 7

    def test_is_lesson(self) -> None:
        assert "Lesson" in ImprovisationCapstone(owner=None).subtypes

    def test_is_red(self) -> None:
        from engine.types import Color

        assert Color.RED in ImprovisationCapstone(owner=None).colors

    def test_not_a_creature(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert CardType.CREATURE not in card.card_types

    def test_rules_text_mentions_paradigm(self) -> None:
        text = ImprovisationCapstone(owner=None).rules_text.lower()
        assert "paradigm" in text


# ---------------------------------------------------------------------------
# Main effect: exile from top until total mana value >= 4
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneExileUntilFour:
    """Resolving the spell exiles cards off the top of the library until the
    cumulative mana value of the exiled cards is 4 or greater."""

    def test_exiles_until_total_mana_value_at_least_four(self) -> None:
        # Top-down: three {2} cards. After the first two (2+2=4) the threshold
        # is met, so exactly two cards should be exiled.
        game = create_game(scripts=([False, False, False], []))
        p1 = game.players[0]
        a = _sorcery("Two A", "{2}")
        b = _sorcery("Two B", "{2}")
        c = _sorcery("Two C", "{2}")
        _set_library_top_down(game, 0, [a, b, c])
        card = _capstone_on_battlefield_resolving(game, p1)

        card.on_resolve(game)

        exile = game.get_exile(p1)
        assert exile.contains(a)
        assert exile.contains(b)
        assert not exile.contains(c), "should stop once total MV reaches 4"

    def test_stops_as_soon_as_threshold_reached_single_big_card(self) -> None:
        # A single {4} card meets the threshold by itself; only one exiled.
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        big = _sorcery("Big Four", "{4}")
        rest = _sorcery("Untouched", "{1}")
        _set_library_top_down(game, 0, [big, rest])
        card = _capstone_on_battlefield_resolving(game, p1)

        card.on_resolve(game)

        exile = game.get_exile(p1)
        assert exile.contains(big)
        assert not exile.contains(rest)

    def test_exact_threshold_of_four_stops(self) -> None:
        # Top card has MV exactly 4 -> exiled; the next card is left alone.
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        four = _instant("Exactly Four", "{3}{R}")
        nxt = _instant("Next", "{1}")
        _set_library_top_down(game, 0, [four, nxt])
        card = _capstone_on_battlefield_resolving(game, p1)

        card.on_resolve(game)

        exile = game.get_exile(p1)
        assert exile.contains(four)
        assert not exile.contains(nxt)

    def test_zero_mana_value_cards_do_not_satisfy_threshold(self) -> None:
        # Three zero-MV lands then a {4}: must keep exiling past the lands
        # until the cumulative MV reaches 4.
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        l1 = _land("Land A")
        l2 = _land("Land B")
        l3 = _land("Land C")
        payoff = _sorcery("Payoff", "{4}")
        tail = _sorcery("Tail", "{1}")
        _set_library_top_down(game, 0, [l1, l2, l3, payoff, tail])
        card = _capstone_on_battlefield_resolving(game, p1)

        card.on_resolve(game)

        exile = game.get_exile(p1)
        assert exile.contains(l1)
        assert exile.contains(l2)
        assert exile.contains(l3)
        assert exile.contains(payoff), "must keep exiling until MV>=4 is reached"
        assert not exile.contains(tail)

    def test_exiled_cards_leave_the_library(self) -> None:
        game = create_game(scripts=([False, False], []))
        p1 = game.players[0]
        a = _sorcery("Two A", "{2}")
        b = _sorcery("Two B", "{2}")
        keep = _sorcery("Stay", "{1}")
        _set_library_top_down(game, 0, [a, b, keep])
        card = _capstone_on_battlefield_resolving(game, p1)

        card.on_resolve(game)

        library = game.get_library(p1)
        assert not library.contains(a)
        assert not library.contains(b)
        assert library.contains(keep), "untouched cards remain in the library"

    def test_empty_library_is_safe_noop(self) -> None:
        # No cards to exile -> resolving must not raise and must not prompt.
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        _set_library_top_down(game, 0, [])
        card = _capstone_on_battlefield_resolving(game, p1)

        card.on_resolve(game)  # must not raise / must not consume a script entry

        assert len(game.get_exile(p1)) == 0

    def test_library_smaller_than_threshold_exiles_all(self) -> None:
        # Only one {2} card in the library; threshold never reached but the
        # effect exiles what it can and stops (no infinite loop / no crash).
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        only = _sorcery("Only", "{2}")
        _set_library_top_down(game, 0, [only])
        card = _capstone_on_battlefield_resolving(game, p1)

        card.on_resolve(game)

        assert game.get_exile(p1).contains(only)
        assert len(game.get_library(p1)) == 0


# ---------------------------------------------------------------------------
# Main effect: optional free cast of exiled spells
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneFreeCast:
    """The controller "may cast any number of spells from among" the exiled
    cards without paying their mana costs."""

    def test_yes_casts_an_exiled_spell_onto_the_stack(self) -> None:
        # One {4} spell exiled; controller says "yes" to casting it.
        game = create_game(scripts=([True], []))
        p1 = game.players[0]
        game.active_player_index = 0
        spell = _sorcery("Free Cast Me", "{4}")
        _set_library_top_down(game, 0, [spell])
        card = _capstone_on_battlefield_resolving(game, p1)

        card.on_resolve(game)

        # The spell should have moved out of exile onto the stack (free cast).
        assert p1.zones[Zone.STACK].contains(spell)
        assert not game.get_exile(p1).contains(spell)

    def test_free_cast_pays_no_mana(self) -> None:
        game = create_game(scripts=([True], []))
        p1 = game.players[0]
        game.active_player_index = 0
        p1.mana_pool.empty()
        spell = _sorcery("Free Cast Me", "{4}")
        _set_library_top_down(game, 0, [spell])
        card = _capstone_on_battlefield_resolving(game, p1)

        card.on_resolve(game)

        # The spell was actually cast (left exile, now on the stack) ...
        assert p1.zones[Zone.STACK].contains(spell), "the exiled spell should be cast"
        assert not game.get_exile(p1).contains(spell)
        # ... and no mana was spent or produced doing so.
        assert p1.mana_pool.total() == 0, "casting from among exile must pay no mana"

    def test_no_casts_leaves_spell_in_exile(self) -> None:
        # Declining the optional cast leaves the exiled card in exile.
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        spell = _sorcery("Decline Me", "{4}")
        _set_library_top_down(game, 0, [spell])
        card = _capstone_on_battlefield_resolving(game, p1)

        card.on_resolve(game)

        assert game.get_exile(p1).contains(spell)
        assert game.stack.is_empty()

    def test_can_cast_multiple_exiled_spells(self) -> None:
        # Two {2} spells exiled (total MV 4). Saying yes to both casts both.
        game = create_game(scripts=([True, True], []))
        p1 = game.players[0]
        game.active_player_index = 0
        s1 = _sorcery("Spell One", "{2}")
        s2 = _sorcery("Spell Two", "{2}")
        _set_library_top_down(game, 0, [s1, s2])
        card = _capstone_on_battlefield_resolving(game, p1)

        card.on_resolve(game)

        library = game.get_library(p1)
        exile = game.get_exile(p1)
        # Both were exiled off the top (so they left the library) ...
        assert not library.contains(s1)
        assert not library.contains(s2)
        # ... and both were cast (left exile); neither remains in exile.
        assert not exile.contains(s1)
        assert not exile.contains(s2)
        # At least one of them should be observable on the stack as a cast spell.
        on_stack = [
            obj for obj in p1.zones[Zone.STACK].get_all() if obj in (s1, s2)
        ]
        assert len(on_stack) >= 1, "casting multiple spells should put them on the stack"

    def test_lands_among_exiled_cards_are_not_offered_as_spells(self) -> None:
        # "cast any number of spells" — lands are not spells, so a land among
        # the exiled cards must not consume a yes/no prompt and stays in exile.
        # Script has a single entry for the one castable spell.
        game = create_game(scripts=([True], []))
        p1 = game.players[0]
        game.active_player_index = 0
        land = _land("Exiled Land")
        spell = _sorcery("Payoff Spell", "{4}")
        _set_library_top_down(game, 0, [land, spell])
        card = _capstone_on_battlefield_resolving(game, p1)

        card.on_resolve(game)

        exile = game.get_exile(p1)
        # The land cannot be cast and remains exiled; the spell was cast.
        assert exile.contains(land)
        assert not exile.contains(spell)


# ---------------------------------------------------------------------------
# Paradigm: the spell exiles itself instead of going to the graveyard
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneParadigmSelfExile:
    """Paradigm: "Then exile this spell." — after resolving, the Capstone
    itself is exiled rather than put into the graveyard, so it can be
    recast later from exile."""

    def test_resolved_capstone_is_exiled_not_in_graveyard(self) -> None:
        # Drive a full free-cast resolution through the engine pipeline so the
        # stack->zone move happens, then assert the spell ends up in exile.
        from engine.casting import cast_spell_free

        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        game.active_player_index = 0
        # Put a single low-value card in the library so resolution is simple.
        filler = _sorcery("Filler", "{4}")
        _set_library_top_down(game, 0, [filler])

        card = ImprovisationCapstone(owner=p1, controller=p1)
        # Place the Capstone in the hand and free-cast it so the engine routes
        # its stack->graveyard move through replacement effects (Paradigm
        # should redirect it to exile).
        set_board_state(game, 0, hand=[card])
        card.register_replacement_effects(game)
        cast_spell_free(game, p1, card, Zone.HAND)
        # Resolve the Capstone spell itself.
        stack_obj = game.stack.pop()
        stack_obj.on_resolve(game)

        assert game.get_exile(p1).contains(card), (
            "Paradigm should exile the spell instead of sending it to the graveyard"
        )
        assert not game.get_graveyard(p1).contains(card)


# ---------------------------------------------------------------------------
# Paradigm: recast a copy at the beginning of each first main phase
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneParadigmRecast:
    """Paradigm sets up a begin-of-(first)-main-phase trigger that lets the
    controller cast a copy of the spell from exile for free.  Following the
    sos_57 convention, the delayed/recurring ability is wired through the
    trigger manager keyed to ``BeginningOfMainPhaseTriggeredEvent``."""

    def test_resolution_registers_a_begin_of_main_phase_trigger(self) -> None:
        from engine.events import BeginningOfMainPhaseTriggeredEvent

        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        game.active_player_index = 0
        filler = _sorcery("Filler", "{4}")
        _set_library_top_down(game, 0, [filler])
        card = _capstone_on_battlefield_resolving(game, p1)

        before = len(game.trigger_manager.get_triggers_for_source(card))
        card.on_resolve(game)
        regs = game.trigger_manager.get_triggers_for_source(card)
        after = len(regs)

        assert after - before >= 1, "Paradigm must register a recurring trigger"
        assert any(
            r.event_type is BeginningOfMainPhaseTriggeredEvent for r in regs
        ), "the Paradigm trigger must watch BeginningOfMainPhaseTriggeredEvent"

    def test_paradigm_trigger_controller_is_the_capstone_controller(self) -> None:
        from engine.events import BeginningOfMainPhaseTriggeredEvent

        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        game.active_player_index = 0
        filler = _sorcery("Filler", "{4}")
        _set_library_top_down(game, 0, [filler])
        card = _capstone_on_battlefield_resolving(game, p1)

        card.on_resolve(game)
        regs = [
            r
            for r in game.trigger_manager.get_triggers_for_source(card)
            if r.event_type is BeginningOfMainPhaseTriggeredEvent
        ]
        assert regs, "expected a begin-of-main-phase trigger"
        assert regs[0].controller is p1

    def test_paradigm_trigger_only_fires_for_controllers_main_phase(self) -> None:
        # The trigger condition must reject another player's main phase
        # ("the beginning of each of your first main phases").
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.types import Phase

        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        p2 = game.players[1]
        game.active_player_index = 0
        filler = _sorcery("Filler", "{4}")
        _set_library_top_down(game, 0, [filler])
        card = _capstone_on_battlefield_resolving(game, p1)

        card.on_resolve(game)
        regs = [
            r
            for r in game.trigger_manager.get_triggers_for_source(card)
            if r.event_type is BeginningOfMainPhaseTriggeredEvent
        ]
        assert regs, "expected a begin-of-main-phase trigger"
        reg = regs[0]
        if reg.condition is None:
            raise AssertionError(
                "Paradigm trigger must be conditioned on the controller's main phase"
            )
        opp_event = BeginningOfMainPhaseTriggeredEvent(
            player=p2, phase=Phase.PRECOMBAT_MAIN
        )
        assert reg.condition(game, opp_event) is False
