"""Tests for SOS 57 — Mana Sculpt.

Mana Sculpt — {1}{U}{U} Instant:

    Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase.

Contract derived from the oracle text and the engine's counter plumbing
(see ``cards/fdn/fdn_48`` / ``cards/fdn/fdn_153`` for the established
``_counter_spell`` pattern, plus ``engine/stack.py``,
``engine/triggers.py`` and ``engine/mana.py``):

* **Static data** — name ``"Mana Sculpt"``, mana cost ``{1}{U}{U}``, an
  instant.
* **Counter half** — the spell targets another spell on the stack and, on
  resolution, removes that spell's :class:`StackObject` from the stack and
  puts the countered card into its owner's graveyard.  A counter with no
  legal target (it left the stack) does nothing.
* **Wizard condition** — the deferred mana clause only applies if the
  controller of Mana Sculpt controls a Wizard *as the counter resolves*.
  With no Wizard, only the counter happens.
* **Deferred {C}** — when the controller does control a Wizard, a delayed
  effect is set up that, at the beginning of the controller's next main
  phase, adds an amount of ``{C}`` (colorless mana) to the controller's
  pool equal to the amount of mana spent to cast the countered spell.
  For a normally-cast spell with no X / cost reduction this is the
  countered spell's mana value.

The counter behaviour is asserted by driving ``on_resolve`` directly after
seeding ``chosen_targets`` (the established per-card test convention used by
the FDN reference counter cards).  The deferred-mana behaviour is asserted
through the public trigger system: a Wizard-conditional counter must
register a (delayed) trigger, and firing that trigger's effect must add the
correct amount of ``{C}`` to the controller's pool.
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wizard(owner: Any = None) -> Creature:
    """A 2/2 creature with the Wizard subtype."""
    return Creature(
        name="Test Wizard",
        owner=owner,
        controller=owner,
        subtypes={"Human", "Wizard"},
        base_power=2,
        base_toughness=2,
    )


def _non_wizard(owner: Any = None) -> Creature:
    """A 2/2 creature without the Wizard subtype."""
    return Creature(
        name="Grizzly Bears",
        owner=owner,
        controller=owner,
        subtypes={"Bear"},
        base_power=2,
        base_toughness=2,
    )


def _make_spell_on_stack(
    game: Any,
    caster: Any,
    *,
    mana_cost: str = "{2}{R}",
    name: str = "Lightning Spell",
    creature: bool = False,
) -> StackObject:
    """Put a dummy spell on the stack controlled by *caster*.

    Mirrors the real cast pipeline's bookkeeping enough for a counter to
    act on it: the source card lives in the caster's stack zone and a
    :class:`StackObject` referencing it sits on the game stack.
    """
    if creature:
        spell = Creature(
            name=name,
            owner=caster,
            controller=caster,
            mana_cost=ManaCost.parse(mana_cost),
            base_power=1,
            base_toughness=1,
        )
    else:
        spell = Sorcery(
            name=name,
            owner=caster,
            controller=caster,
            mana_cost=ManaCost.parse(mana_cost),
        )
    caster.zones[Zone.STACK].add(spell)
    stack_obj = StackObject(
        source=spell,
        controller=caster,
        targets=[],
        on_resolve=lambda _g: None,
    )
    game.stack.push(stack_obj)
    return stack_obj


def _fire_main_phase_begin(game: Any, player: Any, *, precombat: bool = True) -> None:
    """Fire ``BeginningOfMainPhaseTriggeredEvent`` for *player* and resolve.

    Drives the engine exactly as ``engine/turn.py`` ``run_turn`` does at the
    start of a main phase: the event is fired via
    :meth:`TriggerManager.fire_event`, which pushes any matching delayed
    trigger's effect onto the stack as a :class:`StackObject`.  The stack is
    then resolved (LIFO) so the deferred effect actually runs — mirroring the
    real ``priority_loop`` resolution that follows the fired event.

    APNAP ordering in ``fire_event`` keys off ``game.active_player``; we set
    the active player to *player* so a trigger they control is pushed normally.
    """
    game.active_player_index = game.players.index(player)
    game.trigger_manager.fire_event(
        game,
        BeginningOfMainPhaseTriggeredEvent(player=player, precombat=precombat),
    )
    # Resolve everything the fired event pushed onto the stack.
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_is_instant(self) -> None:
        card = ManaSculpt(owner=None)
        assert isinstance(card, Instant)
        assert CardType.INSTANT in card.card_types

    def test_not_a_creature(self) -> None:
        card = ManaSculpt(owner=None)
        assert CardType.CREATURE not in card.card_types


# ---------------------------------------------------------------------------
# Targeting / castability — needs a spell on the stack
# ---------------------------------------------------------------------------


class TestManaSculptTargeting:
    """Mana Sculpt targets a spell on the stack."""

    def test_cannot_cast_with_empty_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ManaSculpt(owner=p1, controller=p1)
        assert card.can_cast(game) is False

    def test_can_cast_when_a_spell_is_on_the_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _make_spell_on_stack(game, p2)
        card = ManaSculpt(owner=p1, controller=p1)
        assert card.can_cast(game) is True

    def test_get_targets_offers_the_spell_on_the_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = _make_spell_on_stack(game, p2)
        card = ManaSculpt(owner=p1, controller=p1)
        reqs = card.get_targets(game)
        assert len(reqs) == 1
        # The requirement's filter must accept the spell's StackObject and
        # reject Mana Sculpt itself.
        req = reqs[0]
        assert req.zone == Zone.STACK
        assert req.filter_fn(target) is True

    def test_get_targets_rejects_self(self) -> None:
        """Mana Sculpt must not be able to target its own stack object."""
        game = create_game()
        p1, p2 = game.players
        _make_spell_on_stack(game, p2)
        card = ManaSculpt(owner=p1, controller=p1)
        own_obj = StackObject(source=card, controller=p1, targets=[])
        req = card.get_targets(game)[0]
        assert req.filter_fn(own_obj) is False


# ---------------------------------------------------------------------------
# Counter half
# ---------------------------------------------------------------------------


class TestManaSculptCounter:
    """The counter removes the target spell from the stack."""

    def test_counter_removes_spell_from_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = _make_spell_on_stack(game, p2, name="Doomed Spell")

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target]
        # Sanity: the targeted spell is on the stack before resolution.
        assert target in game.stack.objects()

        card.on_resolve(game)

        assert target not in game.stack.objects()

    def test_countered_spell_goes_to_owners_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = _make_spell_on_stack(game, p2, name="Doomed Spell")
        spell_card = target.source

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)

        # The countered card is owned by p2; it ends up in p2's graveyard.
        assert game.get_graveyard(p2).contains(spell_card)
        # And it is no longer in the stack zone.
        assert not p2.zones[Zone.STACK].contains(spell_card)

    def test_counters_creature_spell_too(self) -> None:
        """"Counter target spell" is not limited to noncreature spells."""
        game = create_game()
        p1, p2 = game.players
        target = _make_spell_on_stack(game, p2, name="Big Beast", creature=True)
        spell_card = target.source

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)

        assert target not in game.stack.objects()
        assert game.get_graveyard(p2).contains(spell_card)

    def test_no_target_is_a_noop(self) -> None:
        """If there is no legal target, resolution does nothing (fizzles)."""
        game = create_game()
        p1, p2 = game.players
        # A bystander spell that must remain on the stack untouched.
        bystander = _make_spell_on_stack(game, p2, name="Bystander")

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [None]
        card.on_resolve(game)

        assert bystander in game.stack.objects()
        assert not game.get_graveyard(p2).contains(bystander.source)


# ---------------------------------------------------------------------------
# Wizard condition + deferred {C}
# ---------------------------------------------------------------------------


class TestManaSculptWizardCondition:
    """The deferred-mana clause only applies if you control a Wizard."""

    def test_no_wizard_registers_no_delayed_trigger(self) -> None:
        game = create_game()
        p1, p2 = game.players
        # Controller has a non-Wizard creature only.
        set_board_state(game, 0, battlefield=[_non_wizard(p1)])
        target = _make_spell_on_stack(game, p2, mana_cost="{2}{R}")

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target]

        before = len(game.trigger_manager.get_triggers())
        card.on_resolve(game)
        after = len(game.trigger_manager.get_triggers())

        # The spell is still countered, but no deferred-mana trigger exists.
        assert target not in game.stack.objects()
        assert after == before

    def test_no_wizard_adds_no_mana_now_or_via_pool(self) -> None:
        """Without a Wizard, the controller's pool gains no colorless mana."""
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_non_wizard(p1)],
                        mana={ManaType.COLORLESS: 0})
        target = _make_spell_on_stack(game, p2, mana_cost="{2}{R}")

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_wizard_registers_a_delayed_trigger(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard(p1)])
        target = _make_spell_on_stack(game, p2, mana_cost="{2}{R}")  # mv 3

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target]

        before = len(game.trigger_manager.get_triggers())
        card.on_resolve(game)
        after = len(game.trigger_manager.get_triggers())

        # Counter happened, and a deferred-mana trigger was registered for
        # the controller's next main phase.
        assert target not in game.stack.objects()
        assert after == before + 1

    def test_delayed_trigger_is_controlled_by_caster(self) -> None:
        """The deferred mana belongs to Mana Sculpt's controller ("you")."""
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard(p1)])
        target = _make_spell_on_stack(game, p2, mana_cost="{2}{R}")

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)

        new_triggers = [
            t for t in game.trigger_manager.get_triggers()
            if t.controller is p1
        ]
        assert len(new_triggers) == 1

    def test_delayed_trigger_effect_adds_colorless_equal_to_mana_spent(self) -> None:
        """Firing the registered effect adds {C} equal to the spell's cost.

        The countered spell costs {2}{R} (mana value 3, no X / reductions),
        so the controller gains exactly 3 colorless mana.
        """
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard(p1)],
                        mana={ManaType.COLORLESS: 0})
        target = _make_spell_on_stack(game, p2, mana_cost="{2}{R}")  # mv 3

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)

        new_triggers = [
            t for t in game.trigger_manager.get_triggers()
            if t.controller is p1
        ]
        assert len(new_triggers) == 1
        # Execute the deferred effect (as the engine would when the trigger
        # resolves at the controller's next main phase).
        new_triggers[0].effect(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_deferred_amount_scales_with_a_more_expensive_spell(self) -> None:
        """{C} added equals the amount of mana spent — a 5-mana spell → 5 {C}."""
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard(p1)],
                        mana={ManaType.COLORLESS: 0})
        target = _make_spell_on_stack(game, p2, mana_cost="{3}{U}{U}")  # mv 5

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)

        new_triggers = [
            t for t in game.trigger_manager.get_triggers()
            if t.controller is p1
        ]
        assert len(new_triggers) == 1
        new_triggers[0].effect(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 5

    def test_deferred_mana_is_colorless_not_colored(self) -> None:
        """The deferred mana is {C}; it must not add colored mana."""
        game = create_game()
        p1, p2 = game.players
        set_board_state(
            game, 0, battlefield=[_wizard(p1)],
            mana={
                ManaType.COLORLESS: 0,
                ManaType.BLUE: 0,
                ManaType.RED: 0,
            },
        )
        target = _make_spell_on_stack(game, p2, mana_cost="{2}{R}")  # mv 3

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)

        new_triggers = [
            t for t in game.trigger_manager.get_triggers()
            if t.controller is p1
        ]
        assert len(new_triggers) == 1
        new_triggers[0].effect(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 3
        # No colored mana was added by the colorless clause.
        assert p1.mana_pool.get(ManaType.BLUE) == 0
        assert p1.mana_pool.get(ManaType.RED) == 0

    def test_opponents_wizard_does_not_enable_the_clause(self) -> None:
        """"If *you* control a Wizard" — an opponent's Wizard does not count."""
        game = create_game()
        p1, p2 = game.players
        # Only the opponent (p2) controls a Wizard.
        set_board_state(game, 0, battlefield=[_non_wizard(p1)])
        set_board_state(game, 1, battlefield=[_wizard(p2)])
        target = _make_spell_on_stack(game, p2, mana_cost="{2}{R}")

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target]

        before = len(game.trigger_manager.get_triggers())
        card.on_resolve(game)
        after = len(game.trigger_manager.get_triggers())

        assert target not in game.stack.objects()
        # No deferred-mana trigger because the controller has no Wizard.
        assert after == before


