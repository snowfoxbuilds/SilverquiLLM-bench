"""Regression tests for FDN 160 — An Offer You Can't Refuse.

An Offer You Can't Refuse is cast through the REAL pipeline: its Zone.STACK
target requirement offers exact StackObject occurrences (noncreature spells
only — an ability sharing a source card is not a spell), the counter routes
through :func:`engine.stack.move_spell_off_stack` (owner's graveyard for an
ordinary spell, exile for a flashbacked one, rule 702.34a), and the Treasure
consolation is created for the countered spell's controller exactly when the
counter succeeds — a fizzled cast (target occurrence departed) creates
nothing.
"""

from __future__ import annotations

import pytest
from cards.fdn.fdn_160.card_impl import AnOfferYouCantRefuse
from engine.card import Creature, Instant
from engine.casting import CastingError, CastMode, cast_spell_free
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.stack import move_spell_off_stack, resolve_top_of_stack
from engine.types import ManaCost, Zone
from test_utils import create_game


def _treasures(game, player):
    return [
        o
        for o in game.get_battlefield(player).get_all()
        if getattr(o, "name", "") == "Treasure"
    ]


class TestAnOfferProperties:
    def test_is_instant(self) -> None:
        assert isinstance(AnOfferYouCantRefuse(owner=None), Instant)

    def test_mana_cost(self) -> None:
        assert AnOfferYouCantRefuse(owner=None).mana_cost == ManaCost.parse("{U}")


class TestAnOfferCounters:
    def _game(self):
        game = create_game()
        p1, p2 = game.players
        return game, p1, p2

    def _spell(self, owner, *, flashback: bool = False):
        card = Instant(name="Zap", mana_cost=ManaCost.parse("{U}"), owner=owner)
        card.controller = owner
        if flashback:
            card.flashback_cost = ManaCost.parse("{2}{U}")
        return card

    def _cast_offer_at(self, game, p1, occurrence):
        """Cast An Offer through the real pipeline, selecting *occurrence* by
        its engine-minted stack instance id."""
        offer = AnOfferYouCantRefuse(owner=p1, controller=p1)
        game.get_hand(p1).add(offer)
        occ_iid = game.refs.instance_id(occurrence, Zone.STACK.value)
        p1.start_intent("offer-cast", Intent(
            pattern=GameRef(card=frozenset({("name", "An Offer You Can't Refuse")})),
            preferences=(Decision.obj(instance=occ_iid),),
        ))
        try:
            offer_so = cast_spell_free(game, p1, offer, Zone.HAND)
        finally:
            p1.end_intent("offer-cast")
        assert offer_so.targets[0] is occurrence
        return offer, offer_so

    def test_countered_spell_to_owner_graveyard_with_treasures(self) -> None:
        game, p1, p2 = self._game()
        spell = self._spell(p2)
        game.get_hand(p2).add(spell)
        so = cast_spell_free(game, p2, spell, Zone.HAND)

        offer, _ = self._cast_offer_at(game, p1, so)
        resolve_top_of_stack(game)

        # Destination ownership: countered card to ITS owner's (p2's)
        # graveyard; An Offer to p1's graveyard.
        assert game.get_graveyard(p2).contains(spell)
        assert not game.get_exile(p2).contains(spell)
        assert game.get_graveyard(p1).contains(offer)
        # Consolation: the countered spell's CONTROLLER gets the Treasures.
        assert len(_treasures(game, p2)) == 2
        assert len(_treasures(game, p1)) == 0
        assert game.stack.is_empty()

    def test_flashback_countered_spell_exiled_with_treasures(self) -> None:
        """Countering a flashbacked spell exiles it (rule 702.34a); the
        Treasure consolation still applies — the counter succeeded."""
        game, p1, p2 = self._game()
        spell = self._spell(p2, flashback=True)
        game.get_graveyard(p2).add(spell)
        so = cast_spell_free(game, p2, spell, Zone.GRAVEYARD, mode=CastMode.FLASHBACK)

        self._cast_offer_at(game, p1, so)
        resolve_top_of_stack(game)

        assert game.get_exile(p2).contains(spell)
        assert not game.get_graveyard(p2).contains(spell)
        assert len(_treasures(game, p2)) == 2

    def test_creature_spell_is_not_targetable(self) -> None:
        """Only noncreature spells qualify: with just a creature spell on the
        stack, An Offer has no legal target and cannot be cast."""
        game, p1, p2 = self._game()
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2)
        creature.controller = p2
        game.get_hand(p2).add(creature)
        cast_spell_free(game, p2, creature, Zone.HAND)

        offer = AnOfferYouCantRefuse(owner=p1, controller=p1)
        game.get_hand(p1).add(offer)
        assert offer.can_cast(game) is False
        with pytest.raises(CastingError):
            cast_spell_free(game, p1, offer, Zone.HAND)
        assert game.get_hand(p1).contains(offer)  # rolled back

    def test_counter_fizzles_when_occurrence_departed_no_treasures(self) -> None:
        """Rule 608.2b: the targeted occurrence left the stack, so An Offer
        fizzles entirely — no counter, no Treasures, and never a move of the
        re-cast occurrence's card."""
        game, p1, p2 = self._game()
        spell = self._spell(p2)
        game.get_hand(p2).add(spell)
        so = cast_spell_free(game, p2, spell, Zone.HAND)

        offer, _ = self._cast_offer_at(game, p1, so)

        assert move_spell_off_stack(game, so) is True  # departs (other counter)
        recast_so = cast_spell_free(game, p2, spell, Zone.GRAVEYARD)
        assert recast_so is not so

        resolve_top_of_stack(game)  # the recast resolves normally
        assert game.get_graveyard(p2).contains(spell)

        resolve_top_of_stack(game)  # An Offer resolves — and fizzles
        assert sum(1 for o in game.get_graveyard(p2).get_all() if o is spell) == 1
        assert not game.get_exile(p2).contains(spell)
        assert len(_treasures(game, p2)) == 0  # no consolation on a fizzle
        assert game.get_graveyard(p1).contains(offer)
        assert game.stack.is_empty()
