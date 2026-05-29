"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell_with_alternate_cost
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import (
    AlternateCostType,
    CardMechanic,
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Step,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


def _set_library(player, cards: list[object]) -> None:
    library = player.zones[Zone.LIBRARY]
    for card in library.get_all():
        library.remove(card)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


class TestLoreholdTheHistorianProperties:
    """Static card data should match the SOS 201 spec."""

    def test_is_a_creature(self) -> None:
        assert isinstance(LoreholdTheHistorian(owner=None), Creature)

    def test_name_and_mana_cost(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.name == 'Lorehold, the Historian'
        assert card.mana_cost == ManaCost.parse('{3}{R}{W}')

    def test_is_a_legendary_elder_dragon_with_flying_and_haste(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {'Elder', 'Dragon'} <= card.subtypes
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords

    def test_is_five_five(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5


class TestLoreholdTheHistorianUpkeepTrigger:
    """The rummage trigger should happen on each opponent's upkeep only."""

    def test_registers_an_opponent_upkeep_trigger(self) -> None:
        game = create_game()
        controller = game.players[0]
        card = LoreholdTheHistorian(owner=controller, controller=controller)
        set_board_state(game, 0, battlefield=[card])

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is BeginningOfUpkeepTriggeredEvent

    def test_trigger_fires_on_opponents_upkeep_but_not_your_own(self) -> None:
        game = create_game()
        controller = game.players[0]
        card = LoreholdTheHistorian(owner=controller, controller=controller)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.active_player_index = 0
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert len(game.stack) == 0

        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert len(game.stack) == 1
        assert game.stack.peek() is not None
        assert game.stack.peek().source is card

    def test_may_decline_without_discarding_or_drawing(self) -> None:
        game = create_game()
        controller = game.players[0]
        card = LoreholdTheHistorian(owner=controller, controller=controller)
        discard_card = Instant(name='Old Notes', mana_cost=ManaCost.parse('{R}'))
        drawn_card = Instant(name='Fresh Notes', mana_cost=ManaCost.parse('{W}'))
        set_board_state(game, 0, battlefield=[card], hand=[discard_card])
        _set_library(controller, [drawn_card])
        controller.choose_yes_no = lambda prompt: False

        card.register_triggers(game)
        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert controller.zones[Zone.HAND].contains(discard_card)
        assert not controller.zones[Zone.GRAVEYARD].contains(discard_card)
        assert not controller.zones[Zone.HAND].contains(drawn_card)
        assert controller.zones[Zone.LIBRARY].contains(drawn_card)

    def test_discarding_a_card_draws_one(self) -> None:
        game = create_game()
        controller = game.players[0]
        card = LoreholdTheHistorian(owner=controller, controller=controller)
        discard_card = Instant(name='Old Notes', mana_cost=ManaCost.parse('{R}'))
        drawn_card = Instant(name='Fresh Notes', mana_cost=ManaCost.parse('{W}'))
        set_board_state(game, 0, battlefield=[card], hand=[discard_card])
        _set_library(controller, [drawn_card])
        controller.choose_yes_no = lambda prompt: True
        controller.choose_card = lambda cards, description: discard_card

        card.register_triggers(game)
        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert controller.zones[Zone.GRAVEYARD].contains(discard_card)
        assert not controller.zones[Zone.HAND].contains(discard_card)
        assert controller.zones[Zone.HAND].contains(drawn_card)
        assert not controller.zones[Zone.LIBRARY].contains(drawn_card)
        assert len(controller.zones[Zone.HAND].get_all()) == 1

    def test_empty_hand_means_no_discard_and_no_draw(self) -> None:
        game = create_game()
        controller = game.players[0]
        card = LoreholdTheHistorian(owner=controller, controller=controller)
        drawn_card = Instant(name='Fresh Notes', mana_cost=ManaCost.parse('{W}'))
        set_board_state(game, 0, battlefield=[card], hand=[])
        _set_library(controller, [drawn_card])
        controller.choose_yes_no = lambda prompt: True
        controller.choose_card = lambda cards, description: None

        card.register_triggers(game)
        game.active_player_index = 1
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        trigger_obj = game.stack.pop()
        trigger_obj.on_resolve(game)

        assert len(controller.zones[Zone.HAND].get_all()) == 0
        assert len(controller.zones[Zone.GRAVEYARD].get_all()) == 0
        assert controller.zones[Zone.LIBRARY].contains(drawn_card)


class TestLoreholdTheHistorianMiracle:
    """Lorehold should grant and expose miracle {2} correctly."""

    def test_grants_miracle_two_to_instants_and_sorceries_in_your_hand_only(self) -> None:
        game = create_game()
        controller = game.players[0]
        lorehold = LoreholdTheHistorian(owner=controller, controller=controller)
        instant_card = Instant(name='Sudden Insight', mana_cost=ManaCost.parse('{3}{U}'))
        sorcery_card = Sorcery(name='Archivist Lesson', mana_cost=ManaCost.parse('{4}{R}'))
        creature_card = Creature(name='Campus Bear', base_power=2, base_toughness=2)
        graveyard_instant = Instant(name='Spent Notes', mana_cost=ManaCost.parse('{W}'))
        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            hand=[instant_card, sorcery_card, creature_card],
            graveyard=[graveyard_instant],
        )

        expected_cost = ManaCost.parse('{2}')
        assert instant_card.get_miracle_cost(game, controller) == expected_cost
        assert sorcery_card.get_miracle_cost(game, controller) == expected_cost
        assert creature_card.get_miracle_cost(game, controller) is None
        assert graveyard_instant.get_miracle_cost(game, controller) is None

    def test_first_card_drawn_gets_public_miracle_alternate_cost_but_second_draw_does_not(self) -> None:
        game = create_game()
        controller = game.players[0]
        lorehold = LoreholdTheHistorian(owner=controller, controller=controller)
        first_drawn = Instant(name='Miraculous Notes', mana_cost=ManaCost.parse('{4}{U}'))
        second_drawn = Instant(name='Ordinary Notes', mana_cost=ManaCost.parse('{2}{U}'))
        set_board_state(game, 0, battlefield=[lorehold])
        _set_library(controller, [second_drawn, first_drawn])

        draw_card(game, controller)
        alternate_costs = first_drawn.get_alternate_costs(game, controller)

        assert first_drawn.can_cast_via_miracle(game, controller) is True
        assert len(alternate_costs) == 1
        assert alternate_costs[0].cost == ManaCost.parse('{2}')
        assert alternate_costs[0].cost_type is AlternateCostType.MIRACLE
        assert alternate_costs[0].mechanic is CardMechanic.MIRACLE

        draw_card(game, controller)

        assert second_drawn.can_cast_via_miracle(game, controller) is False
        assert second_drawn.get_alternate_costs(game, controller) == []

    def test_first_drawn_sorcery_can_be_cast_for_miracle_on_opponents_upkeep(self) -> None:
        game = create_game()
        controller = game.players[0]
        lorehold = LoreholdTheHistorian(owner=controller, controller=controller)
        miracle_spell = Sorcery(name='History Rewritten', mana_cost=ManaCost.parse('{5}{R}'))
        set_board_state(
            game,
            0,
            battlefield=[lorehold],
            mana={ManaType.COLORLESS: 2},
        )
        _set_library(controller, [miracle_spell])
        game.active_player_index = 1
        game.priority_player_index = 0
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP

        draw_card(game, controller)
        alternate_cost = miracle_spell.get_alternate_costs(game, controller)[0]

        cast_spell_with_alternate_cost(game, controller, miracle_spell, alternate_cost)

        assert not controller.zones[Zone.HAND].contains(miracle_spell)
        assert controller.zones[Zone.STACK].contains(miracle_spell)
        assert controller.mana_pool.total() == 0
        assert miracle_spell.alternate_cost_used.cost == ManaCost.parse('{2}')
        assert miracle_spell.alternate_cost_used.cost_type is AlternateCostType.MIRACLE
