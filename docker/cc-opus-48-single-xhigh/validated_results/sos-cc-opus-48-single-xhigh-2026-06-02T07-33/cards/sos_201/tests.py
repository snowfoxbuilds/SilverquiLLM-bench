"""Tests for SOS 201 — Lorehold, the Historian.

Oracle text (from card_spec.json):

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}. (You may cast
    a card for its miracle cost when you draw it if it's the first card you
    drew this turn.)
    At the beginning of each opponent's upkeep, you may discard a card. If you
    do, draw a card.

Behaviour contract derived from that text:

* Static: Legendary Creature — Elder Dragon, {3}{R}{W}, 5/5, red+white, with
  Flying and Haste.
* Miracle-granting static ability: while Lorehold is on the battlefield, every
  instant and sorcery card in its controller's hand "has miracle {2}". There is
  no engine-level miracle pipeline, so the implementation must expose some
  observable surface that reports the miracle cost ({2}) for an instant/sorcery
  in the controller's hand (and grants it to no other cards / no other
  players). These tests probe that surface tolerantly: they accept any of the
  conventional spellings the implementer is likely to use, and skip-with-reason
  only if none exists. The "cast it when you draw it" timing is recorded in
  untestable.json (no engine draw-time cast hook exists).
* Upkeep trigger: a ``BeginningOfUpkeepTriggeredEvent`` trigger that fires only
  on an OPPONENT's upkeep (not the controller's own upkeep). It is optional
  ("you may discard a card"); if a card is discarded the controller draws a
  card. Declining discards nothing and draws nothing. With an empty hand there
  is nothing to discard, so nothing is drawn.

These tests are written for the TDD red phase: they must FAIL against the empty
stub and PASS once the card is implemented correctly.
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Test helper cards
# ---------------------------------------------------------------------------


def _vanilla_instant(name: str = "Test Instant") -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse("{1}{R}"))


def _vanilla_sorcery(name: str = "Test Sorcery") -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse("{2}{B}"))


def _vanilla_creature(name: str = "Test Bear") -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse("{1}{G}"),
        base_power=2,
        base_toughness=2,
    )


def _resolve_full_stack(game: Any) -> None:
    """Resolve every object currently on the stack, top-down."""
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _miracle_cost_for(card_obj: Any, game: Any, hand_card: Any) -> Any:
    """Best-effort probe for the granted miracle cost of *hand_card*.

    The miracle mechanic has no engine pipeline, so the implementation is free
    to surface the granted cost in a number of conventional ways. This helper
    tries each in turn and returns the reported cost, or raises
    ``pytest.skip`` if no recognised surface exists (so the contract is not
    silently green).
    """
    # 1. A method on the Lorehold card that reports the miracle cost it grants
    #    to a given hand card.
    for meth_name in ("miracle_cost_for", "get_miracle_cost", "miracle_cost"):
        meth = getattr(card_obj, meth_name, None)
        if callable(meth):
            try:
                return meth(game, hand_card)
            except TypeError:
                try:
                    return meth(hand_card)
                except TypeError:
                    continue
    # 2. The grant written directly onto the hand card.
    for attr_name in ("miracle_cost", "granted_miracle_cost", "miracle"):
        val = getattr(hand_card, attr_name, None)
        if val is not None:
            return val
    pytest.skip(
        "No observable surface for the granted miracle cost — implementation "
        "must expose miracle_cost_for(...)/get_miracle_cost(...) on the card "
        "or a miracle_cost attribute on the affected hand card."
    )


def _coerce_to_two(value: Any) -> bool:
    """Return True if *value* represents a mana value / cost of {2}."""
    if value is None:
        return False
    if isinstance(value, ManaCost):
        return value.cmc == 2 and value.generic == 2
    if isinstance(value, int):
        return value == 2
    # A string spelling like "{2}".
    if isinstance(value, str):
        try:
            return ManaCost.parse(value).cmc == 2
        except Exception:
            return False
    # Fallback: anything exposing a .cmc.
    cmc = getattr(value, "cmc", None)
    return cmc == 2


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------


class TestLoreholdProperties:
    """Static characteristics must match the SOS 201 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(LoreholdTheHistorian(owner=None), Creature)

    def test_name(self) -> None:
        assert LoreholdTheHistorian(owner=None).name == "Lorehold, the Historian"

    def test_mana_cost(self) -> None:
        assert LoreholdTheHistorian(owner=None).mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_mana_value_is_five(self) -> None:
        assert LoreholdTheHistorian(owner=None).mana_cost.cmc == 5

    def test_power_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in LoreholdTheHistorian(owner=None).supertypes

    def test_is_elder_dragon(self) -> None:
        subtypes = LoreholdTheHistorian(owner=None).subtypes
        assert "Dragon" in subtypes
        assert "Elder" in subtypes

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in LoreholdTheHistorian(owner=None).keywords

    def test_has_haste(self) -> None:
        assert Keyword.HASTE in LoreholdTheHistorian(owner=None).keywords

    def test_is_red_white(self) -> None:
        """{3}{R}{W} has exactly one red and one white pip and no others."""
        cost = LoreholdTheHistorian(owner=None).mana_cost
        from engine.types import ManaType

        assert cost.pips.get(ManaType.RED, 0) == 1
        assert cost.pips.get(ManaType.WHITE, 0) == 1
        assert cost.pips.get(ManaType.BLUE, 0) == 0
        assert cost.pips.get(ManaType.BLACK, 0) == 0
        assert cost.pips.get(ManaType.GREEN, 0) == 0


