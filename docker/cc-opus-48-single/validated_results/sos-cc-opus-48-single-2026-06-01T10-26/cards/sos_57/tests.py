"""Tests for SOS 57 — Mana Sculpt.

Mana Sculpt ({1}{U}{U} Instant):

    Counter target spell. If you control a Wizard, add an amount of {C}
    equal to the amount of mana spent to cast that spell at the beginning
    of your next main phase.

The card has three observable obligations:

1. **Static data** — name, mana cost ({1}{U}{U}), instant type, blue color.
2. **Counter target spell** — the targeted spell is removed from the stack
   and put into its owner's graveyard; it never resolves.
3. **Conditional delayed mana** — *only* if the controller controls a Wizard
   when Mana Sculpt resolves, a delayed effect is set up that adds colorless
   mana equal to the mana spent on the countered spell at the beginning of
   the controller's next main phase. With no Wizard, no such effect occurs.

The engine ships no built-in counter mechanism, no per-spell "mana spent"
tracking, and no begin-of-main-phase trigger firing, so the implementation
must provide these. These tests drive the observable contract: stack/zone
movement for the counter, and the presence/absence + colorless amount of
the delayed mana effect keyed on Wizard control.

TDD red-phase: the stub at ``card_impl.py`` is empty, so everything here is
expected to fail until the card is implemented.
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import CardImpl, Creature, Instant, Sorcery
from engine.casting import cast_spell as engine_cast_spell
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.turn import run_turn
from engine.types import (
    CardType,
    Color,
    ManaCost,
    ManaType,
    Phase,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wizard(name: str = "Test Wizard") -> Creature:
    """A 1/1 creature with the Wizard subtype."""
    return Creature(
        name=name,
        mana_cost=ManaCost.parse("{U}"),
        base_power=1,
        base_toughness=1,
        subtypes={"Wizard"},
    )


def _non_wizard(name: str = "Grizzly Bears") -> Creature:
    """A vanilla 2/2 Bear (no Wizard subtype)."""
    return Creature(
        name=name,
        mana_cost=ManaCost.parse("{1}{G}"),
        base_power=2,
        base_toughness=2,
        subtypes={"Bear"},
    )


def _victim_spell(name: str = "Lightning Bolt", cost: str = "{R}") -> Instant:
    """A throwaway spell to be countered."""
    return Instant(name=name, mana_cost=ManaCost.parse(cost))


def _put_spell_on_stack(game: Any, caster: Any, card: CardImpl) -> StackObject:
    """Place *card* on the stack as a spell controlled by *caster*.

    Mirrors the post-cast state: the card lives in the caster's STACK zone
    and a StackObject referencing it sits on the game stack with an
    ``on_resolve`` that would put it into its owner's graveyard.
    """
    card.owner = caster
    card.controller = caster
    caster.zones[Zone.STACK].add(card)

    resolved = {"flag": False}

    def _resolve(g: Any) -> None:
        # If this ever runs, the spell was NOT countered.
        resolved["flag"] = True
        caster.zones[Zone.STACK].remove(card)
        caster.zones[Zone.GRAVEYARD].add(card)

    obj = StackObject(source=card, controller=caster, on_resolve=_resolve)
    obj.targets = []
    game.stack.push(obj)
    return obj


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------


class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_is_instant(self) -> None:
        card = ManaSculpt(owner=None)
        assert isinstance(card, Instant)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_is_blue(self) -> None:
        card = ManaSculpt(owner=None)
        assert Color.BLUE in card.colors

    def test_not_a_creature(self) -> None:
        assert CardType.CREATURE not in ManaSculpt(owner=None).card_types


# ---------------------------------------------------------------------------
# Targeting — "Counter target spell"
# ---------------------------------------------------------------------------


class TestManaSculptTargeting:
    """get_targets() advertises a single 'target spell' requirement."""

    def test_returns_one_target_requirement(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ManaSculpt(owner=p1, controller=p1)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_requirement_uses_stack_zone(self) -> None:
        """A spell lives on the stack, so the requirement must look there."""
        game = create_game()
        p1 = game.players[0]
        card = ManaSculpt(owner=p1, controller=p1)
        req = card.get_targets(game)[0]
        assert req.zone == Zone.STACK

    def test_filter_accepts_an_instant_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ManaSculpt(owner=p1, controller=p1)
        req = card.get_targets(game)[0]
        victim = _victim_spell()
        assert req.filter_fn(victim) is True

    def test_filter_accepts_a_sorcery_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ManaSculpt(owner=p1, controller=p1)
        req = card.get_targets(game)[0]
        sorc = Sorcery(name="Divination", mana_cost=ManaCost.parse("{2}{U}"))
        assert req.filter_fn(sorc) is True

    def test_filter_rejects_a_player(self) -> None:
        """'target spell' is not 'any target' — players are not legal."""
        game = create_game()
        p1, p2 = game.players
        card = ManaSculpt(owner=p1, controller=p1)
        req = card.get_targets(game)[0]
        assert req.filter_fn(p1) is False
        assert req.filter_fn(p2) is False


# ---------------------------------------------------------------------------
# Counter resolution
# ---------------------------------------------------------------------------


class TestManaSculptCounter:
    """on_resolve counters the targeted spell: removes it from the stack and
    puts it into its owner's graveyard, and the spell never resolves."""

    def test_targeted_spell_leaves_the_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        victim = _victim_spell()
        victim_obj = _put_spell_on_stack(game, p2, victim)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [victim]
        sculpt.on_resolve(game)

        assert victim_obj not in game.stack.objects()
        assert not p2.zones[Zone.STACK].contains(victim)

    def test_countered_spell_goes_to_owners_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        victim = _victim_spell()
        _put_spell_on_stack(game, p2, victim)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [victim]
        sculpt.on_resolve(game)

        assert p2.zones[Zone.GRAVEYARD].contains(victim)

    def test_countered_spell_does_not_resolve(self) -> None:
        """A countered spell's on_resolve callback must never fire."""
        game = create_game()
        p1, p2 = game.players
        victim = _victim_spell()
        victim_obj = _put_spell_on_stack(game, p2, victim)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [victim]
        sculpt.on_resolve(game)

        # The counter removes the victim's StackObject, so its resolve
        # callback can never fire.  Confirm the spell is no longer pending on
        # the stack and never reached the battlefield.
        assert victim_obj not in game.stack.objects()
        assert not p2.zones[Zone.BATTLEFIELD].contains(victim)

    def test_no_target_resolution_is_safe_noop(self) -> None:
        """If the spell has no legal target (none chosen), resolution must not
        raise and must not affect the stack."""
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = []
        # Should not raise.
        sculpt.on_resolve(game)
        assert game.stack.is_empty()


