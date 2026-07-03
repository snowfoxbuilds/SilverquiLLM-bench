"""Tests for Lorehold, the Historian (sos_201)."""

import pytest
from test_utils import create_game, set_board_state
from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import _resolve_top_of_stack


def _sorcery_speed(game, idx=0):
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = idx


class TestLoreholdTheHistorian:
    def test_keywords(self):
        """Has Flying and Haste."""
        card = LoreholdTheHistorian()
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords

    def test_loot_trigger_at_opponent_upkeep(self):
        """At opponent's upkeep, may discard to draw."""
        game = create_game()
        p1, p2 = game.players

        lorehold = LoreholdTheHistorian()
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.controller = p1
        lorehold.register_triggers(game)

        # Put a card in p1's hand to discard
        discard_card = Instant(name="Discard", mana_cost=ManaCost.parse("{R}"))
        discard_card.owner = p1
        # Fill library with a card to draw
        draw_card = Creature(name="DrawTarget", base_power=1, base_toughness=1)
        draw_card.owner = p1
        set_board_state(game, 0, hand=[discard_card])
        p1.zones[Zone.LIBRARY].add(draw_card)

        # p2's upkeep
        game.active_player_index = 1

        # Script: choose discard_card to discard
        p1._script.appendleft(discard_card)

        from engine.events import BeginningOfUpkeepTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_top_of_stack(game)

        # discard_card should be in graveyard, draw_target in hand
        assert discard_card in p1.zones[Zone.GRAVEYARD].get_all()
        assert draw_card in p1.zones[Zone.HAND].get_all()

    def test_loot_trigger_does_not_fire_on_own_upkeep(self):
        """Loot trigger should NOT fire at controller's own upkeep."""
        game = create_game()
        p1 = game.players[0]

        lorehold = LoreholdTheHistorian()
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.controller = p1
        lorehold.register_triggers(game)

        # p1's own upkeep
        game.active_player_index = 0

        from engine.events import BeginningOfUpkeepTriggeredEvent
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        # No trigger should be on the stack
        assert game.stack.is_empty()

    def test_miracle_triggers_on_first_draw(self):
        """Miracle fires when controller draws first instant this turn."""
        game = create_game()
        p1 = game.players[0]

        lorehold = LoreholdTheHistorian()
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.controller = p1
        lorehold.register_triggers(game)

        miracle_instant = Instant(name="Miracle", mana_cost=ManaCost.parse("{5}{R}"))
        miracle_instant.owner = p1
        p1.zones[Zone.LIBRARY].add(miracle_instant)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})

        # Script: yes to cast for miracle cost {2}
        p1._script.appendleft(True)

        from engine.game import draw_card
        draw_card(game, p1)

        # Miracle trigger should be on the stack
        assert not game.stack.is_empty()
        # Resolve: pays {2} and casts
        _resolve_top_of_stack(game)

        # miracle_instant should have been cast (on stack as spell, then resolved to graveyard)
        # After _resolve_top_of_stack resolves everything, it's in graveyard
        assert miracle_instant in p1.zones[Zone.GRAVEYARD].get_all()

    def test_miracle_does_not_trigger_on_second_draw(self):
        """Miracle only fires on first draw this turn."""
        game = create_game()
        p1 = game.players[0]

        lorehold = LoreholdTheHistorian()
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.controller = p1
        lorehold.register_triggers(game)
        # Force turn_number so we can test same-turn tracking
        game.turn_number = 5
        p1._last_miracle_draw_turn = 5  # simulate already drew this turn

        miracle_instant = Instant(name="SecondMiracle", mana_cost=ManaCost.parse("{3}{U}"))
        miracle_instant.owner = p1
        p1.zones[Zone.LIBRARY].add(miracle_instant)

        from engine.game import draw_card
        draw_card(game, p1)

        # No miracle trigger (second draw this turn)
        assert game.stack.is_empty()

    def test_miracle_does_not_trigger_for_creature(self):
        """Miracle only fires for instants/sorceries, not creatures."""
        game = create_game()
        p1 = game.players[0]

        lorehold = LoreholdTheHistorian()
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.controller = p1
        lorehold.register_triggers(game)

        creature_card = Creature(name="Bear", base_power=2, base_toughness=2)
        creature_card.owner = p1
        p1.zones[Zone.LIBRARY].add(creature_card)

        from engine.game import draw_card
        draw_card(game, p1)

        # No miracle trigger (not an instant/sorcery)
        assert game.stack.is_empty()