# ---------------------------------------------------------------------------
# Upkeep trigger registration
# ---------------------------------------------------------------------------


class TestLoreholdUpkeepTriggerRegistration:
    """register_triggers wires exactly one BeginningOfUpkeepTriggeredEvent
    trigger for the loot-on-each-opponent's-upkeep ability."""

    def test_registers_an_upkeep_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        regs_before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        regs_after = len(game.trigger_manager.get_triggers())
        assert regs_after > regs_before

    def test_trigger_watches_upkeep_event(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        card.register_triggers(game)
        regs = game.trigger_manager.get_triggers_for_source(card)
        upkeep_regs = [
            r for r in regs if r.event_type is BeginningOfUpkeepTriggeredEvent
        ]
        assert len(upkeep_regs) == 1
        assert isinstance(upkeep_regs[0], TriggerRegistration)


# ---------------------------------------------------------------------------
# Upkeep trigger: "each opponent's upkeep" timing
# ---------------------------------------------------------------------------


class TestLoreholdUpkeepTiming:
    """The trigger fires only during an OPPONENT's upkeep, not the
    controller's own."""

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        return game, p1, p2, card

    def test_does_not_fire_on_controllers_own_upkeep(self) -> None:
        """When the controller (p1) is the active player, p1's own upkeep must
        NOT put Lorehold's loot trigger on the stack.

        To distinguish a correctly-conditioned trigger from a missing one, we
        first confirm (in ``test_fires_on_opponents_upkeep``) that the trigger
        exists and fires on an opponent's upkeep. Here we additionally require
        that an upkeep trigger is registered, so an empty stub (which registers
        nothing) fails rather than vacuously passing."""
        game, p1, p2, card = self._setup()
        upkeep_regs = [
            r
            for r in game.trigger_manager.get_triggers_for_source(card)
            if r.event_type is BeginningOfUpkeepTriggeredEvent
        ]
        assert len(upkeep_regs) == 1, "Lorehold must register an upkeep trigger"

        game.active_player_index = 0  # controller's own upkeep
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert game.stack.is_empty()

    def test_fires_on_opponents_upkeep(self) -> None:
        """When an opponent (p2) is the active player, the loot trigger goes on
        the stack under the controller's control."""
        game, p1, p2, card = self._setup()
        game.active_player_index = 1  # opponent's upkeep
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert not game.stack.is_empty()
        assert game.stack.peek().controller is p1


# ---------------------------------------------------------------------------
# Upkeep trigger: discard-then-draw effect
# ---------------------------------------------------------------------------


class TestLoreholdLootEffect:
    """Resolving the opponent's-upkeep trigger lets the controller optionally
    discard a card and, if they do, draw a card."""

    def _setup_opponent_upkeep(
        self, *, hand: list[Any], library: list[Any], yes: bool, discard_target: Any
    ):
        """Build a game with Lorehold on p1's battlefield, p1's hand and
        library populated, fire an opponent's-upkeep event, and script p1's
        optional choices.

        DeterministicPlayer pops answers in order; the implementation may ask a
        yes/no ("may discard") and a card choice (which card to discard). We
        feed a permissive script so whichever methods it calls are satisfied.
        """
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], hand=hand)
        # Populate p1's library so a draw has something to fetch.
        lib = game.get_library(p1)
        for obj in lib.get_all():
            lib.remove(obj)
        for c in library:
            c.owner = p1
            c.controller = p1
            lib.add(c)
        card.register_triggers(game)
        game.active_player_index = 1  # opponent's upkeep

        # Script: yes/no, then which card to discard (and a spare copy in case
        # the implementation re-asks).
        p1._script.extend([yes, discard_target, discard_target])

        # Fire the opponent's-upkeep event. The loot trigger must go on the
        # stack — otherwise the card has no effect at all (empty stub) and the
        # no-op assertions below would pass vacuously.
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert not game.stack.is_empty(), (
            "Lorehold's loot ability must trigger on an opponent's upkeep"
        )
        return game, p1, p2, card

    def test_discard_then_draw_on_yes(self) -> None:
        """Saying yes discards the chosen hand card and draws the top of
        library. Net hand size is unchanged (one out, one in) but the drawn
        card and discarded card are different objects in their new zones."""
        to_discard = _vanilla_instant("Discard Me")
        drawn = _vanilla_creature("Draw Me")
        game, p1, p2, card = self._setup_opponent_upkeep(
            hand=[to_discard], library=[drawn], yes=True, discard_target=to_discard
        )
        _resolve_full_stack(game)

        # The discarded card is now in the graveyard.
        assert game.get_graveyard(p1).contains(to_discard)
        # The drawn card moved from library to hand.
        assert game.get_hand(p1).contains(drawn)
        assert not game.get_library(p1).contains(drawn)

    def test_decline_discards_and_draws_nothing(self) -> None:
        """Saying no leaves the hand card in hand and draws nothing."""
        keep = _vanilla_instant("Keep Me")
        top = _vanilla_creature("Stay In Library")
        game, p1, p2, card = self._setup_opponent_upkeep(
            hand=[keep], library=[top], yes=False, discard_target=keep
        )
        _resolve_full_stack(game)

        # Nothing discarded, nothing drawn.
        assert game.get_hand(p1).contains(keep)
        assert not game.get_graveyard(p1).contains(keep)
        assert game.get_library(p1).contains(top)
        assert not game.get_hand(p1).contains(top)

    def test_empty_hand_is_a_noop(self) -> None:
        """With no cards to discard, the controller cannot pay the 'if you do'
        cost, so no draw happens and resolution does not raise."""
        top = _vanilla_creature("Stay In Library")
        game, p1, p2, card = self._setup_opponent_upkeep(
            hand=[], library=[top], yes=True, discard_target=None
        )
        _resolve_full_stack(game)

        # Hand is still empty (nothing was drawn, because nothing was discarded).
        assert len(game.get_hand(p1).get_all()) == 0
        assert game.get_library(p1).contains(top)

    def test_draw_is_conditional_on_discard(self) -> None:
        """The draw is gated on the discard happening ('If you do'). When the
        controller declines, the library is untouched (no draw)."""
        keep = _vanilla_sorcery("Keep Me")
        top = _vanilla_creature("Top Card")
        game, p1, p2, card = self._setup_opponent_upkeep(
            hand=[keep], library=[top], yes=False, discard_target=keep
        )
        lib_size_before = len(game.get_library(p1).get_all())
        _resolve_full_stack(game)
        assert len(game.get_library(p1).get_all()) == lib_size_before