# ---------------------------------------------------------------------------
# Conditional delayed mana — "If you control a Wizard ..."
# ---------------------------------------------------------------------------


class TestManaSculptWizardConditional:
    """The colorless-mana payoff is conditional on controlling a Wizard when
    Mana Sculpt resolves.  We observe the conditional by inspecting whether a
    delayed effect (a registered trigger) is created on resolution."""

    def _triggers_for(self, game: Any, source: Any) -> list[Any]:
        return game.trigger_manager.get_triggers_for_source(source)

    def test_no_wizard_sets_up_no_delayed_mana_effect(self) -> None:
        """With no Wizard controlled, the spell only counters — no delayed
        mana trigger is registered for it."""
        game = create_game()
        p1, p2 = game.players
        # p1 controls a non-Wizard creature only.
        set_board_state(game, 0, battlefield=[_non_wizard()])
        victim = _victim_spell()
        _put_spell_on_stack(game, p2, victim)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [victim]
        before = len(game.trigger_manager.get_triggers())
        sculpt.on_resolve(game)
        after = len(game.trigger_manager.get_triggers())

        # No new delayed trigger should have been registered.
        assert after == before
        # And the counter still happened.
        assert p2.zones[Zone.GRAVEYARD].contains(victim)

    def test_wizard_control_sets_up_a_delayed_mana_effect(self) -> None:
        """With a Wizard controlled, resolution registers a delayed trigger
        (for the 'beginning of your next main phase' mana payoff)."""
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard()])
        victim = _victim_spell()
        _put_spell_on_stack(game, p2, victim)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [victim]
        before = len(game.trigger_manager.get_triggers())
        sculpt.on_resolve(game)
        after = len(game.trigger_manager.get_triggers())

        assert after - before == 1

    def test_delayed_effect_controlled_by_mana_sculpt_caster(self) -> None:
        """The delayed mana effect belongs to Mana Sculpt's controller — they
        are the player who gets the {C}."""
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard()])
        victim = _victim_spell()
        _put_spell_on_stack(game, p2, victim)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [victim]
        sculpt.on_resolve(game)

        new_triggers = [
            t
            for t in game.trigger_manager.get_triggers()
            if t.controller is p1
        ]
        assert len(new_triggers) >= 1


