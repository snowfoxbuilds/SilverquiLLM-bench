"""Tests for SOS 57 — Mana Sculpt.

Covers:
- Static card properties (name, mana cost, type, no keywords)
- Targeting: get_targets() returns a TargetRequirement for spells on Zone.STACK
- Counter effect: on_resolve removes target spell from the stack and sends it to graveyard
- No-target safety: on_resolve with no target is a no-op
- Wizard check: when controller controls a Wizard, a deferred-mana trigger is registered
- No-wizard path: when no Wizard, no trigger is registered
- Mana amount: the pending mana equals the countered spell's mana value (CMC)
"""

from __future__ import annotations

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

from cards.sos.sos_57.card_impl import ManaSculpt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_wizard(owner, controller) -> Creature:
    """Create a 2/2 Human Wizard creature for testing."""
    wizard = Creature(
        name="Test Wizard",
        owner=owner,
        controller=controller,
        base_power=2,
        base_toughness=2,
    )
    wizard.card_types = {CardType.CREATURE}
    wizard.subtypes = {"Human", "Wizard"}
    return wizard


def _make_non_wizard(owner, controller) -> Creature:
    """Create a 2/2 Bear creature (no Wizard subtype) for testing."""
    bear = Creature(
        name="Grizzly Bears",
        owner=owner,
        controller=controller,
        base_power=2,
        base_toughness=2,
    )
    bear.card_types = {CardType.CREATURE}
    bear.subtypes = {"Bear"}
    return bear


def _push_sorcery(game, owner, controller, name="Divination", cost="{2}{U}") -> StackObject:
    """Put a sorcery on the stack and return its StackObject."""
    spell = Sorcery(
        name=name,
        owner=owner,
        controller=controller,
        mana_cost=ManaCost.parse(cost),
    )
    stack_obj = StackObject(source=spell, controller=controller)
    game.stack.push(stack_obj)
    return stack_obj


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------


class TestManaSculptProperties:
    """Static card data must match the SOS 57 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_card_type_includes_instant(self) -> None:
        card = ManaSculpt(owner=None)
        assert CardType.INSTANT in card.card_types

    def test_no_keywords(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.keywords == Keyword(0)


# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------


class TestManaSculptTargeting:
    """get_targets() must advertise exactly one TargetRequirement for the stack."""

    def test_returns_one_target_requirement(self) -> None:
        game = create_game()
        reqs = ManaSculpt(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1

    def test_target_requirement_type(self) -> None:
        game = create_game()
        req = ManaSculpt(owner=None).get_targets(game)[0]
        assert isinstance(req, TargetRequirement)

    def test_target_zone_is_stack(self) -> None:
        """Counterspells target spells on the stack."""
        game = create_game()
        req = ManaSculpt(owner=None).get_targets(game)[0]
        assert req.zone == Zone.STACK

    def test_target_filter_accepts_stack_object(self) -> None:
        """The filter must accept objects that represent spells on the stack."""
        game = create_game()
        p2 = game.players[1]
        req = ManaSculpt(owner=None).get_targets(game)[0]

        spell = Sorcery(name="Divination", owner=p2, controller=p2)
        stack_obj = StackObject(source=spell, controller=p2)

        assert req.filter_fn(stack_obj) is True


# ---------------------------------------------------------------------------
# Counter effect
# ---------------------------------------------------------------------------


class TestManaSculptCounterEffect:
    """on_resolve must counter the chosen target spell."""

    def test_counter_removes_spell_from_stack(self) -> None:
        """The targeted stack object must be removed from the stack on resolution."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        stack_obj = _push_sorcery(game, p2, p2, name="Fireball", cost="{X}{R}")

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        stack_items = game.stack.objects()
        assert stack_obj not in stack_items

    def test_counter_sends_spell_to_graveyard(self) -> None:
        """The countered spell's source card must end up in its owner's graveyard."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        stack_obj = _push_sorcery(game, p2, p2, name="Divination", cost="{2}{U}")
        source_card = stack_obj.source

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        graveyard = game.get_graveyard(p2)
        assert graveyard.contains(source_card)

    def test_counter_removes_entire_stack_object(self) -> None:
        """After countering, the stack should have one fewer item."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Push two spells; counter the top one
        _push_sorcery(game, p2, p2, name="Ponder", cost="{U}")
        top_obj = _push_sorcery(game, p2, p2, name="Divination", cost="{2}{U}")

        before_count = len(game.stack)
        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [top_obj]
        sculpt.on_resolve(game)

        assert len(game.stack) == before_count - 1

    def test_no_target_is_a_noop(self) -> None:
        """When chosen_targets is empty, on_resolve must not raise and must leave state unchanged."""
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = []
        # Must not raise
        sculpt.on_resolve(game)
        # Stack must be empty
        assert game.stack.is_empty()


# ---------------------------------------------------------------------------
# Wizard conditional — trigger registration
# ---------------------------------------------------------------------------


