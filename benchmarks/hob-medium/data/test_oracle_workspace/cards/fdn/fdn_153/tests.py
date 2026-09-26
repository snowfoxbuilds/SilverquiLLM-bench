"""Regression tests for FDN 153 — Essence Scatter.

Essence Scatter is cast through the REAL pipeline: its Zone.STACK target
requirement offers exact StackObject occurrences (never source cards), only
creature-SPELL occurrences qualify (a triggered ability sourced by a creature
card — or by a battlefield creature — is not a creature spell), and the
counter routes through :func:`engine.stack.move_spell_off_stack` (owner's
graveyard for an ordinary spell). A departed occurrence fizzles the spell.
"""

from __future__ import annotations

import pytest
from cards.fdn.fdn_153.card_impl import EssenceScatter
from engine.card import Creature, Instant
from engine.casting import CastingError, cast_spell_free
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.stack import (
    StackObject,
    copy_spell,
    move_spell_off_stack,
    resolve_top_of_stack,
)
from engine.types import ManaCost, Zone
from test_utils import create_game


class TestEssenceScatterProperties:
    def test_is_instant(self) -> None:
        assert isinstance(EssenceScatter(owner=None), Instant)

    def test_mana_cost(self) -> None:
        assert EssenceScatter(owner=None).mana_cost == ManaCost.parse("{1}{U}")


class TestEssenceScatterCounters:
    def _game(self):
        game = create_game()
        p1, p2 = game.players
        return game, p1, p2

    def _creature(self, owner, name="Bear"):
        card = Creature(name=name, base_power=2, base_toughness=2, owner=owner)
        card.controller = owner
        return card

    def _cast_scatter_at(self, game, p1, occurrence):
        """Cast Essence Scatter through the real pipeline, selecting
        *occurrence* by its engine-minted stack instance id."""
        scatter = EssenceScatter(owner=p1, controller=p1)
        game.get_hand(p1).add(scatter)
        occ_iid = game.refs.instance_id(occurrence, Zone.STACK.value)
        p1.start_intent("scatter-cast", Intent(
            pattern=GameRef(card=frozenset({("name", "Essence Scatter")})),
            preferences=(Decision.obj(instance=occ_iid),),
        ))
        try:
            scatter_so = cast_spell_free(game, p1, scatter, Zone.HAND)
        finally:
            p1.end_intent("scatter-cast")
        assert scatter_so.targets[0] is occurrence
        return scatter, scatter_so

    def test_countered_creature_spell_to_owner_graveyard(self) -> None:
        game, p1, p2 = self._game()
        creature = self._creature(p2)
        game.get_hand(p2).add(creature)
        so = cast_spell_free(game, p2, creature, Zone.HAND)

        scatter, _ = self._cast_scatter_at(game, p1, so)
        resolve_top_of_stack(game)

        # Destination ownership: countered card to ITS owner's (p2's)
        # graveyard, never the battlefield; Scatter to p1's graveyard.
        assert game.get_graveyard(p2).contains(creature)
        assert not game.get_battlefield(p2).contains(creature)
        assert not game.get_graveyard(p1).contains(creature)
        assert game.get_graveyard(p1).contains(scatter)
        assert game.stack.is_empty()

    def test_noncreature_spell_is_not_targetable(self) -> None:
        """Only creature spells qualify: with just an instant on the stack,
        Essence Scatter has no legal target and cannot be cast."""
        game, p1, p2 = self._game()
        zap = Instant(name="Zap", mana_cost=ManaCost.parse("{U}"), owner=p2)
        zap.controller = p2
        game.get_hand(p2).add(zap)
        cast_spell_free(game, p2, zap, Zone.HAND)

        scatter = EssenceScatter(owner=p1, controller=p1)
        game.get_hand(p1).add(scatter)
        assert scatter.can_cast(game) is False
        with pytest.raises(CastingError):
            cast_spell_free(game, p1, scatter, Zone.HAND)
        assert game.get_hand(p1).contains(scatter)  # rolled back

    def test_trigger_sourced_by_creature_is_not_a_creature_spell(self) -> None:
        """The occurrence invariant: a triggered ability whose SOURCE is a
        creature card (e.g. a battlefield creature's own ETB trigger) is not a
        creature spell — Essence Scatter must not see it as a target."""
        game, p1, p2 = self._game()
        watcher = self._creature(p2, name="Watcher")
        game.get_battlefield(p2).add(watcher)
        trigger = StackObject(source=watcher, controller=p2)  # is_spell=False
        game.stack.push(trigger)

        scatter = EssenceScatter(owner=p1, controller=p1)
        game.get_hand(p1).add(scatter)
        assert scatter.can_cast(game) is False
        with pytest.raises(CastingError):
            cast_spell_free(game, p1, scatter, Zone.HAND)
        assert game.stack.contains(trigger)  # untouched

    def test_counter_fizzles_when_occurrence_departed_and_recast(self) -> None:
        """The targeted occurrence left the stack: Essence Scatter fizzles at
        resolution and never touches the re-cast occurrence of the same card."""
        game, p1, p2 = self._game()
        creature = self._creature(p2)
        game.get_hand(p2).add(creature)
        so = cast_spell_free(game, p2, creature, Zone.HAND)

        scatter, _ = self._cast_scatter_at(game, p1, so)

        assert move_spell_off_stack(game, so) is True  # departs (other counter)
        assert game.get_graveyard(p2).contains(creature)
        recast_so = cast_spell_free(game, p2, creature, Zone.GRAVEYARD)
        assert recast_so is not so

        resolve_top_of_stack(game)  # the recast resolves — creature enters
        assert game.get_battlefield(p2).contains(creature)

        resolve_top_of_stack(game)  # Scatter resolves — and fizzles
        assert game.get_battlefield(p2).contains(creature)  # untouched
        assert not game.get_graveyard(p2).contains(creature)
        assert game.get_graveyard(p1).contains(scatter)
        assert game.stack.is_empty()

    def test_copy_countered_distinctly_from_original(self) -> None:
        """A creature-spell COPY is its own occurrence: countering it leaves
        the original cast untouched and moves no card."""
        game, p1, p2 = self._game()
        creature = self._creature(p2)
        game.get_hand(p2).add(creature)
        so = cast_spell_free(game, p2, creature, Zone.HAND)
        copy_so = copy_spell(game, so, p2)
        game.stack.push(copy_so)

        _, scatter_so = self._cast_scatter_at(game, p1, copy_so)
        assert scatter_so.targets[0] is copy_so
        resolve_top_of_stack(game)

        assert not game.stack.contains(copy_so)
        assert game.stack.contains(so)  # original untouched
        assert p2.zones[Zone.STACK].contains(creature)
        assert not game.get_graveyard(p2).contains(creature)
