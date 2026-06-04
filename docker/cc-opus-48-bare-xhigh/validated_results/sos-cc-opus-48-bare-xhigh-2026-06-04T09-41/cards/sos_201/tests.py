"""Tests for Lorehold, the Historian (SOS #201)."""

from __future__ import annotations

from collections import deque
from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.events import (
    BeginningOfUpkeepTriggeredEvent,
    DrawsCardTriggeredEvent,
)
from engine.game import draw_card
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, TargetRequirement, Zone
from test_utils import create_game, set_board_state


def _is_creature(obj: Any) -> bool:
    return CardType.CREATURE in getattr(obj, "card_types", set())


class _Bolt(Instant):
    """Deals 2 damage to target creature."""

    def __init__(self) -> None:
        super().__init__(name="Test Bolt", mana_cost=ManaCost.parse("{3}{R}"))

    def get_targets(self, game: Any) -> list[TargetRequirement]:
        return [TargetRequirement(_is_creature, "target creature", Zone.BATTLEFIELD)]

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        targets = getattr(self, "chosen_targets", []) or []
        if targets and targets[0] is not None:
            deal_damage(game, self, targets[0], 2)


def _resolve_all(game: Any) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _put_on_library_top(game: Any, player_index: int, card: Any) -> None:
    player = game.players[player_index]
    card.owner = player
    card.controller = player
    player.zones[Zone.LIBRARY].add(card)


def test_basic_characteristics():
    card = LoreholdTheHistorian()
    assert card.base_power == 5 and card.base_toughness == 5
    assert Keyword.FLYING in card.keywords
    assert Keyword.HASTE in card.keywords
    assert Supertype.LEGENDARY in card.supertypes
    assert card.mana_cost.generic == 3


def test_miracle_casts_drawn_instant_for_two():
    game = create_game()
    p1, p2 = game.players

    lorehold = LoreholdTheHistorian()
    set_board_state(game, 0, battlefield=[lorehold])
    lorehold.register_triggers(game)

    victim = Creature(
        name="Victim", mana_cost=ManaCost.parse("{1}"), base_power=0, base_toughness=8
    )
    set_board_state(game, 1, battlefield=[victim])

    bolt = _Bolt()
    _put_on_library_top(game, 0, bolt)

    # Pay the miracle cost {2}, not the full {3}{R}.
    p1.mana_pool.add(ManaType.COLORLESS, 2)

    # First card drawn this turn → miracle is available.
    p1.cards_drawn_this_turn = 0
    # Script: say yes to miracle, then target the victim.
    p1._script = deque([True, victim])

    draw_card(game, p1)
    _resolve_all(game)

    # Cast for its miracle cost: 2 damage dealt, {2} spent.
    assert victim.damage_marked == 2
    assert p1.mana_pool.total() == 0
    # Bolt resolved to the graveyard, not still in hand.
    assert game.get_graveyard(p1).contains(bolt)
    assert not game.get_hand(p1).contains(bolt)


def test_miracle_declined_keeps_card_in_hand():
    game = create_game()
    p1, p2 = game.players

    lorehold = LoreholdTheHistorian()
    set_board_state(game, 0, battlefield=[lorehold])
    lorehold.register_triggers(game)

    bolt = _Bolt()
    _put_on_library_top(game, 0, bolt)
    p1.mana_pool.add(ManaType.COLORLESS, 2)

    p1.cards_drawn_this_turn = 0
    p1._script = deque([False])  # decline the miracle

    draw_card(game, p1)
    _resolve_all(game)

    assert game.get_hand(p1).contains(bolt)
    assert p1.mana_pool.total() == 2


def test_miracle_only_for_first_card_drawn():
    game = create_game()
    p1, p2 = game.players

    lorehold = LoreholdTheHistorian()
    set_board_state(game, 0, battlefield=[lorehold])
    lorehold.register_triggers(game)

    bolt = _Bolt()
    _put_on_library_top(game, 0, bolt)
    p1.mana_pool.add(ManaType.COLORLESS, 2)

    # Pretend a card was already drawn this turn → this is the 2nd.
    p1.cards_drawn_this_turn = 1
    p1._script = deque([])  # no choices expected — miracle must not trigger

    draw_card(game, p1)
    _resolve_all(game)

    # No miracle: bolt stays in hand, mana untouched.
    assert game.get_hand(p1).contains(bolt)
    assert p1.mana_pool.total() == 2


def test_loot_on_opponent_upkeep():
    game = create_game()
    p1, p2 = game.players

    lorehold = LoreholdTheHistorian()
    set_board_state(game, 0, battlefield=[lorehold])
    lorehold.register_triggers(game)

    discard_me = Sorcery(name="Junk", mana_cost=ManaCost.parse("{1}"))
    set_board_state(game, 0, hand=[discard_me])

    # Drawn card is a creature so the loot draw can't itself trigger miracle.
    drawn = Creature(
        name="Fresh Card", mana_cost=ManaCost.parse("{1}"), base_power=1, base_toughness=1
    )
    _put_on_library_top(game, 0, drawn)

    # Opponent's upkeep.
    game.active_player_index = 1
    p1._script = deque([True, discard_me])

    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    _resolve_all(game)

    assert game.get_graveyard(p1).contains(discard_me)
    assert game.get_hand(p1).contains(drawn)
    assert not game.get_hand(p1).contains(discard_me)


def test_no_loot_on_own_upkeep():
    game = create_game()
    p1, p2 = game.players

    lorehold = LoreholdTheHistorian()
    set_board_state(game, 0, battlefield=[lorehold])
    lorehold.register_triggers(game)

    card_in_hand = Sorcery(name="Junk", mana_cost=ManaCost.parse("{1}"))
    set_board_state(game, 0, hand=[card_in_hand])

    # p1's own upkeep — the loot ability only triggers on opponents' upkeeps.
    game.active_player_index = 0
    p1._script = deque([])

    game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    _resolve_all(game)

    assert game.get_hand(p1).contains(card_in_hand)
    assert not game.get_graveyard(p1).contains(card_in_hand)
