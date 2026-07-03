"""Tests for SOS 182 — Conciliator's Duelist."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_182.card_impl import ConciliatorsDuelist
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.events import (
    EndStepTriggeredEvent,
    EntersBattlefieldTriggeredEvent,
    SpellCastTriggeredEvent,
)
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
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


class TestConciliatorsDuelistProperties:
    """Static card data should match the SOS 182 spec."""

    def test_is_kor_warlock_creature(self) -> None:
        card = ConciliatorsDuelist(owner=None)

        assert isinstance(card, Creature)
        assert "Kor" in card.subtypes
        assert "Warlock" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = ConciliatorsDuelist(owner=None)

        assert card.name == "Conciliator's Duelist"
        assert card.mana_cost == ManaCost.parse("{W}{W}{B}{B}")
        assert card.base_power == 4
        assert card.base_toughness == 3


class TestConciliatorsDuelistEntersTrigger:
    """Conciliator's Duelist should cantrip and drain each player on entry."""

    def test_registers_enters_battlefield_and_spell_cast_triggers(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ConciliatorsDuelist(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 2
        assert any(trigger.event_type is EntersBattlefieldTriggeredEvent for trigger in triggers)
        assert any(trigger.event_type is SpellCastTriggeredEvent for trigger in triggers)

    def test_when_it_enters_you_draw_a_card_and_each_player_loses_one_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ConciliatorsDuelist(owner=p1, controller=p1)
        drawn = CardImpl(name="Lesson Learned", owner=p1, controller=p1)
        game.get_library(p1).add(drawn)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        assert len(game.stack) == 1
        resolve_top(game)

        assert game.get_hand(p1).contains(drawn)
        assert p1.life == 19
        assert p2.life == 19


class TestConciliatorsDuelistRepartee:
    """Conciliator's Duelist should blink a creature off repartee."""

    def test_creature_targeting_spell_exiles_target_creature_and_returns_it_at_next_end_step_under_its_owners_control(
        self,
    ) -> None:
        game = create_game()
        p1, p2 = game.players
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = ConciliatorsDuelist(owner=p1, controller=p1)
        spell_target = Creature(
            name="Spell Target",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        stolen = Creature(
            name="Borrowed Lecturer",
            owner=p2,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        spell = CreatureTargetingTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card, spell_target, stolen],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        p1._script.extend([spell_target, stolen])
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert not game.get_battlefield(p1).contains(stolen)
        assert game.get_exile(p2).contains(stolen)
        assert game.stack.peek().source is spell

        resolve_top(game)

        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)

        assert not game.get_exile(p2).contains(stolen)
        assert game.get_battlefield(p2).contains(stolen)
        assert stolen.controller is p2

    def test_spell_that_does_not_target_a_creature_does_not_trigger_repartee(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ConciliatorsDuelist(owner=p1, controller=p1)
        spell = PlayerTargetingTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            mana={ManaType.WHITE: 1},
        )
        p1._script.append(p2)
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
