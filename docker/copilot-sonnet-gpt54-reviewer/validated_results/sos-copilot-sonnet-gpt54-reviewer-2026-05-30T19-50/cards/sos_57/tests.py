"""Tests for Mana Sculpt (SOS #57)."""

from __future__ import annotations

import pytest

from test_utils import create_game, set_board_state
from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wizard(name: str = "Merfolk Wizard") -> Creature:
    return Creature(
        name=name,
        subtypes={"Merfolk", "Wizard"},
        base_power=2,
        base_toughness=2,
    )


def _make_target_spell(cmc: int = 3, owner=None) -> tuple[Instant, StackObject]:
    """Create an Instant and a corresponding StackObject to place on the stack."""
    card = Instant(
        name="Test Spell",
        mana_cost=ManaCost(generic=cmc),
        owner=owner,
    )
    so = StackObject(
        source=card,
        controller=owner,
    )
    return card, so


def _resolve_stack(game) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


# ---------------------------------------------------------------------------
# Card attribute tests
# ---------------------------------------------------------------------------

class TestManaSculptAttributes:
    def test_name(self) -> None:
        card = ManaSculpt()
        assert card.name == "Mana Sculpt"

    def test_is_instant(self) -> None:
        card = ManaSculpt()
        assert CardType.INSTANT in card.card_types

    def test_mana_cost(self) -> None:
        card = ManaSculpt()
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_mana_cost_cmc(self) -> None:
        card = ManaSculpt()
        assert card.mana_cost.cmc == 3


# ---------------------------------------------------------------------------
# Counter effect tests
# ---------------------------------------------------------------------------

class TestManaSculptCounterEffect:
    def test_target_spell_removed_from_stack(self) -> None:
        """The targeted spell must be removed from the stack on resolve."""
        game = create_game()
        player = game.players[1]  # opponent's spell
        target_card, target_so = _make_target_spell(cmc=3, owner=player)
        target_so.controller = player
        game.stack.push(target_so)
        assert len(game.stack) == 1

        sculpt = ManaSculpt(owner=game.players[0], controller=game.players[0])
        sculpt.chosen_targets = [target_so]
        sculpt.on_resolve(game)

        assert len(game.stack) == 0

    def test_countered_spell_goes_to_owner_graveyard(self) -> None:
        """Countered spell moves to the owner's graveyard."""
        game = create_game()
        player = game.players[1]
        target_card, target_so = _make_target_spell(cmc=2, owner=player)
        target_so.controller = player
        game.stack.push(target_so)

        sculpt = ManaSculpt(owner=game.players[0], controller=game.players[0])
        sculpt.chosen_targets = [target_so]
        sculpt.on_resolve(game)

        gy = game.get_graveyard(player)
        assert gy.contains(target_card)

    def test_no_targets_is_noop(self) -> None:
        """Resolving with no chosen targets does nothing."""
        game = create_game()
        sculpt = ManaSculpt(owner=game.players[0], controller=game.players[0])
        sculpt.chosen_targets = []
        sculpt.on_resolve(game)  # should not raise

    def test_stack_not_in_stack_still_moves_to_graveyard(self) -> None:
        """If target already left the stack, it still goes to graveyard."""
        game = create_game()
        player = game.players[1]
        target_card, target_so = _make_target_spell(cmc=2, owner=player)
        target_so.controller = player
        # Do NOT push target_so onto the stack

        sculpt = ManaSculpt(owner=game.players[0], controller=game.players[0])
        sculpt.chosen_targets = [target_so]
        sculpt.on_resolve(game)

        gy = game.get_graveyard(player)
        assert gy.contains(target_card)


# ---------------------------------------------------------------------------
# Wizard condition — no mana without Wizard
# ---------------------------------------------------------------------------

class TestManaSculptNoWizard:
    def test_no_mana_added_without_wizard(self) -> None:
        """Mana trigger must NOT register if controller has no Wizard."""
        game = create_game()
        player0 = game.players[0]
        player1 = game.players[1]

        target_card, target_so = _make_target_spell(cmc=4, owner=player1)
        target_so.controller = player1
        game.stack.push(target_so)

        sculpt = ManaSculpt(owner=player0, controller=player0)
        sculpt.chosen_targets = [target_so]
        sculpt.on_resolve(game)

        # No Wizard on player0's battlefield → no pending triggers for main phase.
        trigger_count_before = len(game.trigger_manager.get_triggers())
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=player0)
        )
        _resolve_stack(game)

        assert player0.mana_pool.get(ManaType.COLORLESS) == 0

    def test_wizard_on_opponent_battlefield_does_not_count(self) -> None:
        """A Wizard controlled by the opponent must not satisfy the condition."""
        game = create_game()
        player0 = game.players[0]
        player1 = game.players[1]

        wizard = _make_wizard()
        wizard.owner = player1
        wizard.controller = player1
        set_board_state(game, 1, battlefield=[wizard])

        target_card, target_so = _make_target_spell(cmc=3, owner=player1)
        target_so.controller = player1
        game.stack.push(target_so)

        sculpt = ManaSculpt(owner=player0, controller=player0)
        sculpt.chosen_targets = [target_so]
        sculpt.on_resolve(game)

        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=player0)
        )
        _resolve_stack(game)

        assert player0.mana_pool.get(ManaType.COLORLESS) == 0


# ---------------------------------------------------------------------------
# Wizard condition — mana IS added with Wizard
# ---------------------------------------------------------------------------

