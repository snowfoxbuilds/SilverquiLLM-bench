"""Regression tests for FDN 48 — Refute.

Refute counters a target spell through the engine's shared stack-departure
primitive (:func:`engine.stack.move_spell_off_stack`), which is what makes
the countered spell's disposition uniform with resolution: an ordinary
countered spell goes to its owner's graveyard (rule 701.5a), while a spell
cast via flashback is exiled instead — rule 702.34a exiles a flashbacked
spell any time it would leave the stack, countering included. A target that
already left the stack is not moved again (fizzle).
"""

from __future__ import annotations

from cards.fdn.fdn_48.card_impl import Refute
from engine.card import Creature, Instant
from engine.casting import CastMode, cast_spell_free
from engine.decisions import GameRef
from engine.intent_player import Intent
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

    def _refute(self, game, p1, target_stack_obj):
        """Drive Refute's resolution against *target_stack_obj*. An Intent
        scoped to Refute answers its discard query (first option)."""
        refute = Refute(owner=p1, controller=p1)
        refute.chosen_targets = [target_stack_obj]
        p1.start_intent("refute", Intent(
            pattern=GameRef(card=frozenset({("name", "Refute")})),
            preferences=(),
        ))
        try:
            refute.on_resolve(game)
        finally:
            p1.end_intent("refute")
        return refute

    def test_ordinary_countered_spell_to_owner_graveyard(self) -> None:
        game, p1, p2 = self._game()
        spell = self._spell(p2)
        game.get_hand(p2).add(spell)
        cast_spell_free(game, p2, spell, Zone.HAND)
        (so,) = [s for s in game.stack._items if s.source is spell]

        self._refute(game, p1, so)

        assert game.get_graveyard(p2).contains(spell)
        assert not game.get_exile(p2).contains(spell)
        assert not any(item is so for item in game.stack._items)

    def test_flashback_countered_spell_exiled(self) -> None:
        """Countering a flashbacked spell exiles it (rule 702.34a) — the
        departure replacement applies to countering exactly as to resolution."""
        game, p1, p2 = self._game()
        spell = self._spell(p2, flashback=True)
        game.get_graveyard(p2).add(spell)
        cast_spell_free(game, p2, spell, Zone.GRAVEYARD, mode=CastMode.FLASHBACK)
        (so,) = [s for s in game.stack._items if s.source is spell]

        self._refute(game, p1, so)

        assert game.get_exile(p2).contains(spell)
        assert not game.get_graveyard(p2).contains(spell)

    def test_counter_fizzles_when_target_already_departed(self) -> None:
        """A target StackObject that already left the stack is not processed:
        the card is not moved again."""
        from engine.stack import resolve_top_of_stack

        game, p1, p2 = self._game()
        spell = self._spell(p2)
        game.get_hand(p2).add(spell)
        cast_spell_free(game, p2, spell, Zone.HAND)
        (so,) = [s for s in game.stack._items if s.source is spell]
        resolve_top_of_stack(game)
        assert game.get_graveyard(p2).contains(spell)

        self._refute(game, p1, so)

        assert sum(1 for o in game.get_graveyard(p2).get_all() if o is spell) == 1
        assert not game.get_exile(p2).contains(spell)

    def test_refute_still_draws_after_counter(self) -> None:
        game, p1, p2 = self._game()
        spell = self._spell(p2)
        game.get_hand(p2).add(spell)
        cast_spell_free(game, p2, spell, Zone.HAND)
        (so,) = [s for s in game.stack._items if s.source is spell]
        hand_before = len(game.get_hand(p1))

        self._refute(game, p1, so)

        # Draw a card, then discard a card: net hand size unchanged, but the
        # library card moved through the hand.
        assert len(game.get_library(p1)) == 0
        assert len(game.get_hand(p1)) == hand_before  # +1 draw, -1 discard
