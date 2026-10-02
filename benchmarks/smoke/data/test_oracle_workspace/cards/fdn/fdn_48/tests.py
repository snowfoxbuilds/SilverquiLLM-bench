"""Regression tests for FDN 48 — Refute.

Refute is cast through the REAL pipeline: its Zone.STACK target requirement
offers exact StackObject occurrences (never source cards), the chosen
occurrence is revalidated at resolution (it must still be on ``game.stack``),
and the counter itself goes through the engine's shared stack-departure
primitive (:func:`engine.stack.move_spell_off_stack`) — an ordinary countered
spell to its owner's graveyard (rule 701.5a), a flashbacked spell to exile
(rule 702.34a). A target occurrence that already left the stack fizzles the
whole spell (rule 608.2b): no counter, no draw/discard, and never a move of a
re-cast card.
"""

from __future__ import annotations

import pytest
from cards.fdn.fdn_48.card_impl import Refute
from engine.card import Creature, Instant
from engine.casting import CastingError, CastMode, cast_spell_free
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.stack import StackObject, move_spell_off_stack, resolve_top_of_stack
from engine.types import ManaCost, Zone
from test_utils import create_game


def _library_card(name: str = "Blank"):
    return Creature(name=name, base_power=1, base_toughness=1)


class TestRefuteProperties:
    def test_is_instant(self) -> None:
        assert isinstance(Refute(owner=None), Instant)

    def test_mana_cost(self) -> None:
        assert Refute(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")


class TestRefuteCounters:
    def _game(self):
        game = create_game()
        p1, p2 = game.players
        # A card for Refute's controller to draw.
        game.get_library(p1).add(_library_card())
        return game, p1, p2

    def _spell(self, owner, *, flashback: bool = False):
        card = Instant(name="Zap", mana_cost=ManaCost.parse("{U}"), owner=owner)
        card.controller = owner
        if flashback:
            card.flashback_cost = ManaCost.parse("{2}{U}")
        return card

    def _cast_refute_at(self, game, p1, occurrence):
        """Cast Refute through the real pipeline, selecting *occurrence* by its
        engine-minted stack instance id — the occurrence's own identity,
        matching what the Zone.STACK target enumeration offers."""
        refute = Refute(owner=p1, controller=p1)
        game.get_hand(p1).add(refute)
        occ_iid = game.refs.instance_id(occurrence, Zone.STACK.value)
        p1.start_intent("refute-cast", Intent(
            pattern=GameRef(card=frozenset({("name", "Refute")})),
            preferences=(Decision.obj(instance=occ_iid),),
        ))
        try:
            refute_so = cast_spell_free(game, p1, refute, Zone.HAND)
        finally:
            p1.end_intent("refute-cast")
        assert refute_so.targets[0] is occurrence  # the occurrence, not the card
        return refute, refute_so

    def _resolve_top_as(self, game, p1):
        """Resolve the top of the stack with an intent answering Refute's
        discard query (first offered option)."""
        p1.start_intent("refute-resolve", Intent(
            pattern=GameRef(card=frozenset({("name", "Refute")})),
            preferences=(),
        ))
        try:
            resolve_top_of_stack(game)
        finally:
            p1.end_intent("refute-resolve")

    def test_ordinary_countered_spell_to_owner_graveyard(self) -> None:
        game, p1, p2 = self._game()
        spell = self._spell(p2)
        game.get_hand(p2).add(spell)
        so = cast_spell_free(game, p2, spell, Zone.HAND)

        refute, _ = self._cast_refute_at(game, p1, so)
        self._resolve_top_as(game, p1)

        # Destination ownership: the countered card goes to ITS owner's (p2's)
        # graveyard; Refute goes to its own owner's (p1's) graveyard.
        assert game.get_graveyard(p2).contains(spell)
        assert not game.get_exile(p2).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)
        assert game.get_graveyard(p1).contains(refute)
        assert game.stack.is_empty()

    def test_flashback_countered_spell_exiled(self) -> None:
        """Countering a flashbacked spell exiles it (rule 702.34a) — the
        departure replacement applies to countering exactly as to resolution."""
        game, p1, p2 = self._game()
        spell = self._spell(p2, flashback=True)
        game.get_graveyard(p2).add(spell)
        so = cast_spell_free(game, p2, spell, Zone.GRAVEYARD, mode=CastMode.FLASHBACK)

        self._cast_refute_at(game, p1, so)
        self._resolve_top_as(game, p1)

        assert game.get_exile(p2).contains(spell)
        assert not game.get_graveyard(p2).contains(spell)

    def test_refute_draws_and_discards_on_successful_counter(self) -> None:
        game, p1, p2 = self._game()
        spell = self._spell(p2)
        game.get_hand(p2).add(spell)
        so = cast_spell_free(game, p2, spell, Zone.HAND)
        hand_before = len(game.get_hand(p1))

        self._cast_refute_at(game, p1, so)
        self._resolve_top_as(game, p1)

        # Draw a card, then discard a card: net hand size unchanged, but the
        # library card moved through the hand.
        assert len(game.get_library(p1)) == 0
        assert len(game.get_hand(p1)) == hand_before  # +1 draw, -1 discard

    def test_counter_fizzles_when_occurrence_departed_and_recast(self) -> None:
        """Rule 608.2b: the targeted OCCURRENCE left the stack, so Refute
        fizzles entirely at resolution — the re-cast of the same card (a new
        occurrence) is not touched, the card is not moved again, and the
        draw/discard secondary effect does not happen."""
        game, p1, p2 = self._game()
        spell = self._spell(p2)
        game.get_hand(p2).add(spell)
        so = cast_spell_free(game, p2, spell, Zone.HAND)

        refute, _ = self._cast_refute_at(game, p1, so)

        # The targeted occurrence departs (countered by something else) …
        assert move_spell_off_stack(game, so) is True
        assert game.get_graveyard(p2).contains(spell)
        # … and the same card is re-cast: a NEW occurrence.
        recast_so = cast_spell_free(game, p2, spell, Zone.GRAVEYARD)
        assert recast_so is not so

        resolve_top_of_stack(game)  # the recast resolves normally
        assert game.get_graveyard(p2).contains(spell)

        library_before = len(game.get_library(p1))
        self._resolve_top_as(game, p1)  # Refute resolves — and fizzles

        assert sum(1 for o in game.get_graveyard(p2).get_all() if o is spell) == 1
        assert not game.get_exile(p2).contains(spell)
        assert len(game.get_library(p1)) == library_before  # no draw on fizzle
        assert game.get_graveyard(p1).contains(refute)
        assert game.stack.is_empty()

    def test_copy_countered_distinctly_from_original(self) -> None:
        """A spell COPY is its own occurrence: countering the copy leaves the
        original cast (and its card) untouched, and moves no card (a copy's
        card occupies no stack zone, rule 707.10a)."""
        from engine.stack import copy_spell

        game, p1, p2 = self._game()
        spell = self._spell(p2)
        game.get_hand(p2).add(spell)
        so = cast_spell_free(game, p2, spell, Zone.HAND)
        copy_so = copy_spell(game, so, p2)
        game.stack.push(copy_so)

        _, refute_so = self._cast_refute_at(game, p1, copy_so)
        assert refute_so.targets[0] is copy_so
        self._resolve_top_as(game, p1)

        assert not game.stack.contains(copy_so)
        assert game.stack.contains(so)  # original untouched
        assert p2.zones[Zone.STACK].contains(spell)
        assert not game.get_graveyard(p2).contains(spell)

    def test_trigger_sharing_source_card_is_not_a_target_spell(self) -> None:
        """A triggered ability on the stack is NOT a spell, even though it has
        a source card: with only it on the stack Refute has no legal target
        and cannot be cast."""
        game, p1, p2 = self._game()
        permanent = Creature(name="Watcher", base_power=2, base_toughness=2, owner=p2)
        permanent.controller = p2
        game.get_battlefield(p2).add(permanent)
        trigger = StackObject(source=permanent, controller=p2)  # is_spell=False
        game.stack.push(trigger)

        refute = Refute(owner=p1, controller=p1)
        game.get_hand(p1).add(refute)
        assert refute.can_cast(game) is False
        with pytest.raises(CastingError):
            cast_spell_free(game, p1, refute, Zone.HAND)
        assert game.get_hand(p1).contains(refute)  # rolled back
        assert game.stack.contains(trigger)
