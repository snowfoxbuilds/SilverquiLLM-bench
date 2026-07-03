"""Tests for SOS 21 — Inkshape Demonstrator."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_21.card_impl import InkshapeDemonstrator
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.game import deal_damage
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


class TestInkshapeDemonstratorProperties:
    """Static card data should match the SOS 21 spec."""

    def test_is_elephant_cleric_creature_with_ward(self) -> None:
        card = InkshapeDemonstrator(owner=None)
        assert isinstance(card, Creature)
        assert "Elephant" in card.subtypes
        assert "Cleric" in card.subtypes
        assert Keyword.WARD in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = InkshapeDemonstrator(owner=None)
        assert card.name == "Inkshape Demonstrator"
        assert card.mana_cost == ManaCost.parse("{3}{W}")
        assert card.base_power == 3
        assert card.base_toughness == 4


class TestInkshapeDemonstratorWard:
    """Inkshape Demonstrator should enforce Ward {2} against opponents."""

    def test_opponents_targeting_spell_is_countered_when_they_cannot_pay_ward(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = InkshapeDemonstrator(owner=p1, controller=p1)
        spell = CreatureTargetingTestInstant(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, hand=[spell], mana={ManaType.WHITE: 1})
        p2._script.append(card)

        cast_spell_paid(game, p2, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert getattr(spell, "last_ward_outcome", None) == "countered"
        assert game.get_graveyard(p2).contains(spell)
        assert len(game.stack) == 0

    def test_opponent_may_pay_ward_to_keep_their_targeting_spell_on_the_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = InkshapeDemonstrator(owner=p1, controller=p1)
        spell = CreatureTargetingTestInstant(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, hand=[spell], mana={ManaType.WHITE: 3})
        p2._script.extend([card, True])

        cast_spell_paid(game, p2, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert getattr(spell, "last_ward_outcome", None) == "paid"
        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
        assert p2.mana_pool.total() == 0


class TestInkshapeDemonstratorRepartee:
    """Inkshape Demonstrator should reward creature-targeting spells."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = InkshapeDemonstrator(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_creature_targeting_instant_puts_trigger_on_stack_and_grants_plus_one_power_and_lifelink(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = InkshapeDemonstrator(owner=p1, controller=p1)
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
        assert Keyword.LIFELINK in card.keywords

        deal_damage(game, card, p2, card.power)

        assert p1.life == 24
        assert p2.life == 16

    def test_granted_bonus_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = InkshapeDemonstrator(owner=p1, controller=p1)
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
        assert Keyword.LIFELINK in card.keywords

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert card.power == 3
        assert card.toughness == 4
        assert Keyword.LIFELINK not in card.keywords

    def test_spell_that_does_not_target_a_creature_does_not_trigger(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = InkshapeDemonstrator(owner=p1, controller=p1)
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
        assert Keyword.LIFELINK not in card.keywords
