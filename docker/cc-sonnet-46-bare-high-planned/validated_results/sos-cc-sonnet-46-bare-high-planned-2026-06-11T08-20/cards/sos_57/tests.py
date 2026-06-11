"""Tests for Mana Sculpt (sos_57)."""

import pytest
from test_utils import create_game, set_board_state
from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import _resolve_top_of_stack


def _setup_casting(game, player_idx=0):
    from engine.types import Phase
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = player_idx


class TestManaSculpt:
    def test_counter_removes_spell_from_stack(self):
        """Mana Sculpt counters a target spell and moves it to graveyard."""
        game = create_game()
        p1, p2 = game.players

        class TargetSpell(Instant):
            def __init__(self):
                super().__init__(name="Target", mana_cost=ManaCost.parse("{R}"))

        target = TargetSpell()
        target.owner = p2
        set_board_state(game, 1, hand=[target], mana={ManaType.RED: 2})
        _setup_casting(game, 1)
        game.active_player_index = 1

        from engine.casting import cast_spell
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        cast_spell(game, p2, target)
        # target is now on the stack

        # Switch priority to p1 to counter
        sculpt = ManaSculpt()
        sculpt.owner = p1
        set_board_state(game, 0, hand=[sculpt], mana={ManaType.BLUE: 3, ManaType.COLORLESS: 1})

        # p1 casts Mana Sculpt targeting the spell on the stack
        target_stack_obj = game.stack.peek()
        p1._script.appendleft(target_stack_obj)  # choose target

        game.active_player_index = 0
        cast_spell(game, p1, sculpt)
        _resolve_top_of_stack(game)  # resolve sculpt

        # target should be in graveyard, not stack
        assert target in p2.zones[Zone.GRAVEYARD].get_all()
        assert game.stack.is_empty() or game.stack.peek().source is not target

    def test_no_wizard_no_delayed_mana(self):
        """Without a Wizard on the battlefield, no delayed mana trigger fires."""
        game = create_game()
        p1, p2 = game.players

        class TargetSpell(Instant):
            def __init__(self):
                super().__init__(name="Target2", mana_cost=ManaCost.parse("{2}{R}"))

        target = TargetSpell()
        target.owner = p2
        set_board_state(game, 1, hand=[target], mana={ManaType.RED: 5})
        game.active_player_index = 1
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        from engine.casting import cast_spell
        cast_spell(game, p2, target)

        sculpt = ManaSculpt()
        sculpt.owner = p1
        set_board_state(game, 0, hand=[sculpt], mana={ManaType.BLUE: 3, ManaType.COLORLESS: 1})
        target_stack_obj = game.stack.peek()
        p1._script.appendleft(target_stack_obj)
        game.active_player_index = 0
        cast_spell(game, p1, sculpt)
        _resolve_top_of_stack(game)

        # No triggers for Mana Sculpt should exist (no Wizard → no delayed mana)
        triggers = game.trigger_manager.get_triggers_for_source(sculpt)
        assert len(triggers) == 0

    def test_wizard_triggers_delayed_mana(self):
        """With a Wizard, delayed mana fires at beginning of next main phase."""
        game = create_game()
        p1, p2 = game.players

        class TargetSpell(Sorcery):
            def __init__(self):
                super().__init__(name="BigSorcery", mana_cost=ManaCost.parse("{3}{R}"))

        # p1 controls a Wizard
        wizard = Creature(name="Wizard", base_power=1, base_toughness=1)
        wizard.subtypes = {"Wizard"}
        set_board_state(game, 0, battlefield=[wizard])
        wizard.controller = p1

        target = TargetSpell()
        target.owner = p2
        set_board_state(game, 1, hand=[target], mana={ManaType.RED: 5, ManaType.COLORLESS: 5})
        game.active_player_index = 1
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        from engine.casting import cast_spell
        cast_spell(game, p2, target)

        sculpt = ManaSculpt()
        sculpt.owner = p1
        set_board_state(game, 0, hand=[sculpt], mana={ManaType.BLUE: 3, ManaType.COLORLESS: 1})
        wizard.controller = p1  # restore after set_board_state
        target_stack_obj = game.stack.peek()
        mana_spent = target_stack_obj.mana_spent_total
        p1._script.appendleft(target_stack_obj)

        game.active_player_index = 0
        cast_spell(game, p1, sculpt)
        _resolve_top_of_stack(game)

        # Should have a delayed trigger registered
        triggers = game.trigger_manager.get_triggers_for_source(sculpt)
        assert len(triggers) == 1

        # Simulate beginning of p1's next main phase
        from engine.events import BeginningOfPrecombatMainTriggeredEvent
        game.active_player_index = 0
        game.trigger_manager.fire_event(game, BeginningOfPrecombatMainTriggeredEvent())

        # Delayed trigger is now on the stack
        mana_before = p1.mana_pool.get(ManaType.COLORLESS)
        _resolve_top_of_stack(game)

        # Mana added equals mana spent on the countered spell
        assert p1.mana_pool.get(ManaType.COLORLESS) == mana_before + mana_spent
        assert mana_spent > 0

        # Trigger should be unregistered (one-shot)
        triggers = game.trigger_manager.get_triggers_for_source(sculpt)
        assert len(triggers) == 0

    def test_mana_spent_total_recorded(self):
        """mana_spent_total is recorded on the StackObject at cast time."""
        game = create_game()
        p1 = game.players[0]

        class ThreeManaInstant(Instant):
            def __init__(self):
                super().__init__(name="ThrMana", mana_cost=ManaCost.parse("{2}{U}"))

        spell = ThreeManaInstant()
        spell.owner = p1
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 3, ManaType.COLORLESS: 2})
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        from engine.casting import cast_spell
        cast_spell(game, p1, spell)
        stack_obj = game.stack.peek()
        assert getattr(stack_obj, "mana_spent_total", None) == 3  # {2}{U} = 3
