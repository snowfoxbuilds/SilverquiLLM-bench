"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_201.card_impl import LoreholdTheHistorian
from benchmarks.sos.workspace.engine.casting import (
    CastingError,
    can_cast_for_miracle,
    cast_spell_for_miracle,
    get_miracle_cost,
    resolve_top,
)
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.events import BeginningOfUpkeepTriggeredEvent
from benchmarks.sos.workspace.engine.game import draw_card
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, Phase, Step, Supertype
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestLoreholdTheHistorianProperties:
    """Static card data should match the SOS 201 spec."""

    def test_is_a_legendary_elder_dragon_with_flying_and_haste(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords

    def test_name_mana_cost_and_power_toughness(self) -> None:
        card = LoreholdTheHistorian(owner=None)

        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert card.base_power == 5
        assert card.base_toughness == 5


class TestLoreholdTheHistorianUpkeepTrigger:
    """Lorehold, the Historian should loot on each opponent's upkeep."""

    def test_opponents_upkeep_may_discard_a_card_to_draw_a_card(self) -> None:
        game = create_game()
        p1, p2 = game.players
        historian = LoreholdTheHistorian(owner=p1, controller=p1)
        discarded = CardImpl(name="Ancient Notes", owner=p1, controller=p1)
        drawn = CardImpl(name="Fresh Notes", owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[historian], hand=[discarded])
        game.get_library(p1).add(drawn)
        historian.register_triggers(game)
        game.active_player_index = 1
        p1._script.extend([True, discarded])

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert len(game.stack) == 1
        assert game.stack.peek().source is historian

        resolve_top(game)

        assert game.get_graveyard(p1).contains(discarded)
        assert game.get_hand(p1).contains(drawn)
        assert not game.get_hand(p1).contains(discarded)

    def test_opponents_upkeep_can_choose_not_to_discard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        historian = LoreholdTheHistorian(owner=p1, controller=p1)
        kept = CardImpl(name="Kept Notes", owner=p1, controller=p1)
        undrawn = CardImpl(name="Still on Top", owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[historian], hand=[kept])
        game.get_library(p1).add(undrawn)
        historian.register_triggers(game)
        game.active_player_index = 1
        p1._script.append(False)

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        resolve_top(game)

        assert game.get_hand(p1).contains(kept)
        assert not game.get_hand(p1).contains(undrawn)
        assert game.get_graveyard(p1).get_all() == []

    def test_your_own_upkeep_does_not_trigger_the_ability(self) -> None:
        game = create_game()
        p1 = game.players[0]
        historian = LoreholdTheHistorian(owner=p1, controller=p1)

        game.get_battlefield(p1).add(historian)
        historian.register_triggers(game)
        game.active_player_index = 0

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert len(game.stack) == 0


class TestLoreholdTheHistorianMiracle:
    """Lorehold, the Historian should grant and enable miracle casts."""

    def test_grants_miracle_two_to_instants_and_sorceries_in_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        historian = LoreholdTheHistorian(owner=p1, controller=p1)
        instant = Instant(
            name="Sudden Insight",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{4}{U}"),
        )
        sorcery = Sorcery(
            name="Patient Thesis",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{5}{U}"),
        )
        creature = Creature(
            name="Campus Guardian",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{2}{W}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(game, 0, battlefield=[historian], hand=[instant, sorcery, creature])

        assert get_miracle_cost(game, p1, instant) == ManaCost.parse("{2}")
        assert get_miracle_cost(game, p1, sorcery) == ManaCost.parse("{2}")
        assert get_miracle_cost(game, p1, creature) is None

    def test_first_card_drawn_this_turn_can_be_cast_for_miracle_two(self) -> None:
        game = create_game()
        p1, p2 = game.players
        historian = LoreholdTheHistorian(owner=p1, controller=p1)
        spell = Sorcery(
            name="Expensive Thesis",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{5}{U}"),
        )

        set_board_state(
            game,
            0,
            battlefield=[historian],
            mana={ManaType.COLORLESS: 2},
        )
        game.get_library(p1).add(spell)
        game.active_player_index = 1
        game.priority_player_index = 0
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP

        drawn = draw_card(game, p1)

        assert drawn is spell
        assert can_cast_for_miracle(game, p1, spell) is True

        cast_spell_for_miracle(game, p1, spell)

        assert game.stack.peek().source is spell
        assert not game.get_hand(p1).contains(spell)
        assert p1.mana_pool.total() == 0

        resolve_top(game)

        assert game.get_graveyard(p1).contains(spell)
        assert game.active_player is p2

    def test_second_card_drawn_this_turn_cannot_be_cast_for_miracle(self) -> None:
        game = create_game()
        p1 = game.players[0]
        historian = LoreholdTheHistorian(owner=p1, controller=p1)
        first_draw = CardImpl(name="Morning Notes", owner=p1, controller=p1)
        spell = Sorcery(
            name="Delayed Thesis",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{5}{U}"),
        )

        set_board_state(
            game,
            0,
            battlefield=[historian],
            mana={ManaType.COLORLESS: 2},
        )
        game.get_library(p1).add(spell)
        game.get_library(p1).add(first_draw)

        assert draw_card(game, p1) is first_draw
        assert draw_card(game, p1) is spell
        assert get_miracle_cost(game, p1, spell) == ManaCost.parse("{2}")
        assert can_cast_for_miracle(game, p1, spell) is False

        with pytest.raises(CastingError):
            cast_spell_for_miracle(game, p1, spell)

        assert game.get_hand(p1).contains(spell)
        assert p1.mana_pool.total() == 2