class TestManaSculptWithWizard:
    def test_mana_added_equals_countered_spell_cmc(self) -> None:
        """{C} added equals the CMC of the countered spell."""
        game = create_game()
        player0 = game.players[0]
        player1 = game.players[1]

        wizard = _make_wizard()
        wizard.owner = player0
        wizard.controller = player0
        set_board_state(game, 0, battlefield=[wizard])

        cmc = 5
        target_card, target_so = _make_target_spell(cmc=cmc, owner=player1)
        target_so.controller = player1
        game.stack.push(target_so)

        sculpt = ManaSculpt(owner=player0, controller=player0)
        sculpt.chosen_targets = [target_so]
        sculpt.on_resolve(game)

        # Simulate beginning of player0's main phase.
        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=player0)
        )
        _resolve_stack(game)

        assert player0.mana_pool.get(ManaType.COLORLESS) == cmc

    def test_mana_is_colorless_not_colored(self) -> None:
        """The mana added is colorless {C}, not any colored mana."""
        game = create_game()
        player0 = game.players[0]
        player1 = game.players[1]

        wizard = _make_wizard()
        wizard.owner = player0
        wizard.controller = player0
        set_board_state(game, 0, battlefield=[wizard])

        target_card, target_so = _make_target_spell(cmc=3, owner=player1)
        target_so.controller = player1
        game.stack.push(target_so)

        sculpt = ManaSculpt(owner=player0, controller=player0)
        sculpt.chosen_targets = [target_so]
        sculpt.on_resolve(game)

        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=player0)
        )
        _resolve_stack(game)

        # Colorless should be 3, all other types 0.
        assert player0.mana_pool.get(ManaType.COLORLESS) == 3
        assert player0.mana_pool.get(ManaType.BLUE) == 0
        assert player0.mana_pool.get(ManaType.WHITE) == 0
        assert player0.mana_pool.get(ManaType.RED) == 0
        assert player0.mana_pool.get(ManaType.GREEN) == 0
        assert player0.mana_pool.get(ManaType.BLACK) == 0

    def test_trigger_only_fires_once(self) -> None:
        """The mana trigger is one-shot — it must not fire a second time."""
        game = create_game()
        player0 = game.players[0]
        player1 = game.players[1]

        wizard = _make_wizard()
        wizard.owner = player0
        wizard.controller = player0
        set_board_state(game, 0, battlefield=[wizard])

        target_card, target_so = _make_target_spell(cmc=4, owner=player1)
        target_so.controller = player1
        game.stack.push(target_so)

        sculpt = ManaSculpt(owner=player0, controller=player0)
        sculpt.chosen_targets = [target_so]
        sculpt.on_resolve(game)

        game.active_player_index = 0
        # First main phase — trigger fires.
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=player0)
        )
        _resolve_stack(game)
        assert player0.mana_pool.get(ManaType.COLORLESS) == 4

        # Manually drain the pool to test second firing.
        player0.mana_pool.empty()

        # Second main phase — trigger should NOT fire again.
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=player0)
        )
        _resolve_stack(game)
        assert player0.mana_pool.get(ManaType.COLORLESS) == 0

    def test_mana_not_added_before_main_phase_event(self) -> None:
        """Mana is not added immediately on resolution — only at main phase."""
        game = create_game()
        player0 = game.players[0]
        player1 = game.players[1]

        wizard = _make_wizard()
        wizard.owner = player0
        wizard.controller = player0
        set_board_state(game, 0, battlefield=[wizard])

        target_card, target_so = _make_target_spell(cmc=3, owner=player1)
        target_so.controller = player1
        game.stack.push(target_so)

        sculpt = ManaSculpt(owner=player0, controller=player0)
        sculpt.chosen_targets = [target_so]
        sculpt.on_resolve(game)

        # No main phase event fired yet.
        assert player0.mana_pool.get(ManaType.COLORLESS) == 0

    def test_opponent_main_phase_does_not_give_mana(self) -> None:
        """The mana trigger only fires during the controller's own main phase."""
        game = create_game()
        player0 = game.players[0]
        player1 = game.players[1]

        wizard = _make_wizard()
        wizard.owner = player0
        wizard.controller = player0
        set_board_state(game, 0, battlefield=[wizard])

        target_card, target_so = _make_target_spell(cmc=3, owner=player1)
        target_so.controller = player1
        game.stack.push(target_so)

        sculpt = ManaSculpt(owner=player0, controller=player0)
        sculpt.chosen_targets = [target_so]
        sculpt.on_resolve(game)

        # Simulate opponent's main phase (player1 is active).
        game.active_player_index = 1
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=player1)
        )
        _resolve_stack(game)

        # player0 should have received no mana.
        assert player0.mana_pool.get(ManaType.COLORLESS) == 0

        # Now simulate player0's main phase — should fire.
        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=player0)
        )
        _resolve_stack(game)
        assert player0.mana_pool.get(ManaType.COLORLESS) == 3

    def test_cmc_zero_no_mana_even_with_wizard(self) -> None:
        """A countered spell with CMC 0 adds no mana (nothing to give)."""
        game = create_game()
        player0 = game.players[0]
        player1 = game.players[1]

        wizard = _make_wizard()
        wizard.owner = player0
        wizard.controller = player0
        set_board_state(game, 0, battlefield=[wizard])

        target_card, target_so = _make_target_spell(cmc=0, owner=player1)
        target_so.controller = player1
        game.stack.push(target_so)

        sculpt = ManaSculpt(owner=player0, controller=player0)
        sculpt.chosen_targets = [target_so]
        sculpt.on_resolve(game)

        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=player0)
        )
        _resolve_stack(game)
        assert player0.mana_pool.get(ManaType.COLORLESS) == 0
