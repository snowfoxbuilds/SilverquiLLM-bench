"""Tests for SOS 84 — Forum Necroscribe."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_84.card_impl import ForumNecroscribe
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CreatureTargetingTestInstant(Instant):
    """Simple instant used to exercise ward and repartee-style triggers."""

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


class TestForumNecroscribeProperties:
    """Static card data should match the SOS 84 spec."""

    def test_is_troll_warlock_creature_with_ward(self) -> None:
        card = ForumNecroscribe(owner=None)
        assert isinstance(card, Creature)
        assert "Troll" in card.subtypes
        assert "Warlock" in card.subtypes
        assert Keyword.WARD in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = ForumNecroscribe(owner=None)
        assert card.name == "Forum Necroscribe"
        assert card.mana_cost == ManaCost.parse("{5}{B}")
        assert card.base_power == 5
        assert card.base_toughness == 4


class TestForumNecroscribeWard:
    """Forum Necroscribe should enforce Ward—Discard a card."""

    def test_opponents_targeting_spell_is_countered_when_they_cannot_discard_for_ward(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ForumNecroscribe(owner=p1, controller=p1)
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
        assert game.stack.is_empty()

    def test_opponent_may_discard_a_card_to_pay_ward_and_keep_their_spell_on_the_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ForumNecroscribe(owner=p1, controller=p1)
        spell = CreatureTargetingTestInstant(owner=p2, controller=p2)
        discard_card = CardImpl(name="Spare Notes", owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, hand=[spell, discard_card], mana={ManaType.WHITE: 1})
        p2._script.extend([card, True, discard_card])

        cast_spell_paid(game, p2, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert getattr(spell, "last_ward_outcome", None) == "paid"
        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
        assert game.get_graveyard(p2).contains(discard_card)
        assert not game.get_hand(p2).contains(discard_card)


class TestForumNecroscribeRepartee:
    """Forum Necroscribe should reanimate a creature for creature-targeting spells."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ForumNecroscribe(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_creature_targeting_spell_puts_trigger_on_stack_and_returns_a_creature_from_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ForumNecroscribe(owner=p1, controller=p1)
        spell_target = Creature(
            name="Spell Target",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        returned = Creature(
            name="Returned Assistant",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        spell = CreatureTargetingTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card, spell_target],
            hand=[spell],
            graveyard=[returned],
            mana={ManaType.WHITE: 1},
        )
        card.register_triggers(game)
        p1._script.extend([spell_target, returned])

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert not game.get_graveyard(p1).contains(returned)
        assert game.get_battlefield(p1).contains(returned)
        assert game.stack.peek().source is spell

        resolve_top(game)

        assert game.get_graveyard(p1).contains(spell)

    def test_spell_that_does_not_target_a_creature_does_not_trigger(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ForumNecroscribe(owner=p1, controller=p1)
        returned = Creature(
            name="Returned Assistant",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        spell = PlayerTargetingTestInstant(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[spell],
            graveyard=[returned],
            mana={ManaType.WHITE: 1},
        )
        card.register_triggers(game)
        p1._script.append(p2)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell

        resolve_top(game)

        assert game.get_graveyard(p1).contains(returned)
        assert not game.get_battlefield(p1).contains(returned)
