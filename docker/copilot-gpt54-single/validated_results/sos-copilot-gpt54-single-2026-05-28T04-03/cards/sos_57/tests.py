"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import CardImpl, Creature, Instant
from engine.casting import cast_spell as engine_cast_spell
from engine.stack import StackObject
from engine.types import ManaCost, ManaType, Phase, Step, TargetRequirement, Zone
from test_utils import advance_to_phase, create_game, fire_beginning_of_main_phase, set_board_state


def _wizard() -> Creature:
    return Creature(
        name="Academy Wizard",
        subtypes={"Wizard"},
        base_power=1,
        base_toughness=3,
    )


def _put_game_in_combat(game) -> None:
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.COMBAT
    game.step = Step.BEGIN_COMBAT


class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_is_an_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")


class TestManaSculptTargeting:
    """Mana Sculpt should only be castable when it can target a spell."""

    def test_can_cast_is_false_when_no_spell_is_on_the_stack(self) -> None:
        game = create_game()

        assert ManaSculpt(owner=None).can_cast(game) is False

    def test_get_targets_returns_one_stack_spell_requirement(self) -> None:
        game = create_game()
        opponent = game.players[1]
        spell = Instant(name="Lightning Burst", owner=opponent, controller=opponent)
        spell_obj = StackObject(source=spell, controller=opponent)
        game.stack.push(spell_obj)

        reqs = ManaSculpt(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.STACK
        assert reqs[0].filter_fn(spell_obj) is True
        assert reqs[0].filter_fn(CardImpl(name="Not a spell")) is False


class TestManaSculptResolution:
    """Mana Sculpt should counter its target and only set up delayed mana later."""

    def test_on_resolve_without_a_chosen_target_is_a_noop(self) -> None:
        game = create_game()
        caster = game.players[0]
        spell = ManaSculpt(owner=caster, controller=caster)

        spell.on_resolve(game)

        assert caster.mana_pool.total() == 0
        assert len(game.trigger_manager.get_triggers()) == 0

    def test_resolve_counters_the_targeted_spell(self) -> None:
        game = create_game()
        caster = game.players[0]
        opponent = game.players[1]
        target_spell = Instant(
            name="Volcanic Riposte",
            mana_cost=ManaCost.parse("{2}{R}"),
            owner=opponent,
            controller=opponent,
        )
        target_obj = StackObject(source=target_spell, controller=opponent)
        opponent.zones[Zone.STACK].add(target_spell)
        game.stack.push(target_obj)

        spell = ManaSculpt(owner=caster, controller=caster)
        spell.chosen_targets = [target_obj]

        spell.on_resolve(game)

        assert game.stack.is_empty()
        assert opponent.zones[Zone.GRAVEYARD].contains(target_spell)
        assert not opponent.zones[Zone.STACK].contains(target_spell)


class TestManaSculptDelayedManaSetup:
    """The Wizard clause should create delayed mana, not immediate mana."""

    def test_resolving_with_a_wizard_registers_one_delayed_trigger_and_adds_no_mana_immediately(self) -> None:
        game = create_game()
        caster = game.players[0]
        opponent = game.players[1]
        mana_sculpt = ManaSculpt(owner=caster, controller=caster)
        target_spell = Instant(
            name="Volcanic Riposte",
            mana_cost=ManaCost.parse("{2}{R}"),
        )
        _put_game_in_combat(game)
        set_board_state(
            game,
            0,
            battlefield=[_wizard()],
            hand=[mana_sculpt],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        set_board_state(
            game,
            1,
            hand=[target_spell],
            mana={ManaType.RED: 1, ManaType.COLORLESS: 2},
        )

        engine_cast_spell(game, opponent, target_spell)
        target_obj = game.stack.peek()
        assert target_obj is not None
        caster.choose_target = lambda options, requirement: target_obj
        before = len(game.trigger_manager.get_triggers())

        engine_cast_spell(game, caster, mana_sculpt)
        game.stack.pop().on_resolve(game)

        assert game.stack.is_empty()
        assert opponent.zones[Zone.GRAVEYARD].contains(target_spell)
        assert len(game.trigger_manager.get_triggers()) == before + 1
        assert caster.mana_pool.total() == 0

    def test_delayed_trigger_adds_colorless_equal_to_mana_spent_at_next_main_phase(self) -> None:
        game = create_game()
        caster = game.players[0]
        opponent = game.players[1]
        mana_sculpt = ManaSculpt(owner=caster, controller=caster)
        target_spell = Instant(
            name="Volcanic Riposte",
            mana_cost=ManaCost.parse("{2}{R}"),
        )
        _put_game_in_combat(game)
        set_board_state(
            game,
            0,
            battlefield=[_wizard()],
            hand=[mana_sculpt],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        set_board_state(
            game,
            1,
            hand=[target_spell],
            mana={ManaType.RED: 1, ManaType.COLORLESS: 2},
        )

        engine_cast_spell(game, opponent, target_spell)
        target_obj = game.stack.peek()
        assert target_obj is not None
        caster.choose_target = lambda options, requirement: target_obj
        before = len(game.trigger_manager.get_triggers())

        engine_cast_spell(game, caster, mana_sculpt)
        game.stack.pop().on_resolve(game)

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        assert caster.mana_pool.total() == 0

        fire_beginning_of_main_phase(game)

        delayed_obj = game.stack.peek()
        assert delayed_obj is not None
        game.stack.pop().on_resolve(game)

        assert caster.mana_pool.get(ManaType.COLORLESS) == 3
        assert caster.mana_pool.total() == 3
        assert len(game.trigger_manager.get_triggers()) == before

    def test_resolving_without_a_wizard_registers_no_delayed_trigger(self) -> None:
        game = create_game()
        caster = game.players[0]
        opponent = game.players[1]
        mana_sculpt = ManaSculpt(owner=caster, controller=caster)
        target_spell = Instant(
            name="Volcanic Riposte",
            mana_cost=ManaCost.parse("{2}{R}"),
        )
        _put_game_in_combat(game)
        set_board_state(
            game,
            0,
            hand=[mana_sculpt],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        set_board_state(
            game,
            1,
            hand=[target_spell],
            mana={ManaType.RED: 1, ManaType.COLORLESS: 2},
        )

        engine_cast_spell(game, opponent, target_spell)
        target_obj = game.stack.peek()
        assert target_obj is not None
        caster.choose_target = lambda options, requirement: target_obj
        before = len(game.trigger_manager.get_triggers())

        engine_cast_spell(game, caster, mana_sculpt)
        game.stack.pop().on_resolve(game)

        assert game.stack.is_empty()
        assert opponent.zones[Zone.GRAVEYARD].contains(target_spell)
        assert len(game.trigger_manager.get_triggers()) == before
        assert caster.mana_pool.total() == 0
