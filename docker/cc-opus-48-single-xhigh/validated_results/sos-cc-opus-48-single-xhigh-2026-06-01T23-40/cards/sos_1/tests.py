"""Tests for SOS 1 — The Dawning Archaic.

The Dawning Archaic — {10} — Legendary Creature — Avatar — 7/7.

Oracle text:
- "This spell costs {1} less to cast for each instant and sorcery card in
  your graveyard."  (cost reduction)
- "Reach"  (keyword)
- "Whenever The Dawning Archaic attacks, you may cast target instant or
  sorcery card from your graveyard without paying its mana cost. If that
  spell would be put into your graveyard, exile it instead."
  (attack trigger + free cast from graveyard + replacement to exile)

These tests are written before the implementation (TDD red phase) and define
the contract the implementation must satisfy. The mechanics mirror the
reference card Etali, Primal Storm (FDN 194) for the attack-trigger /
free-cast pattern, and the engine cost-reduction hook (CardImpl.cost_reduction).
"""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell, get_cost_reduction
from engine.events import AttacksTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bolt(name: str = "Lightning Bolt") -> Instant:
    """A cheap instant for graveyard fodder / free-cast targets."""
    return Instant(name=name, mana_cost=ManaCost.parse("{R}"))


def _divination(name: str = "Divination") -> Sorcery:
    """A cheap sorcery for graveyard fodder / free-cast targets."""
    return Sorcery(name=name, mana_cost=ManaCost.parse("{2}{U}"))


def _bear(name: str = "Grizzly Bears") -> Creature:
    """A vanilla creature used as a non-instant/sorcery graveyard occupant."""
    return Creature(name=name, mana_cost=ManaCost.parse("{1}{G}"),
                    base_power=2, base_toughness=2)


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_is_creature(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_power_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7
        assert card.base_toughness == 7

    def test_legendary(self) -> None:
        assert Supertype.LEGENDARY in TheDawningArchaic(owner=None).supertypes

    def test_avatar_subtype(self) -> None:
        assert "Avatar" in TheDawningArchaic(owner=None).subtypes

    def test_has_reach(self) -> None:
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords

    def test_is_colorless(self) -> None:
        """A {10} cost has no colored pips — the card is colorless."""
        cost = TheDawningArchaic(owner=None).mana_cost
        colored = {mt: n for mt, n in cost.pips.items() if mt != ManaType.COLORLESS}
        assert colored == {}
        assert cost.hybrid == []


# ---------------------------------------------------------------------------
# Cost reduction: {1} less for each instant/sorcery in your graveyard
# ---------------------------------------------------------------------------

class TestTheDawningArchaicCostReduction:
    """cost_reduction counts instant + sorcery cards in the controller's
    graveyard. The engine clamps the reduction to the generic portion of the
    mana cost (here, the whole {10})."""

    def test_no_reduction_with_empty_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_instant_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, graveyard=[_bolt()])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 1

    def test_one_sorcery_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, graveyard=[_divination()])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 1

    def test_mixed_instants_and_sorceries_sum(self) -> None:
        """Three instants + two sorceries → reduction of 5."""
        game = create_game()
        p1 = game.players[0]
        set_board_state(
            game, 0,
            graveyard=[_bolt("Bolt1"), _bolt("Bolt2"), _bolt("Bolt3"),
                       _divination("Div1"), _divination("Div2")],
        )
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 5

    def test_creatures_in_graveyard_do_not_reduce(self) -> None:
        """Only instant/sorcery cards count — creatures are ignored."""
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, graveyard=[_bear("B1"), _bear("B2")])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_only_instant_sorcery_among_mixed_graveyard_count(self) -> None:
        """A graveyard with 1 instant + 1 sorcery + 2 creatures → reduction 2."""
        game = create_game()
        p1 = game.players[0]
        set_board_state(
            game, 0,
            graveyard=[_bolt(), _divination(), _bear("B1"), _bear("B2")],
        )
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 2

    def test_opponent_graveyard_does_not_reduce(self) -> None:
        """Only *your* graveyard counts, not the opponent's."""
        game = create_game()
        p1 = game.players[0]
        # Opponent (player 1) has instants/sorceries; controller's is empty.
        set_board_state(game, 1, graveyard=[_bolt(), _divination(), _bolt("B2")])
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_engine_clamps_reduction_to_generic(self) -> None:
        """get_cost_reduction clamps the value to the generic portion (10).
        With more than 10 spells, the reduction is capped at 10."""
        game = create_game()
        p1 = game.players[0]
        gy = [_bolt(f"Bolt{i}") for i in range(12)]
        set_board_state(game, 0, graveyard=gy)
        card = TheDawningArchaic(owner=p1, controller=p1)
        assert get_cost_reduction(game, card, p1) == 10

    def test_cast_with_reduction_succeeds_with_reduced_mana(self) -> None:
        """{10} with 4 instant/sorcery in graveyard → effective {6}.
        Six colorless mana should be exactly enough to cast it."""
        game = create_game()
        p1 = game.players[0]
        set_board_state(
            game, 0,
            graveyard=[_bolt("B1"), _bolt("B2"), _divination("D1"), _divination("D2")],
        )
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card], mana={ManaType.COLORLESS: 6})
        # Sorcery-speed timing for the engine cast_spell: active player,
        # main phase, empty stack.
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        cast_spell(game, p1, card)
        # Spell goes on the stack; resolve it so the creature lands.
        spell_obj = game.stack.pop()
        spell_obj.on_resolve(game)
        assert game.get_battlefield(p1).contains(card)

    def test_cast_without_enough_reduction_fails(self) -> None:
        """With an empty graveyard the full {10} is required; 6 mana is too few.

        The failure must be due to *mana*, not timing or another incidental
        legality issue — otherwise a cost-reduction bug could slip through.
        """
        from engine.casting import CastingError

        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        # Empty graveyard, only 6 mana.
        set_board_state(game, 0, hand=[card], graveyard=[], mana={ManaType.COLORLESS: 6})
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell(game, p1, card)


