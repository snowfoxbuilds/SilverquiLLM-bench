"""Tests for SOS 210 — Practiced Scrollsmith."""

from __future__ import annotations

from typing import Any

from benchmarks.sos.workspace.cards.sos.sos_210.card_impl import PracticedScrollsmith
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Land, Sorcery
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, Phase, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class GraveyardLesson(Sorcery):
    """Simple noncreature, nonland card for Scrollsmith's ETB test coverage."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Graveyard Lesson")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        super().__init__(**kwargs)


class TestPracticedScrollsmithProperties:
    """Static card data should match the SOS 210 spec."""

    def test_is_dwarf_cleric_creature_with_first_strike(self) -> None:
        card = PracticedScrollsmith(owner=None)

        assert isinstance(card, Creature)
        assert "Dwarf" in card.subtypes
        assert "Cleric" in card.subtypes
        assert Keyword.FIRST_STRIKE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = PracticedScrollsmith(owner=None)

        assert card.name == "Practiced Scrollsmith"
        assert card.mana_cost == ManaCost.parse("{R}{R/W}{W}")
        assert card.base_power == 3
        assert card.base_toughness == 2


class TestPracticedScrollsmithEntersTrigger:
    """Practiced Scrollsmith should temporarily exile and let you cast the right graveyard card."""

    def test_registers_an_enters_battlefield_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PracticedScrollsmith(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent

    def test_self_entry_puts_a_trigger_on_the_stack_and_exiles_a_noncreature_nonland_card_from_your_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = PracticedScrollsmith(owner=p1, controller=p1)
        target = GraveyardLesson(owner=p1, controller=p1)
        filler = CardImpl(name="Study Notes", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], graveyard=[target, filler])
        p1._script.append(target)
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        assert len(game.stack) == 1

        resolve_top(game)

        assert game.get_exile(p1).contains(target)
        assert not game.get_graveyard(p1).contains(target)
        assert game.get_graveyard(p1).contains(filler)
        assert game.can_player_play_exiled_card(p1, target) is True
        assert game.can_player_play_exiled_card(p2, target) is False

    def test_exiled_card_can_be_cast_from_exile_before_the_permission_expires(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = PracticedScrollsmith(owner=p1, controller=p1)
        target = GraveyardLesson(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[card],
            graveyard=[target],
            mana={ManaType.RED: 2},
        )
        p1._script.append(target)
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )
        resolve_top(game)

        cast_spell_paid(game, p1, target, from_zone=Zone.EXILE)

        assert len(game.stack) == 1
        assert game.stack.peek().source is target

        resolve_top(game)

        assert game.get_graveyard(p1).contains(target)
        assert not game.get_exile(p1).contains(target)

    def test_if_your_graveyard_has_only_creature_and_land_cards_self_entry_does_not_put_the_trigger_on_the_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PracticedScrollsmith(owner=p1, controller=p1)
        creature_card = Creature(
            name="Dormant Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        land_card = Land(name="Campus Grounds", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], graveyard=[creature_card, land_card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(creature_card)
        assert game.get_graveyard(p1).contains(land_card)

    def test_exile_permission_lasts_until_the_end_of_your_next_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = PracticedScrollsmith(owner=p1, controller=p1)
        target = GraveyardLesson(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], graveyard=[target])
        p1._script.append(target)
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )
        resolve_top(game)

        assert game.can_player_play_exiled_card(p1, target) is True

        for _ in range(12):
            game.advance_phase()
        assert game.can_player_play_exiled_card(p1, target) is True

        for _ in range(12):
            game.advance_phase()
        assert game.can_player_play_exiled_card(p1, target) is True

        for _ in range(12):
            game.advance_phase()
        assert game.can_player_play_exiled_card(p1, target) is False
