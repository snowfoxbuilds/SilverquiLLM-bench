"""Tests for SOS 57 — Mana Sculpt.

Mana Sculpt is a {1}{U}{U} Instant:
  Counter target spell. If you control a Wizard, add an amount of {C}
  equal to the amount of mana spent to cast that spell at the beginning
  of your next main phase.

Requirements tested:
1. Static properties: name, mana cost, card type (Instant).
2. Targeting: targets a spell on the stack.
3. Counter effect: on_resolve counters (removes from stack) the targeted spell.
4. Wizard conditional: checks if controller has a Wizard on the battlefield.
5. Mana rebate: delayed trigger adds {C} equal to mana spent on the countered
   spell at the beginning of the controller's next main phase.
6. Edge cases: no Wizard means no mana rebate; no target is a no-op;
   countered spell goes to its owner's graveyard.
"""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.stack import StackObject
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wizard(owner=None, controller=None):
    """Create a simple Wizard creature for testing the Wizard condition."""
    wiz = Creature(
        name="Test Wizard",
        owner=owner,
        controller=controller,
        base_power=1,
        base_toughness=1,
        subtypes={"Human", "Wizard"},
    )
    return wiz


def _make_spell_on_stack(game, player, name="Target Spell", mana_cost_str="{2}{R}"):
    """Create a dummy Instant, place it on the stack, and return a StackObject
    representing it.  The card's mana_cost.cmc represents total mana spent."""
    spell_card = Instant(
        name=name,
        owner=player,
        controller=player,
        mana_cost=ManaCost.parse(mana_cost_str),
    )
    # Simulate being on the stack
    player.zones[Zone.STACK].add(spell_card)
    stack_obj = StackObject(
        source=spell_card,
        controller=player,
        targets=[],
        on_resolve=lambda g: None,
    )
    game.stack.push(stack_obj)
    return spell_card, stack_obj


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_is_instant(self) -> None:
        card = ManaSculpt(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_has_instant_card_type(self) -> None:
        card = ManaSculpt(owner=None)
        assert CardType.INSTANT in card.card_types


# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------


class TestManaSculptTargeting:
    """get_targets() should advertise a single target requirement that
    targets a spell (an object on the stack)."""

    def test_returns_at_least_one_target_requirement(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=None)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) >= 1

    def test_target_requirement_is_target_requirement_type(self) -> None:
        game = create_game()
        card = ManaSculpt(owner=None)
        reqs = card.get_targets(game)
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_stack(self) -> None:
        """Counter target spell means targeting something on the stack."""
        game = create_game()
        card = ManaSculpt(owner=None)
        reqs = card.get_targets(game)
        req = reqs[0]
        assert req.zone == Zone.STACK

    def test_target_filter_accepts_spell(self) -> None:
        """The filter should accept a spell (card with instant/sorcery type)."""
        game = create_game()
        card = ManaSculpt(owner=None)
        reqs = card.get_targets(game)
        req = reqs[0]

        spell = Instant(name="Lightning Bolt")
        # A spell on the stack should be a valid target
        assert req.filter_fn(spell) is True

    def test_target_filter_accepts_sorcery_spell(self) -> None:
        """The filter should accept a sorcery spell."""
        game = create_game()
        card = ManaSculpt(owner=None)
        reqs = card.get_targets(game)
        req = reqs[0]

        spell = Sorcery(name="Divination")
        assert req.filter_fn(spell) is True

    def test_target_filter_accepts_creature_spell(self) -> None:
        """Counter target spell can counter any spell, including creatures."""
        game = create_game()
        card = ManaSculpt(owner=None)
        reqs = card.get_targets(game)
        req = reqs[0]

        creature_spell = Creature(name="Bear", base_power=2, base_toughness=2)
        assert req.filter_fn(creature_spell) is True


# ---------------------------------------------------------------------------
# Counter effect — on_resolve
# ---------------------------------------------------------------------------


class TestManaSculptCounterEffect:
    """on_resolve should counter (remove from stack) the targeted spell."""

    def test_countered_spell_goes_to_graveyard(self) -> None:
        """When Mana Sculpt resolves, the targeted spell should be moved
        to its owner's graveyard (standard counterspell behavior)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target_spell = Instant(
            name="Lightning Bolt",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{R}"),
        )
        # Put the target spell in p2's stack zone
        p2.zones[Zone.STACK].add(target_spell)

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target_spell]
        card.on_resolve(game)

        # The countered spell should be in p2's graveyard
        assert p2.zones[Zone.GRAVEYARD].contains(target_spell)

    def test_countered_spell_removed_from_stack_zone(self) -> None:
        """After countering, the spell should no longer be in the stack zone."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target_spell = Instant(
            name="Counterspell Target",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{1}{U}"),
        )
        p2.zones[Zone.STACK].add(target_spell)

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target_spell]
        card.on_resolve(game)

        # The spell should no longer be on the stack
        assert not p2.zones[Zone.STACK].contains(target_spell)

    def test_no_target_is_noop(self) -> None:
        """When chosen_targets is empty or not set, on_resolve should not raise."""
        game = create_game()
        p1 = game.players[0]
        card = ManaSculpt(owner=p1, controller=p1)
        # No chosen_targets set
        card.on_resolve(game)

    def test_empty_chosen_targets_does_not_raise(self) -> None:
        """Empty chosen_targets list should not crash."""
        game = create_game()
        p1 = game.players[0]
        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = []
        card.on_resolve(game)


