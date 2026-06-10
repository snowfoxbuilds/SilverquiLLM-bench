"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.game import draw_card
from engine.stack import priority_loop
from engine.turn import run_turn
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


class LifeRush(Instant):
    """Test instant: you gain 3 life."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Life Rush")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 3


def _filler_creature(name: str) -> Creature:
    return Creature(name=name, base_power=1, base_toughness=1,
                    mana_cost=ManaCost.parse("{1}"))


def _cast_lorehold(game):
    lorehold = LoreholdTheHistorian()
    set_board_state(
        game, 0, hand=[lorehold],
        mana={ManaType.RED: 1, ManaType.WHITE: 1, ManaType.COLORLESS: 3},
    )
    cast_spell(game, 0, "Lorehold, the Historian")
    return lorehold


class TestLorehold:
    def test_keywords(self):
        card = LoreholdTheHistorian()
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords

    def test_loot_on_opponent_upkeep(self):
        deck1 = [_filler_creature(f"D1-{i}") for i in range(10)]
        deck2 = [_filler_creature(f"D2-{i}") for i in range(10)]
        game = create_game(deck1, deck2)
        p1, p2 = game.players
        _cast_lorehold(game)

        # Finish p1's turn (declare no attackers).
        p1._script.extend([None])
        run_turn(game)
        assert game.active_player is p2

        # Set a known hand, then run p2's turn: loot fires at p2's upkeep.
        keep = _filler_creature("Keeper")
        toss = _filler_creature("Tosser")
        set_board_state(game, 0, hand=[keep, toss])
        hand_before = len(game.get_hand(p1))
        p2._script.extend(["pass"])
        p1._script.extend(["pass", True, toss])
        run_turn(game)
        assert game.get_graveyard(p1).contains(toss)
        assert game.get_hand(p1).contains(keep)
        assert len(game.get_hand(p1)) == hand_before  # discarded 1, drew 1

    def test_loot_optional_and_not_on_own_upkeep(self):
        deck1 = [_filler_creature(f"D1-{i}") for i in range(10)]
        deck2 = [_filler_creature(f"D2-{i}") for i in range(10)]
        game = create_game(deck1, deck2)
        p1, p2 = game.players
        _cast_lorehold(game)

        p1._script.extend([None])
        run_turn(game)  # rest of p1's turn 1

        # p2's turn: decline the loot.
        gy_before = len(game.get_graveyard(p1))
        p2._script.extend(["pass"])
        p1._script.extend(["pass", False])
        run_turn(game)
        assert len(game.get_graveyard(p1)) == gy_before

        # p1's own turn: no loot trigger at p1's upkeep — only the attacker
        # declaration consumes a choice.
        p1._script.extend([None])
        run_turn(game)
        assert len(game.get_graveyard(p1)) == gy_before

    def test_miracle_cast_on_first_draw(self):
        game = create_game()
        p1, p2 = game.players
        _cast_lorehold(game)
        rush = LifeRush()
        rush.owner = rush.controller = p1
        p1.zones[Zone.LIBRARY].add(rush)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})

        draw_card(game, p1)  # first draw this turn — miracle trigger
        assert len(game.stack) == 1
        p1._script.extend(["pass", True, "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)
        # Cast for {2} (the only mana available) and resolved.
        assert p1.life == 23
        assert p1.mana_pool.total() == 0
        assert game.get_graveyard(p1).contains(rush)

    def test_miracle_decline_keeps_card(self):
        game = create_game()
        p1, p2 = game.players
        _cast_lorehold(game)
        rush = LifeRush()
        rush.owner = rush.controller = p1
        p1.zones[Zone.LIBRARY].add(rush)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})

        draw_card(game, p1)
        p1._script.extend(["pass", False])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert game.get_hand(p1).contains(rush)
        assert p1.mana_pool.total() == 2  # nothing paid

    def test_miracle_only_first_draw_of_turn(self):
        game = create_game()
        p1 = game.players[0]
        _cast_lorehold(game)
        creature = _filler_creature("First Drawn")
        rush = LifeRush()
        for c in (rush, creature):  # creature on top, instant beneath
            c.owner = c.controller = p1
            p1.zones[Zone.LIBRARY].add(c)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})

        draw_card(game, p1)  # creature — no miracle
        assert game.stack.is_empty()
        draw_card(game, p1)  # instant, but second draw — no miracle
        assert game.stack.is_empty()
        assert game.get_hand(p1).contains(rush)

    def test_no_miracle_for_opponent_draws(self):
        game = create_game()
        p1, p2 = game.players
        _cast_lorehold(game)
        rush = LifeRush()
        rush.owner = rush.controller = p2
        p2.zones[Zone.LIBRARY].add(rush)
        draw_card(game, p2)
        assert game.stack.is_empty()
        assert game.get_hand(p2).contains(rush)
