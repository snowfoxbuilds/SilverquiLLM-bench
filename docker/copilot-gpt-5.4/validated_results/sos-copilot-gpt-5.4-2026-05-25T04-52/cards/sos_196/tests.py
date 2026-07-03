"""Tests for SOS 196 — Inkling Mascot."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_196.card_impl import InklingMascot
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, Phase, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CreatureTargetingTestInstant(Instant):
    """Simple instant used to exercise repartee-style triggers."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Creature Targeting Test Instant")
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


class CreatureTargetingTestSorcery(Sorcery):
    """Simple sorcery used to exercise repartee-style triggers."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Creature Targeting Test Sorcery")
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
        kwargs.setdefault("name", "Player Targeting Test Instant")
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


class TestInklingMascotProperties:
    """Static card data should match the SOS 196 spec."""

    def test_is_inkling_cat_creature(self) -> None:
        card = InklingMascot(owner=None)

        assert isinstance(card, Creature)
        assert "Inkling" in card.subtypes
        assert "Cat" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = InklingMascot(owner=None)

        assert card.name == "Inkling Mascot"
        assert card.mana_cost == ManaCost.parse("{W}{B}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestInklingMascotRepartee:
    """Inkling Mascot should gain flying and surveil 1 for creature-targeting spells."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = InklingMascot(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_creature_targeting_instant_puts_trigger_on_stack_gains_flying_until_end_of_turn_and_can_surveil_into_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        mascot = InklingMascot(owner=p1, controller=p1)
        spell_target = Creature(
            name="Study Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        top_card = Instant(name="Top Lesson", owner=p1, controller=p1)
        spell = CreatureTargetingTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[mascot, spell_target],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        game.get_library(p1).add(top_card)
        mascot.register_triggers(game)
        p1._script.extend([spell_target, True])

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is mascot

        resolve_top(game)

        assert Keyword.FLYING in mascot.keywords
        assert game.get_graveyard(p1).contains(top_card)
        assert not game.get_library(p1).contains(top_card)

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert Keyword.FLYING not in mascot.keywords

    def test_creature_targeting_sorcery_also_puts_trigger_on_stack_and_may_leave_the_surveilled_card_on_top(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        mascot = InklingMascot(owner=p1, controller=p1)
        spell_target = Creature(
            name="Lesson Subject",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        top_card = Sorcery(name="Top Chapter", owner=p1, controller=p1)
        spell = CreatureTargetingTestSorcery(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[mascot, spell_target],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        game.get_library(p1).add(top_card)
        mascot.register_triggers(game)
        p1._script.extend([spell_target, False])

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is mascot

        resolve_top(game)

        assert Keyword.FLYING in mascot.keywords
        assert game.get_library(p1).top(1) == [top_card]
        assert not game.get_graveyard(p1).contains(top_card)

    def test_spell_that_does_not_target_a_creature_does_not_trigger(self) -> None:
        game = create_game()
        p1, p2 = game.players
        mascot = InklingMascot(owner=p1, controller=p1)
        spell = PlayerTargetingTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[mascot],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        mascot.register_triggers(game)
        p1._script.append(p2)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