# ---------------------------------------------------------------------------
# Wizard conditional — no Wizard, no mana rebate
# ---------------------------------------------------------------------------


class TestManaSculptWithoutWizard:
    """Without a Wizard on the battlefield, Mana Sculpt should still counter
    the spell but should NOT produce any delayed mana trigger."""

    def test_counter_works_without_wizard(self) -> None:
        """The spell is still countered even without a Wizard."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target_spell = Instant(
            name="Target",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}{R}"),
        )
        p2.zones[Zone.STACK].add(target_spell)

        # No Wizard on p1's battlefield
        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target_spell]
        card.on_resolve(game)

        assert p2.zones[Zone.GRAVEYARD].contains(target_spell)

    def test_no_delayed_trigger_without_wizard(self) -> None:
        """Without a Wizard, no delayed trigger should be registered for
        the mana rebate. We verify by checking that no triggers were
        added to the trigger_manager during resolution."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target_spell = Instant(
            name="Target",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}{R}"),
        )
        p2.zones[Zone.STACK].add(target_spell)

        # No Wizard on battlefield
        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target_spell]

        triggers_before = len(game.trigger_manager.get_triggers())
        card.on_resolve(game)
        triggers_after = len(game.trigger_manager.get_triggers())

        # No new triggers should have been registered
        assert triggers_after == triggers_before


# ---------------------------------------------------------------------------
# Wizard conditional — with Wizard, mana rebate
# ---------------------------------------------------------------------------


