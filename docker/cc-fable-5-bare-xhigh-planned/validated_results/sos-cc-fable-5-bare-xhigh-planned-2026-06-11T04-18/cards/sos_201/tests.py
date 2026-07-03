"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.game import draw_card
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType
from test_utils import create_game, set_board_state


def _put_on_top(game, player_index, card) -> None:
    player = game.players[player_index]
    card.owner = player
    card.controller = player
    game.get_library(player).add(card)  # top = last


class TestStaticProperties:
    def test_keywords_and_stats(self) -> None:
        card = LoreholdTheHistorian()
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords
        assert card.base_power == 5
        assert card.base_toughness == 5
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")


class TestMiracle:
    def test_first_drawn_instant_can_be_miracle_cast(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[LoreholdTheHistorian()],
                        mana={ManaType.COLORLESS: 2})
        bolt = BurstLightning()
        _put_on_top(game, 0, bolt)
        draw_card(game, p1)
        # Resolve the miracle trigger, accept, target p2, resolve the bolt.
        p1._script.extend(["pass", True, p2, "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)
        assert p2.life == 18
        assert game.get_graveyard(p1).contains(bolt)
        assert p1.mana_pool.total() == 0  # paid {2}

    def test_decline_keeps_card_in_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[LoreholdTheHistorian()],
                        mana={ManaType.COLORLESS: 2})
        bolt = BurstLightning()
        _put_on_top(game, 0, bolt)
        draw_card(game, p1)
        p1._script.extend(["pass", False])
        game.players[1]._script.extend(["pass"])
        priority_loop(game)
        assert game.get_hand(p1).contains(bolt)
        assert p1.mana_pool.total() == 2  # nothing paid

    def test_second_draw_this_turn_is_not_miracled(self) -> None:
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[LoreholdTheHistorian()])
        first = Creature(name="Drawn Bear", base_power=2, base_toughness=2)
        second = Instant(name="Late Instant", mana_cost=ManaCost.parse("{1}"))
        _put_on_top(game, 0, second)
        _put_on_top(game, 0, first)  # first on top
        draw_card(game, p1)  # creature: no miracle (but counts as the first draw)
        draw_card(game, p1)  # instant, but not the first draw
        priority_loop(game)  # no trigger may be on the stack
        assert game.stack.is_empty()
        assert game.get_hand(p1).contains(second)
        assert p1.remaining_choices == 0

    def test_new_turn_resets_first_draw(self) -> None:
        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[LoreholdTheHistorian()])
        i1 = Instant(name="I1", mana_cost=ManaCost.parse("{1}"))
        i2 = Instant(name="I2", mana_cost=ManaCost.parse("{1}"))
        _put_on_top(game, 0, i2)
        _put_on_top(game, 0, i1)
        draw_card(game, p1)
        p1._script.extend(["pass", False])
        game.players[1]._script.extend(["pass"])
        priority_loop(game)
        game.turn_number += 1  # next turn
        draw_card(game, p1)
        p1._script.extend(["pass", False])
        game.players[1]._script.extend(["pass"])
        priority_loop(game)
        assert p1.remaining_choices == 0  # both prompts happened

    def test_opponent_draws_do_not_trigger(self) -> None:
        game = create_game()
        p2 = game.players[1]
        set_board_state(game, 0, battlefield=[LoreholdTheHistorian()])
        bolt = BurstLightning()
        _put_on_top(game, 1, bolt)
        draw_card(game, p2)
        assert game.stack.is_empty()  # no miracle trigger for p1's Lorehold


class TestUpkeepLoot:
    def _run_opponent_turn(self, game):
        from engine.turn import run_turn

        game.active_player_index = 1
        game.priority_player_index = 1
        run_turn(game)

    def test_loot_on_opponents_upkeep(self) -> None:
        game = create_game()
        p1, p2 = game.players
        # Libraries so draw steps don't deck anyone; p1's top is a creature
        # (no miracle prompt on the loot draw).
        _put_on_top(game, 1, Creature(name="P2 Card", base_power=1, base_toughness=1))
        replacement = Creature(name="Fresh", base_power=1, base_toughness=1)
        _put_on_top(game, 0, replacement)
        stale = Instant(name="Stale", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, battlefield=[LoreholdTheHistorian()], hand=[stale])
        # p2's upkeep: trigger resolves; p1 discards Stale, draws Fresh.
        p2._script.extend(["pass"])
        p1._script.extend(["pass", stale])
        self._run_opponent_turn(game)
        assert game.get_graveyard(p1).contains(stale)
        assert game.get_hand(p1).contains(replacement)

    def test_decline_loot(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _put_on_top(game, 1, Creature(name="P2 Card", base_power=1, base_toughness=1))
        stale = Instant(name="Stale", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, battlefield=[LoreholdTheHistorian()], hand=[stale])
        p2._script.extend(["pass"])
        p1._script.extend(["pass", None])
        self._run_opponent_turn(game)
        assert game.get_hand(p1).contains(stale)
        assert len(game.get_graveyard(p1).get_all()) == 0

    def test_no_trigger_on_own_upkeep(self) -> None:
        from engine.turn import run_turn

        game = create_game()
        p1 = game.players[0]
        _put_on_top(game, 0, Creature(name="P1 Card", base_power=1, base_toughness=1))
        lorehold = LoreholdTheHistorian()
        set_board_state(game, 0, battlefield=[lorehold])
        lorehold.summoning_sick = False
        # Own turn: no upkeep prompt. Scripts cover only declare-attackers.
        p1._script.extend([None])  # attack with nothing
        run_turn(game)
        assert p1.remaining_choices == 0