# ---------------------------------------------------------------------------
# Delayed mana amount + payoff
# ---------------------------------------------------------------------------


class TestManaSculptManaPayoff:
    """When the delayed effect fires (controller's next main phase), it adds
    colorless mana equal to the amount of mana spent on the countered spell.

    We drive the payoff by firing the registered trigger's effect directly and
    observing the controller's mana pool gain colorless mana."""

    def _resolve_delayed_effect(self, game: Any, source: Any) -> None:
        """Find and run the delayed effect registered by *source*."""
        triggers = game.trigger_manager.get_triggers_for_source(source)
        assert triggers, "expected a delayed trigger registered by Mana Sculpt"
        for t in triggers:
            t.effect(game)

    def test_payoff_adds_colorless_equal_to_mana_spent(self) -> None:
        """A 3-mana spell countered → 3 colorless added to controller's pool."""
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard()])
        # A spell whose mana value / mana spent is 3 ({1}{U}{U}).
        victim = _victim_spell(name="Cancel", cost="{1}{U}{U}")
        _put_spell_on_stack(game, p2, victim)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [victim]
        p1.mana_pool.empty()
        sculpt.on_resolve(game)

        self._resolve_delayed_effect(game, sculpt)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_payoff_amount_scales_with_spell_cost(self) -> None:
        """A 1-mana spell countered → only 1 colorless added."""
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard()])
        victim = _victim_spell(name="Lightning Bolt", cost="{R}")
        _put_spell_on_stack(game, p2, victim)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [victim]
        p1.mana_pool.empty()
        sculpt.on_resolve(game)

        self._resolve_delayed_effect(game, sculpt)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_payoff_mana_is_colorless_not_colored(self) -> None:
        """The added mana is {C} — no colored mana is produced."""
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard()])
        victim = _victim_spell(name="Cancel", cost="{1}{U}{U}")
        _put_spell_on_stack(game, p2, victim)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [victim]
        p1.mana_pool.empty()
        sculpt.on_resolve(game)

        self._resolve_delayed_effect(game, sculpt)
        for mt in (
            ManaType.WHITE,
            ManaType.BLUE,
            ManaType.BLACK,
            ManaType.RED,
            ManaType.GREEN,
        ):
            assert p1.mana_pool.get(mt) == 0


# ---------------------------------------------------------------------------
# Mana-spent tracking through the real payment pipeline
# ---------------------------------------------------------------------------