class TestManaSculptWizardTrigger:
    """When controller has a Wizard, on_resolve must register a deferred
    trigger to add colorless mana at the beginning of the next main phase."""

    def test_with_wizard_registers_a_trigger(self) -> None:
        """After countering a spell with a Wizard on the battlefield, at least
        one new trigger must be registered on the game's trigger manager."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(p1, p1)
        set_board_state(game, 0, battlefield=[wizard])

        stack_obj = _push_sorcery(game, p2, p2, name="Divination", cost="{2}{U}")

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]

        before = len(game.trigger_manager.get_triggers())
        sculpt.on_resolve(game)
        after = len(game.trigger_manager.get_triggers())

        assert after > before

    def test_without_wizard_does_not_register_trigger(self) -> None:
        """Without a Wizard on the battlefield, no new trigger should be registered."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        non_wizard = _make_non_wizard(p1, p1)
        set_board_state(game, 0, battlefield=[non_wizard])

        stack_obj = _push_sorcery(game, p2, p2, name="Divination", cost="{2}{U}")

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]

        before = len(game.trigger_manager.get_triggers())
        sculpt.on_resolve(game)
        after = len(game.trigger_manager.get_triggers())

        assert after == before

    def test_empty_battlefield_does_not_register_trigger(self) -> None:
        """With no creatures at all, no trigger should be registered."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        set_board_state(game, 0, battlefield=[])

        stack_obj = _push_sorcery(game, p2, p2, name="Ponder", cost="{U}")

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]

        before = len(game.trigger_manager.get_triggers())
        sculpt.on_resolve(game)
        after = len(game.trigger_manager.get_triggers())

        assert after == before

    def test_opponent_wizard_does_not_trigger(self) -> None:
        """A Wizard controlled by the *opponent* should not qualify — the card
        says 'if YOU control a Wizard'."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put the Wizard on the opponent's side
        opp_wizard = _make_wizard(p2, p2)
        set_board_state(game, 1, battlefield=[opp_wizard])
        set_board_state(game, 0, battlefield=[])

        stack_obj = _push_sorcery(game, p2, p2, name="Divination", cost="{2}{U}")

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]

        before = len(game.trigger_manager.get_triggers())
        sculpt.on_resolve(game)
        after = len(game.trigger_manager.get_triggers())

        assert after == before


# ---------------------------------------------------------------------------
# Wizard conditional — mana amount
# ---------------------------------------------------------------------------