# ---------------------------------------------------------------------------
# Attack trigger registration
# ---------------------------------------------------------------------------

class TestTheDawningArchaicTriggerRegistration:
    """register_triggers must wire an AttacksTriggeredEvent trigger keyed to
    this creature."""

    def test_registers_an_attacks_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers_for_source(card))
        card.register_triggers(game)
        after = game.trigger_manager.get_triggers_for_source(card)
        assert len(after) - before == 1
        assert after[0].event_type is AttacksTriggeredEvent

    def test_trigger_condition_matches_this_creature(self) -> None:
        """The trigger fires only when THIS creature attacks, not another."""
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        card.register_triggers(game)
        reg = game.trigger_manager.get_triggers_for_source(card)[0]
        # Condition should be present and reject an unrelated attacker.
        assert reg.condition is not None
        other = _bear("Some Other Attacker")
        assert reg.condition(game, AttacksTriggeredEvent(creature=other, attacker=other)) is False
        assert reg.condition(game, AttacksTriggeredEvent(creature=card, attacker=card)) is True


# ---------------------------------------------------------------------------
# Attack trigger effect: free-cast an instant/sorcery from your graveyard
# ---------------------------------------------------------------------------

class TestTheDawningArchaicAttackEffect:
    """The attack trigger lets you cast a chosen instant/sorcery from your
    graveyard without paying its mana cost. The chosen card goes onto the
    stack (free cast) and is removed from the graveyard."""

    def _fire_attack_trigger(self, game, card, *, yes=True, chosen=None):
        """Register the trigger, fire AttacksTriggeredEvent, and resolve the
        single pushed StackObject. Scripts the controller's choices.

        Returns nothing; the test inspects game state afterwards.
        """
        controller = card.controller
        # The effect will ask whether to cast and which target to choose.
        # We seed the deterministic player's script with those answers.
        script_answers = []
        if chosen is not None:
            script_answers.append(yes)        # choose_yes_no — cast it?
            script_answers.append(chosen)     # choose_target / choose_card
        else:
            script_answers.append(yes)
        for ans in reversed(script_answers):
            controller._script.appendleft(ans)

        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=card, attacker=card)
        )
        # Resolve the attack trigger StackObject (the "may cast" effect).
        assert not game.stack.is_empty(), "attack trigger should push a StackObject"
        trig = game.stack.pop()
        trig.on_resolve(game)

    def test_chosen_instant_leaves_graveyard_onto_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bolt = _bolt()
        set_board_state(game, 0, graveyard=[bolt])
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        self._fire_attack_trigger(game, card, yes=True, chosen=bolt)

        # After the trigger resolves, the bolt should no longer be in the
        # graveyard — it has been put onto the stack as a free cast.
        assert not game.get_graveyard(p1).contains(bolt)
        # The free-cast spell is now on the stack.
        on_stack = [obj.source for obj in game.stack.objects()]
        assert bolt in on_stack

    def test_free_cast_does_not_spend_mana(self) -> None:
        """Casting from the graveyard via the trigger requires no mana —
        the controller's (empty) mana pool is untouched."""
        game = create_game()
        p1 = game.players[0]
        bolt = _bolt()
        set_board_state(game, 0, graveyard=[bolt], mana={})
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        self._fire_attack_trigger(game, card, yes=True, chosen=bolt)

        # No mana of any type was paid.
        total = sum(p1.mana_pool.get(mt) for mt in ManaType)
        assert total == 0
        on_stack = [obj.source for obj in game.stack.objects()]
        assert bolt in on_stack

    def test_chosen_sorcery_can_be_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]
        div = _divination()
        set_board_state(game, 0, graveyard=[div])
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        self._fire_attack_trigger(game, card, yes=True, chosen=div)

        assert not game.get_graveyard(p1).contains(div)
        on_stack = [obj.source for obj in game.stack.objects()]
        assert div in on_stack

    def test_may_declining_leaves_graveyard_untouched(self) -> None:
        """The ability is optional ("you may"). Declining leaves the
        graveyard unchanged and nothing extra on the stack."""
        game = create_game()
        p1 = game.players[0]
        bolt = _bolt()
        set_board_state(game, 0, graveyard=[bolt])
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        self._fire_attack_trigger(game, card, yes=False, chosen=None)

        # Declined: the instant stays in the graveyard.
        assert game.get_graveyard(p1).contains(bolt)
        # Nothing new on the stack (the trigger itself was already resolved).
        assert game.stack.is_empty()

    def test_empty_graveyard_is_a_safe_noop(self) -> None:
        """With no instant/sorcery in the graveyard the trigger resolves
        without error and casts nothing."""
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, graveyard=[])
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        controller = p1
        # Even if the engine asks "may cast?", a yes with no legal target
        # must not raise; seed a yes to be safe.
        controller._script.appendleft(True)
        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=card, attacker=card)
        )
        assert not game.stack.is_empty()
        trig = game.stack.pop()
        # Should resolve cleanly with nothing to cast.
        trig.on_resolve(game)
        assert game.stack.is_empty()