class _CostReducedSpell(Instant):
    """A 4-mana instant ({4}) that costs {2} less to cast.

    Casting it through the engine pipeline therefore deducts only 2 mana
    even though its printed mana value (CMC) is 4 — making
    ``mana_spent`` (actual mana paid) diverge from CMC.  This is the case
    that ``ManaSculpt`` must honour: "the amount of mana SPENT", not the
    mana value.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cost Reduced Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))
        super().__init__(**kwargs)
        self.chosen_targets: list[Any] = []

    def cost_reduction(self, game: Any) -> int:  # noqa: ARG002
        return 2


def _cast_through_pipeline(game: Any, player_index: int, card: CardImpl) -> None:
    """Cast *card* from a player's hand via the REAL casting pipeline.

    Puts the card in hand, gives the player enough generic-colourless mana,
    sets sorcery-speed timing, and calls :func:`engine.casting.cast_spell`
    so payment runs through ``ManaPool.pay`` and ``card.mana_spent`` is
    populated from ``last_payment_total``.  The cast spell is left on the
    stack (not resolved) so it can be countered.
    """
    player = game.players[player_index]
    player.zones[Zone.HAND].add(card)
    card.owner = player
    card.controller = player
    # Sorcery-speed timing for the cast (instants bypass this, but set it
    # anyway so any spell type can use this helper).
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    engine_cast_spell(game, player, card)


class TestManaSpentTrackingPipeline:
    """`mana_spent` reflects ACTUAL mana paid (rule 107.7), not the printed
    mana value — verified by casting a cost-reduced spell through the real
    payment pipeline."""

    def test_cost_reduced_spell_records_actual_mana_spent(self) -> None:
        """A {4} spell reduced by {2} pays 2 mana → mana_spent == 2 (not CMC 4)."""
        game = create_game()
        spell = _CostReducedSpell()
        # Exactly enough mana for the *reduced* cost.
        game.players[1].mana_pool.empty()
        game.players[1].mana_pool.add(ManaType.COLORLESS, 2)

        _cast_through_pipeline(game, 1, spell)

        # CMC is 4 but only 2 mana was actually spent.
        assert spell.mana_cost.cmc == 4
        assert spell.mana_spent == 2

    def test_counter_payoff_equals_actual_mana_spent_not_cmc(self) -> None:
        """Countering a cost-reduced spell pays {C} equal to mana SPENT (2),
        not the spell's printed mana value (4)."""
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard()])

        spell = _CostReducedSpell()
        p2.mana_pool.empty()
        p2.mana_pool.add(ManaType.COLORLESS, 2)
        _cast_through_pipeline(game, 1, spell)
        # Sanity: the spell is on the stack and recorded a real mana_spent.
        assert spell.mana_spent == 2

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [spell]
        p1.mana_pool.empty()
        sculpt.on_resolve(game)

        # The spell was countered.
        assert p2.zones[Zone.GRAVEYARD].contains(spell)

        # Fire the delayed effect; payoff must equal mana spent (2), not CMC (4).
        triggers = game.trigger_manager.get_triggers_for_source(sculpt)
        assert triggers, "expected a delayed trigger registered by Mana Sculpt"
        for t in triggers:
            t.effect(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2


# ---------------------------------------------------------------------------
# Beginning-of-main-phase natural firing (end-to-end through the turn loop)
# ---------------------------------------------------------------------------


def _fire_main_phase_for(game: Any, player: Any) -> None:
    """Reproduce the engine's begin-of-main-phase firing site for *player*.

    This is exactly what ``engine.turn.run_turn`` does at the start of a
    main phase (turn.py: fire ``BeginningOfMainPhaseTriggeredEvent`` then
    grant priority so the resulting stack object resolves).  We position
    the game at *player*'s precombat main phase, fire the real event
    through ``trigger_manager.fire_event``, and resolve the stack — driving
    the delayed payoff through the natural trigger-firing path rather than
    by calling the effect directly.
    """
    game.active_player_index = game.players.index(player)
    game.priority_player_index = game.active_player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.trigger_manager.fire_event(
        game,
        BeginningOfMainPhaseTriggeredEvent(player=player, phase=Phase.PRECOMBAT_MAIN),
    )
    # Resolve any triggers the event placed on the stack.
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class TestManaSculptNaturalPayoff:
    """The delayed {C} appears in the controller's pool at the beginning of
    their next main phase via the engine's natural trigger-firing path."""

    def test_payoff_fires_at_controllers_next_main_phase(self) -> None:
        """With a Wizard controlled, the {C} appears when the controller's
        begin-of-main-phase event fires through the trigger manager."""
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard()])
        victim = _victim_spell(name="Cancel", cost="{1}{U}{U}")
        _put_spell_on_stack(game, p2, victim)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [victim]
        sculpt.on_resolve(game)

        p1.mana_pool.empty()
        # No {C} yet — the delayed effect has not fired.
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

        _fire_main_phase_for(game, p1)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_payoff_does_not_fire_on_opponents_main_phase(self) -> None:
        """The trigger is keyed to the CONTROLLER's main phase — the
        opponent's begin-of-main-phase event must not pay out."""
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard()])
        victim = _victim_spell(name="Cancel", cost="{1}{U}{U}")
        _put_spell_on_stack(game, p2, victim)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [victim]
        sculpt.on_resolve(game)

        p1.mana_pool.empty()
        # Fire the OPPONENT's main phase — should not trigger p1's payoff.
        _fire_main_phase_for(game, p2)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_payoff_is_one_shot(self) -> None:
        """After firing once, the delayed effect unregisters — a second
        main phase produces no additional mana."""
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard()])
        victim = _victim_spell(name="Cancel", cost="{1}{U}{U}")
        _put_spell_on_stack(game, p2, victim)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [victim]
        sculpt.on_resolve(game)

        _fire_main_phase_for(game, p1)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

        # The trigger should have removed itself.
        assert game.trigger_manager.get_triggers_for_source(sculpt) == []

        # A second main phase yields no further mana.
        p1.mana_pool.empty()
        _fire_main_phase_for(game, p1)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_no_wizard_means_no_payoff_at_main_phase(self) -> None:
        """With no Wizard controlled, no delayed effect is registered, so the
        controller's next main phase produces no {C}."""
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_non_wizard()])
        victim = _victim_spell(name="Cancel", cost="{1}{U}{U}")
        _put_spell_on_stack(game, p2, victim)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [victim]
        sculpt.on_resolve(game)

        # Counter still happened, but nothing was registered.
        assert p2.zones[Zone.GRAVEYARD].contains(victim)
        assert game.trigger_manager.get_triggers_for_source(sculpt) == []

        p1.mana_pool.empty()
        _fire_main_phase_for(game, p1)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_payoff_via_full_turn_loop(self) -> None:
        """End-to-end: run the real turn loop so the engine itself fires the
        begin-of-main-phase event and the {C} lands in the pool during the
        controller's precombat main phase.

        Because mana pools empty on phase transitions, we observe the pool
        the moment it is granted by hooking the Wizard's natural firing site
        through ``run_turn`` and capturing the pool at the main phase.
        """
        from engine.types import Step

        # Both players auto-pass priority throughout the turn.  Whenever the
        # delayed trigger is placed on the stack, priority_loop asks each
        # player to act; scripting plenty of "pass" answers lets the turn
        # run to completion deterministically.
        passes = ["pass"] * 200
        game = create_game(scripts=(list(passes), list(passes)))
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard()])
        victim = _victim_spell(name="Cancel", cost="{1}{U}{U}")
        _put_spell_on_stack(game, p2, victim)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [victim]
        sculpt.on_resolve(game)

        # Position the turn loop so p1 is the active player and start at the
        # very beginning of p1's turn; run_turn will pass through p1's
        # precombat main phase and fire the begin-of-main-phase event.
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.BEGINNING
        game.step = Step.UNTAP

        captured: dict[str, int] = {}
        original_add = p1.mana_pool.add

        def _spy_add(mana_type: ManaType, amount: int = 1) -> None:
            original_add(mana_type, amount)
            if mana_type == ManaType.COLORLESS:
                captured["colorless"] = p1.mana_pool.get(ManaType.COLORLESS)

        p1.mana_pool.add = _spy_add  # type: ignore[method-assign]
        try:
            run_turn(game)
        finally:
            p1.mana_pool.add = original_add  # type: ignore[method-assign]

        # The delayed effect added exactly 3 {C} during the turn.
        assert captured.get("colorless") == 3
        # And the one-shot trigger removed itself.
        assert game.trigger_manager.get_triggers_for_source(sculpt) == []
