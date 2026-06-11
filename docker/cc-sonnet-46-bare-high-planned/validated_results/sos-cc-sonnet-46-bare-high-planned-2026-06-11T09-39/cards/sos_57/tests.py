"""Tests for sos_57 — Mana Sculpt."""

from __future__ import annotations

import pytest
from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.game_state import Phase
from engine.types import ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, advance_to_phase, _resolve_top_of_stack


def _setup_counter_scenario(
    *,
    controller_index: int = 0,
    has_wizard: bool = False,
    target_cmc: int = 2,
):
    """Set up a game where ManaSculpt can counter a spell on the stack."""
    game = create_game()
    p0 = game.players[0]
    p1 = game.players[1]

    # Sculpt in p0's hand
    sculpt = ManaSculpt()
    sculpt_mana = {ManaType.BLUE: 2, ManaType.COLORLESS: 1}
    set_board_state(game, 0, hand=[sculpt], mana=sculpt_mana)

    # Optionally place a Wizard on p0's battlefield
    if has_wizard:
        wizard = Creature(
            name="Archivist",
            base_power=1,
            base_toughness=1,
            subtypes={"Wizard"},
        )
        set_board_state(game, 0, battlefield=[wizard])

    # Put a target spell on the stack for p1
    target = Instant(name="Target", mana_cost=ManaCost(generic=target_cmc))
    set_board_state(game, 1, hand=[target], mana={ManaType.COLORLESS: target_cmc})

    from engine.casting import cast_spell as _cast
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 1
    game.priority_player_index = 1
    _cast(game, p1, target)

    # Now it's p0's chance to respond — set p0 as priority holder
    game.priority_player_index = 0

    return game, sculpt, target


class TestManaSculptProperties:
    def test_name(self) -> None:
        assert ManaSculpt().name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        c = ManaSculpt()
        assert c.mana_cost.cmc == 3

    def test_is_instant(self) -> None:
        from engine.types import CardType
        assert CardType.INSTANT in ManaSculpt().card_types


class TestCounterSpell:
    def test_counters_target_spell(self) -> None:
        """Mana Sculpt removes the targeted spell from the stack."""
        game, sculpt, target = _setup_counter_scenario()
        p0 = game.players[0]
        p1 = game.players[1]

        from engine.casting import cast_spell as _cast
        # Script p0 to target the spell on stack
        p0._script.append(game.stack.peek())  # the target stack obj
        _cast(game, p0, sculpt)
        # Sculpt is now on top; pop and resolve it
        obj = game.stack.pop()
        obj.on_resolve(game)

        # Target should be in p1's graveyard, not on stack
        assert game.stack.is_empty() or all(
            item.source is not target for item in game.stack._items
        )
        assert game.get_graveyard(p1).contains(target)

    def test_countered_spell_leaves_stack(self) -> None:
        """After countering, the stack has only ManaSculpt (which also resolves)."""
        game, sculpt, target = _setup_counter_scenario()
        p0 = game.players[0]

        from engine.casting import cast_spell as _cast
        p0._script.append(game.stack.peek())
        _cast(game, p0, sculpt)
        # Stack: [target, sculpt] — sculpt on top
        sculpt_obj = game.stack.pop()
        sculpt_obj.on_resolve(game)

        # Only target should remain... but it was countered so it's gone
        assert game.stack.is_empty()


class TestNoWizardNoDelayedMana:
    def test_no_mana_without_wizard(self) -> None:
        """Without a Wizard, no delayed mana is scheduled."""
        game, sculpt, target = _setup_counter_scenario(has_wizard=False, target_cmc=3)
        p0 = game.players[0]

        from engine.casting import cast_spell as _cast
        p0._script.append(game.stack.peek())
        _cast(game, p0, sculpt)
        sculpt_obj = game.stack.pop()
        sculpt_obj.on_resolve(game)

        # Advance to next precombat main — no trigger should have fired
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        # Fire the event directly
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfPrecombatMainTriggeredEvent())
        _resolve_top_of_stack(game)

        assert p0.mana_pool.get(ManaType.COLORLESS) == 0


class TestDelayedManaWithWizard:
    def test_mana_added_at_next_main_phase(self) -> None:
        """With a Wizard, {C} equal to target's CMC is added at next main phase."""
        game, sculpt, target = _setup_counter_scenario(
            has_wizard=True, target_cmc=4
        )
        p0 = game.players[0]

        from engine.casting import cast_spell as _cast
        p0._script.append(game.stack.peek())
        _cast(game, p0, sculpt)
        sculpt_obj = game.stack.pop()
        sculpt_obj.on_resolve(game)

        # Mana pool is empty now
        p0.mana_pool.empty()

        # Simulate beginning of p0's next precombat main phase
        game.active_player_index = 0
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfPrecombatMainTriggeredEvent())
        _resolve_top_of_stack(game)

        # Should have received {C} * 4
        assert p0.mana_pool.get(ManaType.COLORLESS) == 4

    def test_delayed_mana_is_one_shot(self) -> None:
        """The delayed mana trigger fires only once."""
        game, sculpt, target = _setup_counter_scenario(
            has_wizard=True, target_cmc=2
        )
        p0 = game.players[0]

        from engine.casting import cast_spell as _cast
        p0._script.append(game.stack.peek())
        _cast(game, p0, sculpt)
        sculpt_obj = game.stack.pop()
        sculpt_obj.on_resolve(game)

        p0.mana_pool.empty()

        from engine.events import BeginningOfPrecombatMainTriggeredEvent

        # Fire once — trigger resolves and unregisters
        game.active_player_index = 0
        game.trigger_manager.fire_event(game, BeginningOfPrecombatMainTriggeredEvent())
        _resolve_top_of_stack(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 2

        p0.mana_pool.empty()

        # Fire again — trigger should be gone
        game.trigger_manager.fire_event(game, BeginningOfPrecombatMainTriggeredEvent())
        _resolve_top_of_stack(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0

    def test_delayed_mana_not_added_on_opponent_main(self) -> None:
        """Delayed mana only fires on the controller's main phase, not opponent's."""
        game, sculpt, target = _setup_counter_scenario(
            has_wizard=True, target_cmc=3
        )
        p0 = game.players[0]
        p1 = game.players[1]

        from engine.casting import cast_spell as _cast
        p0._script.append(game.stack.peek())
        _cast(game, p0, sculpt)
        sculpt_obj = game.stack.pop()
        sculpt_obj.on_resolve(game)
        p0.mana_pool.empty()

        # Fire event during p1's main phase — should not add mana to p0
        game.active_player_index = 1
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfPrecombatMainTriggeredEvent())
        _resolve_top_of_stack(game)

        assert p0.mana_pool.get(ManaType.COLORLESS) == 0
