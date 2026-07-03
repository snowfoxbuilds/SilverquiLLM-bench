"""Tests for Lorehold, the Historian (sos_201)."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.types import Keyword, ManaCost, ManaType, Phase, Step, Zone
from test_utils import advance_to_phase, create_game, set_board_state
from test_utils import _resolve_top_of_stack


def _setup():
    game = create_game()
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    return game


def test_flying_haste():
    """Lorehold has Flying and Haste."""
    lorehold = LoreholdTheHistorian()
    assert Keyword.FLYING in lorehold.keywords
    assert Keyword.HASTE in lorehold.keywords


def test_miracle_fires_on_first_draw_of_instant():
    """When controller draws an Instant as first card of the turn, miracle offer fires."""
    game = _setup()
    p0, p1 = game.players

    lorehold = LoreholdTheHistorian()
    lorehold.owner = p0
    lorehold.controller = p0
    set_board_state(game, 0, battlefield=[lorehold])
    lorehold.register_triggers(game)

    # Put a 1-generic instant in the library (top of deck)
    instant = Instant(name="Quick Spell", mana_cost=ManaCost(generic=1))
    instant.on_resolve = lambda g: None
    lib = game.get_library(p0)
    lib.add(instant, position="top")

    # Give player {2} mana for miracle cost
    p0.mana_pool.add(ManaType.COLORLESS, 2)

    # Script: say yes to miracle, instant has no targets
    p0._script.appendleft(True)

    from engine.game import draw_card
    draw_card(game, p0)
    _resolve_top_of_stack(game)

    # Instant should be on the stack (cast via miracle) or resolved (in graveyard)
    # Since instant.on_resolve does nothing and it's resolved, check graveyard
    assert game.get_graveyard(p0).contains(instant) or not game.stack.is_empty()


def test_miracle_not_fires_on_second_draw():
    """Miracle does not trigger on the second card drawn in a turn."""
    game = _setup()
    p0, p1 = game.players

    lorehold = LoreholdTheHistorian()
    lorehold.owner = p0
    lorehold.controller = p0
    set_board_state(game, 0, battlefield=[lorehold])
    lorehold.register_triggers(game)

    # First card: a creature (non-IS) → increments draw count to 1, no miracle
    creature_card = Creature(name="Dummy", base_power=1, base_toughness=1)
    instant = Instant(name="Quick Spell", mana_cost=ManaCost(generic=1))
    instant.on_resolve = lambda g: None

    lib = game.get_library(p0)
    lib.add(instant, position="top")    # will be drawn SECOND
    lib.add(creature_card, position="top")  # drawn FIRST (top of deck)

    p0.mana_pool.add(ManaType.COLORLESS, 2)

    from engine.game import draw_card
    # Draw first card (creature) — draw count becomes 1 but not an IS
    draw_card(game, p0)
    _resolve_top_of_stack(game)

    # Draw second card (instant) — draw count becomes 2, miracle condition fails
    draw_card(game, p0)
    _resolve_top_of_stack(game)

    # Instant should still be in hand, not on stack (no miracle)
    assert game.get_hand(p0).contains(instant)
    assert game.stack.is_empty()


def test_loot_fires_on_opponent_upkeep():
    """At the beginning of opponent's upkeep, may discard then draw."""
    game = _setup()
    p0, p1 = game.players

    lorehold = LoreholdTheHistorian()
    lorehold.owner = p0
    lorehold.controller = p0
    set_board_state(game, 0, battlefield=[lorehold])
    lorehold.register_triggers(game)

    # Give p0 a card in hand to discard
    hand_card = Creature(name="HandCard", base_power=1, base_toughness=1)
    hand_card.owner = p0
    hand_card.controller = p0
    p0.zones[Zone.HAND].add(hand_card)

    # Give p0 a library card to draw
    draw_me = Creature(name="DrawMe", base_power=1, base_toughness=1)
    draw_me.owner = p0
    draw_me.controller = p0
    game.get_library(p0).add(draw_me, position="top")

    # Switch to p1's turn so loot condition fires (active_player != p0/controller)
    game.active_player_index = 1

    # Fire upkeep event directly (BeginningOfUpkeepTriggeredEvent is only fired
    # from run_turn, not from advance_phase, so we fire it manually here)
    from engine.events import BeginningOfUpkeepTriggeredEvent
    # Script: yes to loot, then choose hand_card to discard
    p0._script.appendleft(hand_card)  # consumed second: choose card
    p0._script.appendleft(True)       # consumed first: yes to loot

    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    _resolve_top_of_stack(game)

    # hand_card should be in graveyard (discarded), draw_me should be in hand (drawn)
    assert game.get_graveyard(p0).contains(hand_card), "Discarded card should be in graveyard"
    assert game.get_hand(p0).contains(draw_me), "Drawn card should be in hand"


def test_loot_not_fires_on_own_upkeep():
    """Loot trigger does NOT fire at controller's own upkeep."""
    game = _setup()
    p0, p1 = game.players

    lorehold = LoreholdTheHistorian()
    lorehold.owner = p0
    lorehold.controller = p0
    set_board_state(game, 0, battlefield=[lorehold])
    lorehold.register_triggers(game)

    hand_card = Creature(name="HandCard", base_power=1, base_toughness=1)
    hand_card.owner = p0
    hand_card.controller = p0
    p0.zones[Zone.HAND].add(hand_card)

    # active_player is p0 (controller) — loot should NOT trigger
    from engine.events import BeginningOfUpkeepTriggeredEvent
    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    # Stack should be empty (no loot trigger)
    assert game.stack.is_empty(), "No loot trigger for own upkeep"
    assert game.get_hand(p0).contains(hand_card)