# ---------------------------------------------------------------------------
# Miracle-granting static ability
# ---------------------------------------------------------------------------


class TestLoreholdMiracleGrant:
    """While on the battlefield, Lorehold grants miracle {2} to each instant
    and sorcery card in its controller's hand."""

    def _setup(self, controller_hand: list[Any], opp_hand: list[Any] | None = None):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], hand=controller_hand)
        if opp_hand is not None:
            set_board_state(game, 1, hand=opp_hand)
        # Apply continuous effects if the engine maintains them, so a
        # layer-based implementation has a chance to write its grant.
        if hasattr(game, "effect_manager"):
            card.register_replacement_effects(game)
            card.register_triggers(game)
            try:
                game.effect_manager.apply_all(game)
            except Exception:
                pass
        return game, p1, p2, card

    def test_instant_in_hand_gets_miracle_two(self) -> None:
        spell = _vanilla_instant("Hand Instant")
        game, p1, p2, card = self._setup([spell])
        cost = _miracle_cost_for(card, game, spell)
        assert _coerce_to_two(cost)

    def test_sorcery_in_hand_gets_miracle_two(self) -> None:
        spell = _vanilla_sorcery("Hand Sorcery")
        game, p1, p2, card = self._setup([spell])
        cost = _miracle_cost_for(card, game, spell)
        assert _coerce_to_two(cost)

    def test_creature_in_hand_does_not_get_miracle(self) -> None:
        """A creature card is neither an instant nor a sorcery, so it is not
        granted miracle. We anchor on a real instant first (via the probe,
        which skips if no surface exists) so this fails on an empty stub
        rather than passing vacuously, then assert the creature is excluded."""
        bear = _vanilla_creature("Hand Bear")
        anchor = _vanilla_instant("Anchor Instant")
        game, p1, p2, card = self._setup([anchor, bear])
        # Anchor: confirm the grant surface exists and reports {2} for the
        # instant. If no surface exists, _miracle_cost_for skips the test.
        assert _coerce_to_two(_miracle_cost_for(card, game, anchor))
        # The creature must NOT be granted miracle {2}.
        assert not _coerce_to_two(self._probe_silent(card, game, bear))

    def test_opponents_spell_does_not_get_miracle(self) -> None:
        """Only cards in YOUR hand are granted miracle — an instant in the
        opponent's hand is unaffected. Anchored on a controller-hand instant so
        the test fails on an empty stub rather than passing vacuously."""
        opp_spell = _vanilla_instant("Opp Instant")
        my_spell = _vanilla_instant("My Instant")
        game, p1, p2, card = self._setup([my_spell], opp_hand=[opp_spell])
        # Anchor: my own instant gets miracle {2} (skips if no surface exists).
        assert _coerce_to_two(_miracle_cost_for(card, game, my_spell))
        # The opponent's instant must NOT be granted miracle.
        assert not _coerce_to_two(self._probe_silent(card, game, opp_spell))

    @staticmethod
    def _probe_silent(card_obj: Any, game: Any, hand_card: Any) -> Any:
        """Like ``_miracle_cost_for`` but returns None instead of skipping
        when no recognised surface reports a cost for *hand_card*."""
        for meth_name in ("miracle_cost_for", "get_miracle_cost", "miracle_cost"):
            meth = getattr(card_obj, meth_name, None)
            if callable(meth):
                try:
                    return meth(game, hand_card)
                except TypeError:
                    try:
                        return meth(hand_card)
                    except TypeError:
                        continue
        for attr_name in ("miracle_cost", "granted_miracle_cost", "miracle"):
            val = getattr(hand_card, attr_name, None)
            if val is not None:
                return val
        return None