# ---------------------------------------------------------------------------
# End-to-end timing: the {C} arrives at the controller's next main phase
# ---------------------------------------------------------------------------


class TestManaSculptDeliveryTiming:
    """The deferred {C} is delivered to the pool at the next main phase.

    This drives the registered delayed trigger and asserts the colorless
    mana lands in the controller's pool — the observable end state of the
    "add ... at the beginning of your next main phase" clause.
    """

    def test_mana_lands_in_pool_after_firing_delayed_trigger(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard(p1)],
                        mana={ManaType.COLORLESS: 0})
        target = _make_spell_on_stack(game, p2, mana_cost="{4}")  # mv 4

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0  # not added yet

        new_triggers = [
            t for t in game.trigger_manager.get_triggers()
            if t.controller is p1
        ]
        assert len(new_triggers) == 1
        new_triggers[0].effect(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 4


# ---------------------------------------------------------------------------
# Engine-driven timing: BeginningOfMainPhaseTriggeredEvent delivery
# ---------------------------------------------------------------------------


class TestManaSculptMainPhaseTiming:
    """The delayed trigger is delivered by the engine's main-phase event.

    These tests exercise the real timing wiring the Implementer added:

    * ``BeginningOfMainPhaseTriggeredEvent(player=..., precombat=...)`` is the
      event ``engine/turn.py`` fires at the start of each main phase.
    * ``register_delayed`` registers a *one-shot* trigger whose condition is
      ``event.player is controller``.
    * Firing the event through ``game.trigger_manager.fire_event`` pushes the
      delayed effect onto the stack; resolving it deposits ``{C}`` into the
      controller's pool.

    The card-driven assertions (immediate ``trigger.effect(game)``) remain in
    :class:`TestManaSculptWizardCondition` / :class:`TestManaSculptDeliveryTiming`;
    here we assert the *engine* path actually delivers, fires once, and gates on
    the controlling player.
    """

    def _setup_counter_with_wizard(
        self, *, mana_cost: str = "{2}{R}"
    ) -> tuple[Any, Any, Any]:
        """Resolve a Mana Sculpt counter while p1 controls a Wizard.

        Returns ``(game, p1, p2)`` with the deferred trigger registered and
        p1's colorless pool emptied (so a later delivery is unambiguous).
        """
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard(p1)],
                        mana={ManaType.COLORLESS: 0})
        target = _make_spell_on_stack(game, p2, mana_cost=mana_cost)

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)
        return game, p1, p2

    def test_main_phase_event_delivers_colorless_to_controller(self) -> None:
        """Firing the controller's main-phase event lands the {C} in their pool.

        The {C} must NOT be present immediately after the counter resolves, and
        must appear once ``BeginningOfMainPhaseTriggeredEvent(player=p1)`` is
        fired and resolved — the engine-driven version of "at the beginning of
        your next main phase".
        """
        game, p1, _p2 = self._setup_counter_with_wizard(mana_cost="{2}{R}")  # mv 3

        # Not added yet — only registered.
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

        _fire_main_phase_begin(game, p1)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_delayed_trigger_is_consumed_after_firing_once(self) -> None:
        """The one-shot trigger is removed from the manager once it fires.

        After the controller's main-phase event fires, no Mana Sculpt trigger
        remains registered (it is a one-shot delayed trigger).
        """
        game, p1, _p2 = self._setup_counter_with_wizard()

        # Exactly one Mana-Sculpt-owned trigger before delivery.
        before = [t for t in game.trigger_manager.get_triggers()
                  if t.controller is p1]
        assert len(before) == 1

        _fire_main_phase_begin(game, p1)

        # The one-shot trigger has been consumed — none remain.
        after = [t for t in game.trigger_manager.get_triggers()
                 if t.controller is p1]
        assert len(after) == 0

    def test_does_not_fire_again_on_a_later_main_phase(self) -> None:
        """Firing the main-phase event a second time adds no further mana.

        "Your *next* main phase" — exactly once.  After the first delivery the
        trigger is gone, so a later main-phase event must not top up the pool.
        """
        game, p1, _p2 = self._setup_counter_with_wizard(mana_cost="{2}{R}")  # mv 3

        _fire_main_phase_begin(game, p1)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

        # A subsequent main phase fires the event again — but the one-shot
        # trigger was already consumed, so no additional {C} is delivered.
        _fire_main_phase_begin(game, p1, precombat=False)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_does_not_fire_on_opponents_main_phase(self) -> None:
        """The opponent's main-phase event does not deliver the {C}.

        The delayed trigger's condition is ``event.player is controller``, so
        ``BeginningOfMainPhaseTriggeredEvent(player=p2)`` must not deposit mana
        into anyone's pool, and must leave the trigger registered for p1's own
        next main phase.
        """
        game, p1, p2 = self._setup_counter_with_wizard(mana_cost="{2}{R}")

        # Opponent's main phase begins first.
        _fire_main_phase_begin(game, p2)

        # No mana delivered to either player.
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
        assert p2.mana_pool.get(ManaType.COLORLESS) == 0
        # The trigger is still waiting for p1's main phase.
        still_pending = [t for t in game.trigger_manager.get_triggers()
                         if t.controller is p1]
        assert len(still_pending) == 1

    def test_opponent_phase_then_controller_phase_delivers_once(self) -> None:
        """The trigger survives the opponent's main phase, then fires on p1's.

        End-to-end ordering: p2's main phase does nothing, then p1's main phase
        delivers exactly the recorded {C} — confirming the gate doesn't consume
        the one-shot on a non-matching event.
        """
        game, p1, p2 = self._setup_counter_with_wizard(mana_cost="{3}{U}{U}")  # mv 5

        _fire_main_phase_begin(game, p2)          # opponent's main — no-op
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

        _fire_main_phase_begin(game, p1)          # controller's main — delivers
        assert p1.mana_pool.get(ManaType.COLORLESS) == 5

    def test_no_wizard_main_phase_event_delivers_nothing(self) -> None:
        """Without a Wizard no trigger is registered, so the event is inert.

        Firing the controller's main-phase event after a Wizard-less counter
        adds no colorless mana (there was nothing to fire).
        """
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_non_wizard(p1)],
                        mana={ManaType.COLORLESS: 0})
        target = _make_spell_on_stack(game, p2, mana_cost="{2}{R}")

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target]
        card.on_resolve(game)

        _fire_main_phase_begin(game, p1)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
