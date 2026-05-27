"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.casting import cast_spell as engine_cast_spell
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Phase, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state


class TestTargetSpell(Instant):
    """Simple instant used as a counterspell target in Mana Sculpt tests."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Target Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        super().__init__(**kwargs)
        self.resolved = False

    def on_resolve(self, game) -> None:
        self.resolved = True


class ReducedCostTargetSpell(TestTargetSpell):
    """Target spell with a generic cost reduction for paid-mana tests."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Reduced Target Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}"))
        super().__init__(**kwargs)

    def cost_reduction(self, game) -> int:
        return 4


class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_is_instant_with_expected_cost_and_rules_text(self) -> None:
        card = ManaSculpt(owner=None)
        assert isinstance(card, Instant)
        assert card.name == "Mana Sculpt"
        assert CardType.INSTANT in card.card_types
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")
        assert card.rules_text == (
            "Counter target spell. If you control a Wizard, add an amount of {C} "
            "equal to the amount of mana spent to cast that spell at the "
            "beginning of your next main phase."
        )


class TestManaSculptTargeting:
    """Mana Sculpt should only be castable with a spell target on the stack."""

    def test_cannot_be_cast_with_no_spell_on_stack(self) -> None:
        game = create_game()
        assert ManaSculpt(owner=None).can_cast(game) is False

    def test_can_be_cast_when_a_spell_is_on_the_stack(self) -> None:
        game = create_game()
        p2 = game.players[1]
        target_spell = TestTargetSpell(owner=p2, controller=p2)

        set_board_state(game, 1, hand=[target_spell], mana={ManaType.RED: 3})
        engine_cast_spell(game, p2, target_spell)

        assert ManaSculpt(owner=None).can_cast(game) is True

    def test_returns_single_stack_target_requirement_for_spells(self) -> None:
        game = create_game()
        p2 = game.players[1]
        target_spell = TestTargetSpell(owner=p2, controller=p2)
        set_board_state(game, 1, hand=[target_spell], mana={ManaType.RED: 3})
        engine_cast_spell(game, p2, target_spell)

        reqs = ManaSculpt(owner=None).get_targets(game)
        spell_obj = StackObject(
            source=TestTargetSpell(owner=game.players[0], controller=game.players[0]),
            controller=game.players[0],
        )
        ability_obj = StackObject(source=None, controller=game.players[0])
        ability_obj.is_spell = False

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.STACK
        assert reqs[0].filter_fn(spell_obj) is True
        assert reqs[0].filter_fn(ability_obj) is False


class TestManaSculptResolution:
    """Mana Sculpt should counter the chosen spell and conditionally delay mana."""

    def test_counters_target_spell_and_puts_it_into_its_owners_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target_spell = TestTargetSpell(owner=p2, controller=p2)
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)

        set_board_state(game, 0, hand=[mana_sculpt], mana={ManaType.BLUE: 3})
        set_board_state(game, 1, hand=[target_spell], mana={ManaType.RED: 3})

        engine_cast_spell(game, p2, target_spell)
        target_obj = game.stack.peek()
        assert target_obj is not None

        cast_spell(game, 0, "Mana Sculpt", targets=[target_obj])

        assert game.stack.is_empty()
        assert target_spell.resolved is False
        assert p2.zones[Zone.GRAVEYARD].contains(target_spell)
        assert not p2.zones[Zone.STACK].contains(target_spell)
        assert p1.zones[Zone.GRAVEYARD].contains(mana_sculpt)

    def test_wizard_control_delays_colorless_mana_until_your_next_main_phase(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        wizard = Creature(
            name="Test Wizard",
            owner=p1,
            controller=p1,
            subtypes={"Wizard"},
            base_power=1,
            base_toughness=1,
        )
        target_spell = TestTargetSpell(owner=p2, controller=p2)
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)

        game.active_player_index = 1
        game.priority_player_index = 1
        set_board_state(
            game,
            0,
            battlefield=[wizard],
            hand=[mana_sculpt],
            mana={ManaType.BLUE: 3},
        )
        set_board_state(game, 1, hand=[target_spell], mana={ManaType.RED: 3})

        engine_cast_spell(game, p2, target_spell)
        target_obj = game.stack.peek()
        assert target_obj is not None

        cast_spell(game, 0, "Mana Sculpt", targets=[target_obj])

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 1
        game.priority_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent())

        assert game.stack.is_empty()
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

        game.active_player_index = 0
        game.priority_player_index = 0
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent())

        assert not game.stack.is_empty()
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_records_actual_paid_mana_on_the_target_spell_public_surfaces(self) -> None:
        game = create_game()
        p2 = game.players[1]
        target_spell = ReducedCostTargetSpell(owner=p2, controller=p2)

        set_board_state(game, 1, hand=[target_spell], mana={ManaType.RED: 2})

        engine_cast_spell(game, p2, target_spell)
        target_obj = game.stack.peek()

        assert target_obj is not None
        assert target_spell.mana_spent_to_cast == 2
        assert target_obj.mana_spent_to_cast == 2
        assert target_obj.total_mana_spent_to_cast == 2

    def test_wizard_mana_uses_actual_paid_mana_when_target_cost_was_reduced(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        wizard = Creature(
            name="Test Wizard",
            owner=p1,
            controller=p1,
            subtypes={"Wizard"},
            base_power=1,
            base_toughness=1,
        )
        target_spell = ReducedCostTargetSpell(owner=p2, controller=p2)
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)

        game.active_player_index = 1
        game.priority_player_index = 1
        set_board_state(
            game,
            0,
            battlefield=[wizard],
            hand=[mana_sculpt],
            mana={ManaType.BLUE: 3},
        )
        set_board_state(game, 1, hand=[target_spell], mana={ManaType.RED: 2})

        engine_cast_spell(game, p2, target_spell)
        target_obj = game.stack.peek()

        assert target_obj is not None
        assert target_obj.total_mana_spent_to_cast == 2

        cast_spell(game, 0, "Mana Sculpt", targets=[target_obj])

        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.priority_player_index = 0
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent())

        assert not game.stack.is_empty()
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 2

    def test_opponents_wizard_does_not_enable_delayed_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        opponents_wizard = Creature(
            name="Enemy Wizard",
            owner=p2,
            controller=p2,
            subtypes={"Wizard"},
            base_power=1,
            base_toughness=1,
        )
        target_spell = TestTargetSpell(owner=p2, controller=p2)
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)

        game.active_player_index = 1
        game.priority_player_index = 1
        set_board_state(game, 0, hand=[mana_sculpt], mana={ManaType.BLUE: 3})
        set_board_state(
            game,
            1,
            battlefield=[opponents_wizard],
            hand=[target_spell],
            mana={ManaType.RED: 3},
        )

        engine_cast_spell(game, p2, target_spell)
        target_obj = game.stack.peek()
        assert target_obj is not None

        cast_spell(game, 0, "Mana Sculpt", targets=[target_obj])

        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.priority_player_index = 0
        game.trigger_manager.fire_event(game, BeginningOfMainPhaseTriggeredEvent())

        assert game.stack.is_empty()
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
