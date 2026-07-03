"""Tests for SOS 102 — Tragedy Feaster."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_102.card_impl import TragedyFeaster
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.events import EndStepTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CreatureTargetingTestInstant(Instant):
    """Simple instant used to exercise ward handling."""

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


class TestTragedyFeasterProperties:
    """Static card data should match the SOS 102 spec."""

    def test_is_demon_creature_with_trample_and_ward(self) -> None:
        card = TragedyFeaster(owner=None)

        assert isinstance(card, Creature)
        assert "Demon" in card.subtypes
        assert Keyword.TRAMPLE in card.keywords
        assert Keyword.WARD in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = TragedyFeaster(owner=None)

        assert card.name == "Tragedy Feaster"
        assert card.mana_cost == ManaCost.parse("{2}{B}{B}")
        assert card.base_power == 7
        assert card.base_toughness == 6


class TestTragedyFeasterWard:
    """Tragedy Feaster should enforce Ward—Discard a card."""

    def test_opponents_targeting_spell_is_countered_when_they_cannot_discard_for_ward(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = TragedyFeaster(owner=p1, controller=p1)
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
        card = TragedyFeaster(owner=p1, controller=p1)
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


class TestTragedyFeasterInfusion:
    """Tragedy Feaster should demand a sacrifice on your end step unless you gained life."""

    def test_registers_an_end_step_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TragedyFeaster(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EndStepTriggeredEvent

    def test_your_end_step_without_life_gain_puts_a_trigger_on_the_stack_and_makes_you_sacrifice_a_chosen_permanent(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TragedyFeaster(owner=p1, controller=p1)
        fodder = Creature(
            name="Disposable Cultist",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        set_board_state(game, 0, battlefield=[card, fodder])
        p1._script.append(fodder)
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))

        assert len(game.stack) == 1
        resolve_top(game)

        assert game.get_graveyard(p1).contains(fodder)
        assert game.get_battlefield(p1).contains(card)

    def test_your_end_step_with_life_gain_still_triggers_but_does_not_make_you_sacrifice(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TragedyFeaster(owner=p1, controller=p1)
        fodder = Creature(
            name="Disposable Cultist",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        set_board_state(game, 0, battlefield=[card, fodder])
        p1.life_gained_this_turn = 1
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))

        assert len(game.stack) == 1
        resolve_top(game)

        assert game.get_battlefield(p1).contains(card)
        assert game.get_battlefield(p1).contains(fodder)
        assert not game.get_graveyard(p1).contains(card)
        assert not game.get_graveyard(p1).contains(fodder)

    def test_does_not_trigger_on_an_opponents_end_step(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = TragedyFeaster(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1

        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p2))

        assert game.stack.is_empty()
