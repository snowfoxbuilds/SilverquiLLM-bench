"""Tests for SOS 16 — Graduation Day."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_16.card_impl import GraduationDay
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Enchantment, Instant
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CreatureTargetingTestInstant(Instant):
    """Simple instant used to exercise repartee-style triggers."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Creature Targeting Test Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        super().__init__(**kwargs)

    def get_targets(self, game: object) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]


class PlayerTargetingTestInstant(Instant):
    """Instant that targets a player so repartee should not trigger."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Player Targeting Test Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        super().__init__(**kwargs)

    def get_targets(self, game: object) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]


class TestGraduationDayProperties:
    """Static card data should match the SOS 16 spec."""

    def test_is_enchantment(self) -> None:
        assert isinstance(GraduationDay(owner=None), Enchantment)

    def test_name_and_mana_cost(self) -> None:
        card = GraduationDay(owner=None)
        assert card.name == "Graduation Day"
        assert card.mana_cost == ManaCost.parse("{W}")


class TestGraduationDayRepartee:
    """Graduation Day should reward creature-targeting instants and sorceries."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GraduationDay(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_casting_a_creature_targeting_instant_puts_trigger_on_stack_and_adds_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        enchantment = GraduationDay(owner=p1, controller=p1)
        spell_target = Creature(
            name="Spell Target",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        reward_target = Creature(
            name="Reward Target",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = CreatureTargetingTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[enchantment, spell_target, reward_target],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        enchantment.register_triggers(game)
        p1._script.extend([spell_target, reward_target])

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is enchantment

        resolve_top(game)

        assert reward_target.plus_one_counters == 1
        assert game.stack.peek().source is spell

        resolve_top(game)

        assert game.get_graveyard(p1).contains(spell)

    def test_spell_that_does_not_target_a_creature_does_not_trigger(self) -> None:
        game = create_game()
        p1, p2 = game.players
        enchantment = GraduationDay(owner=p1, controller=p1)
        your_creature = Creature(
            name="Helpful Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = PlayerTargetingTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[enchantment, your_creature],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        enchantment.register_triggers(game)
        p1._script.append(p2)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell

        resolve_top(game)

        assert your_creature.plus_one_counters == 0