class TestManaSculptWithWizard:
    """When the controller controls a Wizard, Mana Sculpt should set up a
    delayed trigger to add {C} equal to the mana spent to cast the
    countered spell at the beginning of the controller's next main phase."""

    def test_counter_still_works_with_wizard(self) -> None:
        """The countering effect should work the same with a Wizard."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wizard)

        target_spell = Instant(
            name="Target",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}{R}"),
        )
        p2.zones[Zone.STACK].add(target_spell)

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target_spell]
        card.on_resolve(game)

        assert p2.zones[Zone.GRAVEYARD].contains(target_spell)

    def test_delayed_trigger_registered_with_wizard(self) -> None:
        """With a Wizard on the battlefield, resolving Mana Sculpt should
        register a delayed trigger (or equivalent mechanism) for the mana
        rebate."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wizard)

        target_spell = Instant(
            name="Target",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}{R}"),
        )
        p2.zones[Zone.STACK].add(target_spell)

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target_spell]

        triggers_before = len(game.trigger_manager.get_triggers())
        card.on_resolve(game)
        triggers_after = len(game.trigger_manager.get_triggers())

        # A delayed trigger should have been registered
        assert triggers_after > triggers_before

    def test_mana_rebate_amount_matches_spell_cmc(self) -> None:
        """The amount of {C} added should equal the mana spent to cast
        the countered spell. For a spell with mana cost {2}{R} (CMC 3),
        the rebate should be 3 colorless mana.

        We verify by resolving the delayed trigger and checking the mana pool.
        """
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wizard)

        # Spell that cost 3 total mana to cast
        target_spell = Instant(
            name="Expensive Spell",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}{R}"),
        )
        p2.zones[Zone.STACK].add(target_spell)

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target_spell]
        card.on_resolve(game)

        # Find and resolve the delayed trigger
        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) >= 1, "Expected at least one delayed trigger"

        # Simulate the trigger firing and resolving
        trigger = triggers[0]
        # The trigger effect should add mana to p1's pool
        colorless_before = p1.mana_pool.get(ManaType.COLORLESS)
        trigger.effect(game)

        colorless_after = p1.mana_pool.get(ManaType.COLORLESS)
        # Should have gained 3 colorless mana (CMC of {2}{R})
        assert colorless_after - colorless_before == 3

    def test_mana_rebate_for_one_mana_spell(self) -> None:
        """Countering a 1-mana spell should give a rebate of 1 colorless."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wizard)

        target_spell = Instant(
            name="Shock",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{R}"),
        )
        p2.zones[Zone.STACK].add(target_spell)

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target_spell]
        card.on_resolve(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) >= 1

        trigger = triggers[0]
        colorless_before = p1.mana_pool.get(ManaType.COLORLESS)
        trigger.effect(game)

        colorless_after = p1.mana_pool.get(ManaType.COLORLESS)
        assert colorless_after - colorless_before == 1

    def test_mana_rebate_for_expensive_spell(self) -> None:
        """Countering a 6-mana spell should yield 6 colorless mana."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wizard)

        target_spell = Sorcery(
            name="Big Spell",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{4}{U}{U}"),
        )
        p2.zones[Zone.STACK].add(target_spell)

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target_spell]
        card.on_resolve(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) >= 1

        trigger = triggers[0]
        colorless_before = p1.mana_pool.get(ManaType.COLORLESS)
        trigger.effect(game)

        colorless_after = p1.mana_pool.get(ManaType.COLORLESS)
        assert colorless_after - colorless_before == 6

    def test_mana_rebate_adds_colorless(self) -> None:
        """The mana added should be colorless ({C}), not any colored type."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wizard)

        target_spell = Instant(
            name="Bolt",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{R}"),
        )
        p2.zones[Zone.STACK].add(target_spell)

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target_spell]
        card.on_resolve(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) >= 1

        # Snapshot all mana types before trigger fires
        mana_before = {mt: p1.mana_pool.get(mt) for mt in ManaType}
        trigger = triggers[0]
        trigger.effect(game)
        mana_after = {mt: p1.mana_pool.get(mt) for mt in ManaType}

        # Only colorless should change
        for mt in ManaType:
            if mt == ManaType.COLORLESS:
                assert mana_after[mt] > mana_before[mt]
            else:
                assert mana_after[mt] == mana_before[mt], (
                    f"Non-colorless mana type {mt} changed unexpectedly"
                )


# ---------------------------------------------------------------------------
# Wizard detection — various Wizard subtypes
# ---------------------------------------------------------------------------


class TestManaSculptWizardDetection:
    """The card checks if 'you control a Wizard'. This should check for the
    Wizard creature subtype on any permanent on the controller's battlefield."""

    def test_wizard_subtype_detected(self) -> None:
        """A creature with the Wizard subtype should satisfy the condition."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wizard)

        target_spell = Instant(
            name="Target",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{1}"),
        )
        p2.zones[Zone.STACK].add(target_spell)

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target_spell]

        triggers_before = len(game.trigger_manager.get_triggers())
        card.on_resolve(game)
        triggers_after = len(game.trigger_manager.get_triggers())

        # Wizard was present, so a delayed trigger should be created
        assert triggers_after > triggers_before

    def test_non_wizard_creature_does_not_trigger_rebate(self) -> None:
        """A creature without Wizard subtype should not enable the rebate."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # A non-Wizard creature
        bear = Creature(
            name="Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
            subtypes={"Bear"},
        )
        game.get_battlefield(p1).add(bear)

        target_spell = Instant(
            name="Target",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{1}"),
        )
        p2.zones[Zone.STACK].add(target_spell)

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target_spell]

        triggers_before = len(game.trigger_manager.get_triggers())
        card.on_resolve(game)
        triggers_after = len(game.trigger_manager.get_triggers())

        assert triggers_after == triggers_before

    def test_opponent_wizard_does_not_count(self) -> None:
        """A Wizard controlled by the opponent should NOT enable the rebate."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Wizard on opponent's battlefield
        opp_wizard = _make_wizard(owner=p2, controller=p2)
        game.get_battlefield(p2).add(opp_wizard)

        target_spell = Instant(
            name="Target",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}"),
        )
        p2.zones[Zone.STACK].add(target_spell)

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target_spell]

        triggers_before = len(game.trigger_manager.get_triggers())
        card.on_resolve(game)
        triggers_after = len(game.trigger_manager.get_triggers())

        # No rebate because the Wizard is the opponent's
        assert triggers_after == triggers_before


# ---------------------------------------------------------------------------
# Edge case — countering a zero-mana spell
# ---------------------------------------------------------------------------


class TestManaSculptZeroManaSpell:
    """Countering a spell with CMC 0 should produce 0 colorless mana rebate."""

    def test_zero_cmc_spell_gives_zero_mana(self) -> None:
        """A 0-cost spell yields a rebate of 0 colorless mana."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wizard)

        # A zero-cost spell (like Ornithopter, conceptually)
        target_spell = Instant(
            name="Free Spell",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost(generic=0, pips={}),
        )
        p2.zones[Zone.STACK].add(target_spell)

        card = ManaSculpt(owner=p1, controller=p1)
        card.chosen_targets = [target_spell]
        card.on_resolve(game)

        # Even with a Wizard, zero mana spent means zero mana rebate.
        # The trigger may or may not be registered for a 0-mana spell,
        # but if it fires, no mana should be added.
        triggers = game.trigger_manager.get_triggers_for_source(card)
        if triggers:
            colorless_before = p1.mana_pool.get(ManaType.COLORLESS)
            triggers[0].effect(game)
            colorless_after = p1.mana_pool.get(ManaType.COLORLESS)
            assert colorless_after == colorless_before
