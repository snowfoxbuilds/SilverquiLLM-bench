"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spell_on_stack(game: Any, player: Any, cmc: int) -> StackObject:
    """Put a simple dummy spell on the stack with the given CMC."""
    card = Instant(
        name=f"DummySpell_{cmc}",
        mana_cost=ManaCost(generic=cmc),
        owner=player,
        controller=player,
    )
    stack_obj = StackObject(source=card, controller=player, on_resolve=lambda g: None)
    game.stack.push(stack_obj)
    # Track it in the player's stack zone too
    player.zones[Zone.STACK].add(card)
    return stack_obj


def _make_wizard(owner: Any) -> Creature:
    """Create a minimal Wizard creature."""
    return Creature(
        name="Test Wizard",
        subtypes={"Wizard"},
        base_power=1,
        base_toughness=1,
        owner=owner,
        controller=owner,
    )


# ---------------------------------------------------------------------------
# Card identity
# ---------------------------------------------------------------------------


class TestManaSculptIdentity:
    def test_name(self) -> None:
        card = ManaSculpt()
        assert card.name == "Mana Sculpt"

    def test_type_is_instant(self) -> None:
        card = ManaSculpt()
        assert CardType.INSTANT in card.card_types

    def test_mana_cost(self) -> None:
        card = ManaSculpt()
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_cmc(self) -> None:
        card = ManaSculpt()
        assert card.mana_cost.cmc == 3


# ---------------------------------------------------------------------------
# Countering a spell
# ---------------------------------------------------------------------------


class TestManaSculptCounter:
    def test_countered_spell_moves_to_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        sculpt = ManaSculpt(owner=p1, controller=p1)
        target = _make_spell_on_stack(game, p2, cmc=3)

        sculpt.chosen_targets = [target]
        sculpt.on_resolve(game)

        # Spell card should be in owner's graveyard
        source_card = target.source
        gy = game.get_graveyard(p2)
        assert gy.contains(source_card)

    def test_countered_spell_removed_from_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        sculpt = ManaSculpt(owner=p1, controller=p1)
        target = _make_spell_on_stack(game, p2, cmc=2)

        sculpt.chosen_targets = [target]
        sculpt.on_resolve(game)

        assert game.stack.is_empty()

    def test_no_target_is_noop(self) -> None:
        """If no target (e.g. fizzle), resolve does nothing."""
        game = create_game()
        p1 = game.players[0]

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = []

        # Should not raise
        sculpt.on_resolve(game)


# ---------------------------------------------------------------------------
# Wizard condition — mana refund
# ---------------------------------------------------------------------------


class TestManaSculptWizardCondition:
    def test_no_wizard_no_mana_trigger_registered(self) -> None:
        """Without a Wizard, no delayed trigger is registered."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        sculpt = ManaSculpt(owner=p1, controller=p1)
        target = _make_spell_on_stack(game, p2, cmc=3)

        before_trigger_count = len(game.trigger_manager.get_triggers())
        sculpt.chosen_targets = [target]
        sculpt.on_resolve(game)

        assert len(game.trigger_manager.get_triggers()) == before_trigger_count

    def test_with_wizard_trigger_registered(self) -> None:
        """With a Wizard, a delayed trigger is registered."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(p1)
        set_board_state(game, 0, battlefield=[wizard])

        sculpt = ManaSculpt(owner=p1, controller=p1)
        target = _make_spell_on_stack(game, p2, cmc=3)

        before_trigger_count = len(game.trigger_manager.get_triggers())
        sculpt.chosen_targets = [target]
        sculpt.on_resolve(game)

        assert len(game.trigger_manager.get_triggers()) > before_trigger_count

    def test_with_wizard_mana_added_on_main_phase(self) -> None:
        """With a Wizard, mana equal to CMC is added at beginning of next main phase."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.types import Phase

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(p1)
        set_board_state(game, 0, battlefield=[wizard])

        sculpt = ManaSculpt(owner=p1, controller=p1)
        target = _make_spell_on_stack(game, p2, cmc=4)

        sculpt.chosen_targets = [target]
        sculpt.on_resolve(game)

        # Simulate beginning of p1's next main phase
        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.PRECOMBAT_MAIN),
        )

        # Resolve the trigger from the stack
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert p1.mana_pool._pool.get(ManaType.COLORLESS, 0) == 4

    def test_with_wizard_cmc_5_mana_added(self) -> None:
        """Mana refund matches CMC of the countered spell."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.types import Phase

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(p1)
        set_board_state(game, 0, battlefield=[wizard])

        sculpt = ManaSculpt(owner=p1, controller=p1)
        target = _make_spell_on_stack(game, p2, cmc=5)

        sculpt.chosen_targets = [target]
        sculpt.on_resolve(game)

        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.PRECOMBAT_MAIN),
        )

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert p1.mana_pool._pool.get(ManaType.COLORLESS, 0) == 5

    def test_trigger_only_fires_for_controllers_main_phase(self) -> None:
        """The delayed trigger should not fire during opponent's main phase."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.types import Phase

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(p1)
        set_board_state(game, 0, battlefield=[wizard])

        sculpt = ManaSculpt(owner=p1, controller=p1)
        target = _make_spell_on_stack(game, p2, cmc=3)

        sculpt.chosen_targets = [target]
        sculpt.on_resolve(game)

        # Simulate opponent's main phase — trigger should not fire
        game.active_player_index = 1
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p2, phase=Phase.PRECOMBAT_MAIN),
        )

        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert p1.mana_pool._pool.get(ManaType.COLORLESS, 0) == 0

    def test_trigger_fires_only_once(self) -> None:
        """The delayed trigger is a one-shot — it should not fire twice."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.types import Phase

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(p1)
        set_board_state(game, 0, battlefield=[wizard])

        sculpt = ManaSculpt(owner=p1, controller=p1)
        target = _make_spell_on_stack(game, p2, cmc=2)

        sculpt.chosen_targets = [target]
        sculpt.on_resolve(game)

        # Fire twice
        for _ in range(2):
            game.active_player_index = 0
            game.trigger_manager.fire_event(
                game,
                BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.PRECOMBAT_MAIN),
            )
            while not game.stack.is_empty():
                obj = game.stack.pop()
                obj.on_resolve(game)

        # Mana should only be 2, not 4
        assert p1.mana_pool._pool.get(ManaType.COLORLESS, 0) == 2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestManaSculptEdgeCases:
    def test_zero_cmc_spell_no_trigger_registered(self) -> None:
        """Countering a 0-CMC spell with a Wizard does not register a trigger."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(p1)
        set_board_state(game, 0, battlefield=[wizard])

        sculpt = ManaSculpt(owner=p1, controller=p1)
        target = _make_spell_on_stack(game, p2, cmc=0)

        before_trigger_count = len(game.trigger_manager.get_triggers())
        sculpt.chosen_targets = [target]
        sculpt.on_resolve(game)

        assert len(game.trigger_manager.get_triggers()) == before_trigger_count

    def test_zero_cmc_spell_no_mana_added(self) -> None:
        """Countering a 0-CMC spell gives 0 mana even with a Wizard."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.types import Phase

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = _make_wizard(p1)
        set_board_state(game, 0, battlefield=[wizard])

        sculpt = ManaSculpt(owner=p1, controller=p1)
        target = _make_spell_on_stack(game, p2, cmc=0)

        sculpt.chosen_targets = [target]
        sculpt.on_resolve(game)

        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.PRECOMBAT_MAIN),
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        assert p1.mana_pool._pool.get(ManaType.COLORLESS, 0) == 0