class TestManaSculptManaBonusAmount:
    """The deferred colorless mana trigger should know the countered spell's mana value.

    We test the trigger effect directly (as registered triggers store their
    effect callable) to verify the correct amount of colorless mana is added
    when the trigger resolves, regardless of which event fires it.
    """

    def _register_and_get_mana_trigger(self, game, caster, target_stack_obj):
        """Resolve Mana Sculpt with a Wizard and return the newly registered trigger."""
        wizard = _make_wizard(caster, caster)
        set_board_state(game, game.players.index(caster), battlefield=[wizard])
        sculpt = ManaSculpt(owner=caster, controller=caster)
        sculpt.chosen_targets = [target_stack_obj]

        before = list(game.trigger_manager.get_triggers())
        sculpt.on_resolve(game)
        after = list(game.trigger_manager.get_triggers())

        new_triggers = [t for t in after if t not in before]
        return new_triggers

    def test_trigger_effect_adds_three_colorless_for_three_cmc_spell(self) -> None:
        """When the trigger resolves (CMC 3 spell), 3 colorless mana should be added."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # CMC 3 = {2}{U}
        stack_obj = _push_sorcery(game, p2, p2, name="Divination", cost="{2}{U}")
        new_triggers = self._register_and_get_mana_trigger(game, p1, stack_obj)

        assert len(new_triggers) == 1
        trigger = new_triggers[0]

        # Clear mana pool, then invoke the trigger effect directly
        p1.mana_pool.empty()
        trigger.effect(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_trigger_effect_adds_five_colorless_for_five_cmc_spell(self) -> None:
        """When the trigger resolves (CMC 5 spell), 5 colorless mana should be added."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # CMC 5 = {3}{U}{U}
        stack_obj = _push_sorcery(game, p2, p2, name="Big Spell", cost="{3}{U}{U}")
        new_triggers = self._register_and_get_mana_trigger(game, p1, stack_obj)

        assert len(new_triggers) == 1
        trigger = new_triggers[0]

        p1.mana_pool.empty()
        trigger.effect(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 5

    def test_trigger_effect_adds_one_colorless_for_one_cmc_spell(self) -> None:
        """When the trigger resolves (CMC 1 spell), 1 colorless mana should be added."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # CMC 1 = {U}
        stack_obj = _push_sorcery(game, p2, p2, name="Opt", cost="{U}")
        new_triggers = self._register_and_get_mana_trigger(game, p1, stack_obj)

        assert len(new_triggers) == 1
        trigger = new_triggers[0]

        p1.mana_pool.empty()
        trigger.effect(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 1

    def test_trigger_effect_adds_colorless_not_blue(self) -> None:
        """The mana added by the trigger effect must be colorless ({C}), not blue."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        stack_obj = _push_sorcery(game, p2, p2, name="Divination", cost="{2}{U}")
        new_triggers = self._register_and_get_mana_trigger(game, p1, stack_obj)

        assert len(new_triggers) == 1
        trigger = new_triggers[0]

        p1.mana_pool.empty()
        trigger.effect(game)

        # Must add colorless mana
        assert p1.mana_pool.get(ManaType.COLORLESS) > 0
        # Must NOT add blue mana
        assert p1.mana_pool.get(ManaType.BLUE) == 0

    def test_without_wizard_no_trigger_effect_adds_mana(self) -> None:
        """Without a Wizard on the battlefield, on_resolve should not register
        any trigger that adds mana, leaving the mana pool empty."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        set_board_state(game, 0, battlefield=[])

        stack_obj = _push_sorcery(game, p2, p2, name="Divination", cost="{2}{U}")

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]

        before = list(game.trigger_manager.get_triggers())
        sculpt.on_resolve(game)
        after = list(game.trigger_manager.get_triggers())

        new_triggers = [t for t in after if t not in before]
        assert len(new_triggers) == 0

        # Mana pool should remain empty
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0


# ---------------------------------------------------------------------------
# Beginning-of-main-phase timing
# ---------------------------------------------------------------------------


class TestManaSculptMainPhaseTiming:
    """Verify mana delivery timing: NOT on resolve, YES when
    BeginningOfMainPhaseTriggeredEvent fires."""

    def _setup_with_wizard_and_counter(self, cost: str = "{2}{U}"):
        """Return (game, p1, p2) after Mana Sculpt has resolved with a Wizard
        and countered a spell with the given cost.  p1's mana pool is emptied
        before returning so that assertions start from a clean state."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent  # noqa: F401

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(p1, p1)
        set_board_state(game, 0, battlefield=[wizard])

        stack_obj = _push_sorcery(game, p2, p2, name="Divination", cost=cost)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        # Clear any mana that on_resolve might have added (should be zero, but
        # ensure assertions start from a clean baseline)
        p1.mana_pool.empty()

        return game, p1, p2

    def test_mana_not_added_immediately_on_resolve(self) -> None:
        """on_resolve must NOT add any colorless mana to the mana pool right away."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(p1, p1)
        set_board_state(game, 0, battlefield=[wizard])

        stack_obj = _push_sorcery(game, p2, p2, name="Divination", cost="{2}{U}")

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]

        p1.mana_pool.empty()
        sculpt.on_resolve(game)

        # Mana pool must still be empty immediately after resolution
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_mana_added_when_main_phase_event_fires_and_trigger_resolves(self) -> None:
        """Firing BeginningOfMainPhaseTriggeredEvent must push the mana trigger
        onto the stack; resolving that trigger adds the correct colorless mana."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent

        game, p1, _ = self._setup_with_wizard_and_counter(cost="{2}{U}")  # CMC 3

        # Fire the beginning-of-main-phase event
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent())

        # The trigger should now be on the stack as a StackObject
        assert not game.stack.is_empty(), (
            "Expected a trigger stack-object after BeginningOfMainPhaseTriggeredEvent"
        )

        # Resolve the top of the stack (the triggered ability)
        stack_obj = game.stack.pop()
        stack_obj.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_correct_mana_amount_delivered_via_event(self) -> None:
        """The amount of colorless mana delivered equals the countered spell's CMC."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent

        game, p1, _ = self._setup_with_wizard_and_counter(cost="{3}{U}{U}")  # CMC 5

        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent())

        assert not game.stack.is_empty()
        stack_obj = game.stack.pop()
        stack_obj.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 5

    def test_event_fires_but_without_registered_trigger_no_mana(self) -> None:
        """If Mana Sculpt was cast WITHOUT a Wizard, firing the event must not
        add any mana (no trigger was ever registered)."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # No Wizard on battlefield
        set_board_state(game, 0, battlefield=[])

        stack_obj = _push_sorcery(game, p2, p2, name="Divination", cost="{2}{U}")

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        p1.mana_pool.empty()

        # Fire the event — no trigger should be on the stack
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent())

        # Stack must remain empty
        assert game.stack.is_empty()
        # Mana pool must remain empty
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_trigger_fires_for_beginning_of_main_phase_not_other_events(self) -> None:
        """The registered trigger must respond to BeginningOfMainPhaseTriggeredEvent
        and NOT to unrelated events (e.g. BeginningOfUpkeepTriggeredEvent)."""
        from engine.events import (
            BeginningOfMainPhaseTriggeredEvent,
            BeginningOfUpkeepTriggeredEvent,
        )

        game, p1, _ = self._setup_with_wizard_and_counter(cost="{2}{U}")

        # Fire an unrelated event — should NOT push trigger
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert game.stack.is_empty(), (
            "Upkeep event must not fire the main-phase mana trigger"
        )
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

        # Now fire the correct event — should push trigger
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent())
        assert not game.stack.is_empty()

        stack_obj = game.stack.pop()
        stack_obj.on_resolve(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3
