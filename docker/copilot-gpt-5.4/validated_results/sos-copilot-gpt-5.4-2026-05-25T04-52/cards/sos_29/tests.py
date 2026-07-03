"""Tests for SOS 29 — Rehearsed Debater."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_29.card_impl import RehearsedDebater
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, TargetRequirement, Zone
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


class TestRehearsedDebaterProperties:
    """Static card data should match the SOS 29 spec."""

    def test_is_djinn_bard_creature_with_vigilance(self) -> None:
        card = RehearsedDebater(owner=None)
        assert isinstance(card, Creature)
        assert "Djinn" in card.subtypes
        assert "Bard" in card.subtypes
        assert Keyword.VIGILANCE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = RehearsedDebater(owner=None)
        assert card.name == "Rehearsed Debater"
        assert card.mana_cost == ManaCost.parse("{2}{W}")
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestRehearsedDebaterRepartee:
    """Rehearsed Debater should reward creature-targeting instants and sorceries."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RehearsedDebater(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_creature_targeting_spell_puts_a_trigger_on_the_stack_and_grants_plus_one_plus_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RehearsedDebater(owner=p1, controller=p1)
        spell_target = Creature(
            name="Study Subject",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = CreatureTargetingTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card, spell_target],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        card.register_triggers(game)
        p1._script.append(spell_target)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert card.power == 4
        assert card.toughness == 4

    def test_granted_bonus_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RehearsedDebater(owner=p1, controller=p1)
        spell_target = Creature(
            name="Study Subject",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = CreatureTargetingTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card, spell_target],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        card.register_triggers(game)
        p1._script.append(spell_target)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert card.power == 4
        assert card.toughness == 4

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert card.power == 3
        assert card.toughness == 3

    def test_spell_that_does_not_target_a_creature_does_not_trigger(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RehearsedDebater(owner=p1, controller=p1)
        spell = PlayerTargetingTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        card.register_triggers(game)
        p1._script.append(p2)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell

        resolve_top(game)

        assert card.power == 3
        assert card.toughness == 3