# ---------------------------------------------------------------------------
# Replacement: free-cast spell is exiled instead of going to the graveyard
# ---------------------------------------------------------------------------

class TestTheDawningArchaicExileReplacement:
    """"If that spell would be put into your graveyard, exile it instead."
    After the free-cast spell resolves, it should end up in exile, not the
    graveyard."""

    def _free_cast_and_resolve(self, game, card, spell):
        """Fire the attack trigger choosing *spell*, then resolve the
        free-cast spell that lands on the stack."""
        controller = card.controller
        controller._script.appendleft(spell)   # target/card choice
        controller._script.appendleft(True)     # choose_yes_no — cast it?

        card.register_triggers(game)
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=card, attacker=card)
        )
        # Resolve the trigger (the "may cast" effect) → spell goes on stack.
        trig = game.stack.pop()
        trig.on_resolve(game)
        # Now resolve the free-cast spell itself.
        assert not game.stack.is_empty(), "free-cast spell should be on the stack"
        spell_obj = game.stack.pop()
        spell_obj.on_resolve(game)

    def test_resolved_free_cast_instant_goes_to_exile(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bolt = _bolt()
        set_board_state(game, 0, graveyard=[bolt])
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        self._free_cast_and_resolve(game, card, bolt)

        # The spell should be exiled, NOT returned to the graveyard.
        assert game.get_exile(p1).contains(bolt)
        assert not game.get_graveyard(p1).contains(bolt)

    def test_resolved_free_cast_sorcery_goes_to_exile(self) -> None:
        game = create_game()
        p1 = game.players[0]
        div = _divination()
        set_board_state(game, 0, graveyard=[div])
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        self._free_cast_and_resolve(game, card, div)

        assert game.get_exile(p1).contains(div)
        assert not game.get_graveyard(p1).contains(div)
