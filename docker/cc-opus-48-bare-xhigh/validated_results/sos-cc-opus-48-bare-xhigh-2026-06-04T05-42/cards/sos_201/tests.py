"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.events import (
    BeginningOfUpkeepTriggeredEvent,
    DrawsCardTriggeredEvent,
)
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import _resolve_top_of_stack, create_game, set_board_state


class TestProperties:
    def test_is_creature(self) -> None:
        assert isinstance(LoreholdTheHistorian(owner=None), Creature)

    def test_name(self) -> None:
        assert LoreholdTheHistorian(owner=None).name == "Lorehold, the Historian"

    def test_mana_cost(self) -> None:
        assert LoreholdTheHistorian(owner=None).mana_cost == ManaCost.parse(
            "{3}{R}{W}"
        )

    def test_power_toughness(self) -> None:
        c = LoreholdTheHistorian(owner=None)
        assert (c.base_power, c.base_toughness) == (5, 5)

    def test_flying_haste_legendary(self) -> None:
        c = LoreholdTheHistorian(owner=None)
        assert Keyword.FLYING in c.keywords
        assert Keyword.HASTE in c.keywords
        assert Supertype.LEGENDARY in c.supertypes

    def test_registers_two_triggers(self) -> None:
        game = create_game()
        lore = LoreholdTheHistorian(owner=game.players[0], controller=game.players[0])
        lore.register_triggers(game)
        assert len(game.trigger_manager.get_triggers_for_source(lore)) == 2


class TestUpkeepLoot:
    def test_discard_then_draw_on_opponent_upkeep(self) -> None:
        h1 = Instant(name="H1")
        h2 = Instant(name="H2")
        game = create_game(scripts=([True, h1], []))
        p1, p2 = game.players
        lore = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lore], hand=[h1, h2])
        drawme = Creature(name="DrawMe", base_power=1, base_toughness=1)
        drawme.owner = p1
        drawme.controller = p1
        p1.zones[Zone.LIBRARY].add(drawme)
        lore.register_triggers(game)

        game.active_player_index = 1  # p2's upkeep
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_top_of_stack(game)

        assert p1.zones[Zone.GRAVEYARD].contains(h1)
        assert p1.zones[Zone.HAND].contains(drawme)

    def test_no_trigger_on_own_upkeep(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        lore = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lore], hand=[Instant(name="X")])
        lore.register_triggers(game)
        game.active_player_index = 0  # p1's own upkeep
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert game.stack.is_empty()


class TestMiracle:
    def test_first_instant_drawn_can_be_cast_for_two(self) -> None:
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        game = create_game(scripts=([True], []))
        p1 = game.players[0]
        lore = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lore], hand=[bolt], mana={ManaType.COLORLESS: 2})
        lore.register_triggers(game)
        game.turn_number = 1

        game.trigger_manager.fire_event(
            game, DrawsCardTriggeredEvent(player=p1, card=bolt)
        )
        _resolve_top_of_stack(game)
        # Cast via miracle: the card left the hand and is now in the graveyard.
        assert not p1.zones[Zone.HAND].contains(bolt)
        assert p1.zones[Zone.GRAVEYARD].contains(bolt)

    def test_non_spell_draw_does_not_trigger(self) -> None:
        creature = Creature(name="Beast", base_power=3, base_toughness=3)
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        lore = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lore], hand=[creature])
        lore.register_triggers(game)
        game.turn_number = 1
        game.trigger_manager.fire_event(
            game, DrawsCardTriggeredEvent(player=p1, card=creature)
        )
        assert game.stack.is_empty()

    def test_opponent_draw_does_not_trigger(self) -> None:
        bolt = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        lore = LoreholdTheHistorian(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[lore])
        set_board_state(game, 1, hand=[bolt])
        lore.register_triggers(game)
        game.turn_number = 1
        game.trigger_manager.fire_event(
            game, DrawsCardTriggeredEvent(player=p2, card=bolt)
        )
        assert game.stack.is_empty()
