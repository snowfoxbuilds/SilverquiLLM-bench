"""Tests for SOS 137 — Zealous Lorecaster."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_137.card_impl import ZealousLorecaster
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestZealousLorecasterProperties:
    """Static card data should match the SOS 137 spec."""

    def test_is_giant_sorcerer_creature(self) -> None:
        card = ZealousLorecaster(owner=None)
        assert isinstance(card, Creature)
        assert "Giant" in card.subtypes
        assert "Sorcerer" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = ZealousLorecaster(owner=None)
        assert card.name == "Zealous Lorecaster"
        assert card.mana_cost == ManaCost.parse("{5}{R}")
        assert card.base_power == 4
        assert card.base_toughness == 4


class TestZealousLorecasterTrigger:
    """Zealous Lorecaster should return an instant or sorcery from your graveyard."""

    def test_registers_an_enters_battlefield_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ZealousLorecaster(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent

    def test_self_entry_puts_a_trigger_on_the_stack_and_returns_target_instant_card_from_your_graveyard_to_your_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ZealousLorecaster(owner=p1, controller=p1)
        target = Instant(name="Saved Insight", owner=p1, controller=p1, mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, battlefield=[card], graveyard=[target])
        card.chosen_targets = [target]
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        assert len(game.stack) == 1
        resolve_top(game)

        assert not game.get_graveyard(p1).contains(target)
        assert game.get_hand(p1).contains(target)

    def test_self_entry_puts_a_trigger_on_the_stack_and_returns_target_sorcery_card_from_your_graveyard_to_your_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ZealousLorecaster(owner=p1, controller=p1)
        target = Sorcery(name="Recovered Lecture", owner=p1, controller=p1, mana_cost=ManaCost.parse("{1}{R}"))
        set_board_state(game, 0, battlefield=[card], graveyard=[target])
        card.chosen_targets = [target]
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        assert len(game.stack) == 1
        resolve_top(game)

        assert not game.get_graveyard(p1).contains(target)
        assert game.get_hand(p1).contains(target)

    def test_does_not_return_a_noninstant_nonsorcery_card_from_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ZealousLorecaster(owner=p1, controller=p1)
        target = Creature(
            name="Creature Lesson",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{2}{R}"),
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card], graveyard=[target])
        card.chosen_targets = [target]
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )
        resolve_top(game)

        assert game.get_graveyard(p1).contains(target)
        assert not game.get_hand(p1).contains(target)