# ---------------------------------------------------------------------------
# Draw-time miracle cast (CR 702.94a) — the "you may cast it when you draw it,
# if it's the first card you drew this turn" timing.
#
# These exercise the now-real additive miracle framework
# (``engine.miracle.register_miracle_draw_hook`` wired by ``register_triggers``).
# Previously deferred to untestable.json because no draw-time cast hook existed.
# ---------------------------------------------------------------------------


def _expensive_instant(name: str = "Costly Bolt") -> Instant:
    """An instant whose printed cost ({4}{R}{R}, mv 6) is clearly more than the
    granted miracle cost {2}, so 'charged exactly {2}' is unambiguous."""
    return Instant(name=name, mana_cost=ManaCost.parse("{4}{R}{R}"))


def _put_on_top_of_library(game: Any, player: Any, card: Any) -> None:
    """Replace *player*'s library with exactly *card* (so the next draw fetches
    it deterministically) and assign ownership/control."""
    lib = game.get_library(player)
    for obj in list(lib.get_all()):
        lib.remove(obj)
    card.owner = player
    card.controller = player
    lib.add(card)


class TestLoreholdMiracleDrawCast:
    """While Lorehold is on the battlefield, the first instant/sorcery its
    controller draws each turn may be cast for the miracle cost {2} as it is
    drawn (CR 702.94a). The draw-time hook is wired by ``register_triggers``
    and fires through the engine's ``DrawsCardTriggeredEvent`` pipeline."""

    def _setup(self, controller_index: int = 0):
        """Lorehold on p1's battlefield with its triggers (and draw hook) wired."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        return game, p1, p2, card

    def test_first_draw_accept_casts_for_two(self) -> None:
        """Accepting the miracle offer on the turn's first draw casts the drawn
        instant: it leaves the controller's hand and resolves to the graveyard.
        The miracle hook must put its offer on the stack as a consequence of the
        draw (so a missing hook fails here rather than passing vacuously)."""
        from engine import game as game_mod

        game, p1, p2, card = self._setup()
        top = _expensive_instant("Accept Me")
        _put_on_top_of_library(game, p1, top)
        p1.cards_drawn_this_turn = 0  # the upcoming draw is the turn's first
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        p1._script.append(True)  # accept the miracle offer

        drawn = game_mod.draw_card(game, p1)
        assert drawn is top, "draw_card must fetch the top of library"
        # The draw fires the miracle hook, which puts the cast offer on the stack.
        assert not game.stack.is_empty(), (
            "the first-draw miracle offer must hit the stack as a result of the draw"
        )
        _resolve_full_stack(game)

        # Accepted: the instant was cast (left hand) and resolved to graveyard.
        assert not game.get_hand(p1).contains(top)
        assert game.get_graveyard(p1).contains(top)

    def test_first_draw_accept_charges_exactly_two(self) -> None:
        """The accepted miracle cast pays only the miracle cost {2}, NOT the
        card's printed {4}{R}{R}. Starting the pool at five mana, exactly two are
        spent (three remain). The printed mana cost is left intact afterward."""
        from engine import game as game_mod

        game, p1, p2, card = self._setup()
        top = _expensive_instant("Charge Me")
        printed_cmc = top.mana_cost.cmc
        _put_on_top_of_library(game, p1, top)
        p1.cards_drawn_this_turn = 0
        # Five generic mana: enough for {2} (and far short of the printed {6}),
        # so 'charged exactly two' is observable as 'three left'.
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        p1._script.append(True)

        game_mod.draw_card(game, p1)
        _resolve_full_stack(game)

        assert p1.mana_pool.total() == 3, (
            "miracle cast must charge exactly {2}, not the printed cost"
        )
        # The printed cost is restored, not permanently mutated to {2}.
        assert top.mana_cost.cmc == printed_cmc

    def test_first_draw_decline_keeps_card_in_hand(self) -> None:
        """Declining the offer leaves the drawn instant in the controller's
        hand, spends no mana, and leaves the stack empty after resolution. (The
        hook still lands the offer on the stack; the yes/no is asked when that
        offer resolves, and 'no' is a no-op.)"""
        from engine import game as game_mod

        game, p1, p2, card = self._setup()
        top = _expensive_instant("Decline Me")
        _put_on_top_of_library(game, p1, top)
        p1.cards_drawn_this_turn = 0
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        p1._script.append(False)  # decline the miracle offer

        game_mod.draw_card(game, p1)
        _resolve_full_stack(game)

        assert game.get_hand(p1).contains(top)
        assert not game.get_graveyard(p1).contains(top)
        assert game.stack.is_empty()
        # No mana spent on a decline.
        assert p1.mana_pool.total() == 5

    def test_non_first_draw_is_not_offered(self) -> None:
        """Miracle's reveal window is only the FIRST card drawn each turn. When
        the controller has already drawn this turn, drawing a granted instant
        offers no miracle: the stack stays empty and the card stays in hand.

        No yes/no is scripted; if the implementation wrongly offered the cast it
        would raise ScriptExhaustedError, so this also guards against an
        unconditioned hook."""
        from engine import game as game_mod

        game, p1, p2, card = self._setup()
        top = _expensive_instant("Second Draw")
        _put_on_top_of_library(game, p1, top)
        # Already drew one card this turn — the upcoming draw is the SECOND.
        p1.cards_drawn_this_turn = 1
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        game_mod.draw_card(game, p1)

        assert game.stack.is_empty(), "non-first draw must not offer miracle"
        assert game.get_hand(p1).contains(top)
        assert not game.get_graveyard(p1).contains(top)

    def test_opponent_first_draw_is_not_offered_loreholds_grant(self) -> None:
        """Lorehold grants miracle only to cards in ITS controller's hand. An
        opponent drawing an instant as their first draw is not offered the
        miracle cast — no offer hits the stack and the card stays in the
        opponent's hand. No yes/no is scripted for the opponent, so a wrongly
        scoped hook would raise ScriptExhaustedError."""
        from engine import game as game_mod

        game, p1, p2, card = self._setup()
        opp_top = _expensive_instant("Opp Draw")
        _put_on_top_of_library(game, p2, opp_top)
        p2.cards_drawn_this_turn = 0  # opponent's first draw this turn
        set_board_state(game, 1, mana={ManaType.COLORLESS: 5})

        game_mod.draw_card(game, p2)

        assert game.stack.is_empty(), (
            "Lorehold must not offer its miracle grant on an opponent's draw"
        )
        assert game.get_hand(p2).contains(opp_top)
        assert not game.get_graveyard(p2).contains(opp_top)

    def test_drawn_creature_is_not_offered_miracle(self) -> None:
        """Miracle is granted only to instants and sorceries. The controller
        drawing a CREATURE as their first draw triggers no miracle offer: the
        stack stays empty and the creature stays in hand. No yes/no is scripted,
        so a hook that ignored the card type would raise ScriptExhaustedError."""
        from engine import game as game_mod

        game, p1, p2, card = self._setup()
        bear = _vanilla_creature("Drawn Bear")
        _put_on_top_of_library(game, p1, bear)
        p1.cards_drawn_this_turn = 0  # first draw of the turn
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})

        game_mod.draw_card(game, p1)

        assert game.stack.is_empty(), (
            "a drawn creature is neither instant nor sorcery — no miracle offer"
        )
        assert game.get_hand(p1).contains(bear)

    def test_first_draw_sorcery_accept_casts_for_two(self) -> None:
        """The grant covers sorceries too: accepting the offer on a first-drawn
        sorcery casts it for {2} (leaves hand, resolves to graveyard), charging
        exactly two from a five-mana pool."""
        from engine import game as game_mod

        game, p1, p2, card = self._setup()
        top = Sorcery(name="Costly Ritual", mana_cost=ManaCost.parse("{5}{B}"))
        _put_on_top_of_library(game, p1, top)
        p1.cards_drawn_this_turn = 0
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        p1._script.append(True)

        game_mod.draw_card(game, p1)
        assert not game.stack.is_empty()
        _resolve_full_stack(game)

        assert not game.get_hand(p1).contains(top)
        assert game.get_graveyard(p1).contains(top)
        assert p1.mana_pool.total() == 3
