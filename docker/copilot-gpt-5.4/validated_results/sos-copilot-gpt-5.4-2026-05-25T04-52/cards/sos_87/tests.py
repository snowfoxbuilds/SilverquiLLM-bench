"""Tests for SOS 87 — Lecturing Scornmage."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_87.card_impl import LecturingScornmage
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CreatureTargetingTestInstant(Instant):
    """Simple instant used to exercise repartee-style triggers."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Creature Targeting Test Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        super().__init__(**kwargs)

    def get_targets(self, game: object) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]


class CreatureTargetingTestSorcery(Sorcery):
    """Simple sorcery used to exercise repartee-style triggers."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Creature Targeting Test Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
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
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        super().__init__(**kwargs)

    def get_targets(self, game: object) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]


class TestLecturingScornmageProperties:
    """Static card data should match the SOS 87 spec."""

    def test_is_human_warlock_creature(self) -> None:
        card = LecturingScornmage(owner=None)
        assert isinstance(card, Creature)
        assert "Human" in card.subtypes
        assert "Warlock" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = LecturingScornmage(owner=None)
        assert card.name == "Lecturing Scornmage"
        assert card.mana_cost == ManaCost.parse("{B}")
        assert card.base_power == 1
        assert card.base_toughness == 1


class TestLecturingScornmageRepartee:
    """Lecturing Scornmage should grow from creature-targeting spells."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LecturingScornmage(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_creature_targeting_instant_puts_trigger_on_stack_and_adds_a_plus_one_counter(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LecturingScornmage(owner=p1, controller=p1)
        spell_target = Creature(
            name="Opposing Assistant",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        spell = CreatureTargetingTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )
        set_board_state(game, 1, battlefield=[spell_target])
        card.register_triggers(game)
        p1._script.append(spell_target)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert card.plus_one_counters == 1

    def test_creature_targeting_sorcery_also_puts_trigger_on_stack_and_adds_a_plus_one_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        card = LecturingScornmage(owner=p1, controller=p1)
        spell_target = Creature(
            name="Study Subject",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = CreatureTargetingTestSorcery(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card, spell_target],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )
        card.register_triggers(game)
        p1._script.append(spell_target)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert card.plus_one_counters == 1

    def test_spell_that_targets_a_player_does_not_trigger(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = LecturingScornmage(owner=p1, controller=p1)
        spell = PlayerTargetingTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.BLACK: 1},
        )
        card.register_triggers(game)
        p1._script.append(p2)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell

        resolve_top(game)

        assert card.plus_one_counters == 0
