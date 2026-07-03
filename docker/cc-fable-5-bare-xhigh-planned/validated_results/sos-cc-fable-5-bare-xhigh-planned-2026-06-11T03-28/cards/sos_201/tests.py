"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.game import draw_card
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


class _Zap(Instant):
    """Helper instant: controller gains 1 life on resolution."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 1


def _setup(game, library_top=None):
    """Lorehold on p1's battlefield with triggers registered; optionally
    stack p1's library (first item on top)."""
    p1 = game.players[0]
    dragon = LoreholdTheHistorian(owner=p1)
    set_board_state(game, 0, battlefield=[dragon])
    dragon.register_triggers(game)
    if library_top:
        library = p1.zones[Zone.LIBRARY]
        for card in library_top:
            card.owner = card.controller = p1
            library.add(card, position="bottom")
    return p1, dragon


class TestLoreholdProperties:
    def test_static_data(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords
        assert card.base_power == 5
        assert card.base_toughness == 5
        assert Supertype.LEGENDARY in card.supertypes


class TestLoreholdMiracle:
    def test_first_drawn_instant_castable_for_two(self) -> None:
        game = create_game()
        zap = _Zap()
        p1, dragon = _setup(game, [zap])
        p2 = game.players[1]
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        draw_card(game, p1)
        # Miracle trigger on the stack — accept, then resolve the cast.
        p1._script.extend(["pass", True, "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)
        assert p1.life == 21
        assert game.get_graveyard(p1).contains(zap)
        assert p1.mana_pool.total() == 0  # the {2} was paid

    def test_miracle_may_be_declined(self) -> None:
        game = create_game()
        zap = _Zap()
        p1, dragon = _setup(game, [zap])
        p2 = game.players[1]
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        draw_card(game, p1)
        p1._script.extend(["pass", False])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert p1.life == 20
        assert game.get_hand(p1).contains(zap)
        assert p1.mana_pool.total() == 2

    def test_no_miracle_on_second_draw(self) -> None:
        game = create_game()
        bear = Creature(name="Top Bear", base_power=2, base_toughness=2)
        zap = _Zap()
        p1, dragon = _setup(game, [bear, zap])
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        draw_card(game, p1)  # first draw: a creature — no miracle
        assert game.stack.is_empty()
        draw_card(game, p1)  # second draw: the instant — not first
        assert game.stack.is_empty()
        assert game.get_hand(p1).contains(zap)

    def test_no_miracle_when_two_short_on_mana(self) -> None:
        game = create_game()
        zap = _Zap()
        p1, dragon = _setup(game, [zap])
        p2 = game.players[1]
        p1.mana_pool.add(ManaType.COLORLESS, 1)  # cannot pay {2}
        draw_card(game, p1)
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert game.get_hand(p1).contains(zap)
        assert p1.remaining_choices == 0  # never even prompted

    def test_draw_counter_resets_each_turn(self) -> None:
        game = create_game()
        bear = Creature(name="Top Bear", base_power=2, base_toughness=2)
        zap = _Zap()
        p1, dragon = _setup(game, [bear, zap])
        p2 = game.players[1]
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        draw_card(game, p1)  # turn 1, first draw: creature
        assert game.stack.is_empty()
        game.turn_number += 1  # new turn — counter restarts
        p1.mana_pool.add(ManaType.COLORLESS, 2)
        draw_card(game, p1)  # new turn's first draw: the instant
        assert not game.stack.is_empty()
        p1._script.extend(["pass", True, "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)
        assert game.get_graveyard(p1).contains(zap)


class TestLoreholdUpkeepLoot:
    def test_loot_at_opponents_upkeep(self) -> None:
        from engine.turn import run_turn

        deck1 = [Creature(name=f"D1-{i}", base_power=1, base_toughness=1)
                 for i in range(10)]
        deck2 = [Creature(name=f"D2-{i}", base_power=1, base_toughness=1)
                 for i in range(10)]
        game = create_game(deck1=deck1, deck2=deck2)
        p1, p2 = game.players
        dragon = LoreholdTheHistorian(owner=p1)
        game.get_battlefield(p1).add(dragon)
        dragon.owner = dragon.controller = p1
        dragon.register_triggers(game)

        # Make it p2's turn from the top.
        game.active_player_index = 1
        game.priority_player_index = 1
        game._normal_next_index = 0

        hand_before = game.get_hand(p1).get_all()
        to_discard = hand_before[0]
        # Scripts: upkeep trigger → p2 pass, p1 pass, then p1 picks the
        # discard.  p2 discards to hand size at cleanup (drew to 8).
        p1._script.extend(["pass", to_discard])
        p2._script.extend(["pass"])
        p2_cleanup_discard = game.get_hand(p2).get_all()[0]
        p2._script.extend([p2_cleanup_discard])
        run_turn(game)

        assert game.get_graveyard(p1).contains(to_discard)
        assert len(game.get_hand(p1).get_all()) == len(hand_before)  # -1 +1

    def test_no_loot_on_own_upkeep(self) -> None:
        from engine.turn import run_turn

        deck1 = [Creature(name=f"D1-{i}", base_power=1, base_toughness=1)
                 for i in range(10)]
        deck2 = [Creature(name=f"D2-{i}", base_power=1, base_toughness=1)
                 for i in range(10)]
        game = create_game(deck1=deck1, deck2=deck2)
        p1, p2 = game.players
        dragon = LoreholdTheHistorian(owner=p1)
        game.get_battlefield(p1).add(dragon)
        dragon.owner = dragon.controller = p1
        dragon.register_triggers(game)

        # p1's own turn (turn 1: starting player skips the draw step).
        gy_before = len(game.get_graveyard(p1).get_all())
        p1_cleanup = game.get_hand(p1).get_all()[0]
        p1._script.extend([p1_cleanup])  # only the cleanup discard, if any
        run_turn(game)
        assert len(game.get_graveyard(p1).get_all()) == gy_before
