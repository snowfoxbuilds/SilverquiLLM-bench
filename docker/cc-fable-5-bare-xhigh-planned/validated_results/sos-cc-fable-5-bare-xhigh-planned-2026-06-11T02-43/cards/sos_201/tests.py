"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.game import draw_card
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


def _library_add(game, player_index, card):
    player = game.players[player_index]
    card.owner = player
    card.controller = player
    player.zones[Zone.LIBRARY].add(card)


def _setup(p1_mana=None):
    game = create_game(scripts=([], []))
    lorehold = LoreholdTheHistorian()
    set_board_state(game, 0, battlefield=[lorehold], hand=[],
                    mana=p1_mana or {})
    lorehold.register_triggers(game)  # set_board_state skips ETB hooks
    return game, lorehold


class TestProperties:
    def test_static_data(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert card.base_power == 5 and card.base_toughness == 5
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords


class TestMiracle:
    def test_first_drawn_instant_cast_for_two(self) -> None:
        game, lorehold = _setup(p1_mana={ManaType.COLORLESS: 2})
        p1, p2 = game.players
        trick = Instant(name="Costly Trick", mana_cost=ManaCost.parse("{4}{U}"))
        _library_add(game, 0, trick)

        draw_card(game, p1)                       # real draw fires the event
        assert len(game.stack) == 1               # miracle trigger waiting

        p1._script.extend(["pass", True, "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)

        assert game.get_graveyard(p1).contains(trick)   # cast and resolved
        assert not game.get_hand(p1).contains(trick)
        assert p1.mana_pool.total() == 0                # paid {2}

    def test_miracle_may_be_declined(self) -> None:
        game, lorehold = _setup(p1_mana={ManaType.COLORLESS: 2})
        p1, p2 = game.players
        trick = Instant(name="Trick", mana_cost=ManaCost.parse("{4}{U}"))
        _library_add(game, 0, trick)

        draw_card(game, p1)
        p1._script.extend(["pass", False])
        p2._script.extend(["pass"])
        priority_loop(game)

        assert game.get_hand(p1).contains(trick)        # stayed in hand
        assert p1.mana_pool.total() == 2

    def test_second_draw_no_miracle(self) -> None:
        game, lorehold = _setup()
        p1 = game.players[0]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        trick = Instant(name="Trick", mana_cost=ManaCost.parse("{U}"))
        _library_add(game, 0, trick)                    # drawn second
        _library_add(game, 0, bear)                     # on top, drawn first

        draw_card(game, p1)                             # bear: not instant
        assert game.stack.is_empty()
        draw_card(game, p1)                             # trick: not first
        assert game.stack.is_empty()
        assert game.get_hand(p1).contains(trick)

    def test_new_turn_resets_first_draw(self) -> None:
        game, lorehold = _setup(p1_mana={})
        p1, p2 = game.players
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        trick = Instant(name="Trick", mana_cost=ManaCost.parse("{U}"))
        _library_add(game, 0, trick)
        _library_add(game, 0, bear)

        draw_card(game, p1)                             # turn N first draw
        assert game.stack.is_empty()

        game.turn_number += 1                           # next turn
        draw_card(game, p1)                             # first draw again
        assert len(game.stack) == 1                     # miracle for Trick

        p1._script.extend(["pass", False])
        p2._script.extend(["pass"])
        priority_loop(game)


class TestOpponentUpkeepLoot:
    def _run_opponent_turn(self, game):
        from engine.turn import run_turn

        game.active_player_index = 1
        game.priority_player_index = 1
        game._normal_next_index = 0
        game.phase = Phase.BEGINNING
        game.step = None
        from engine.types import Step

        game.step = Step.UNTAP
        run_turn(game)

    def test_discard_to_draw_on_opponent_upkeep(self) -> None:
        game, lorehold = _setup()
        p1, p2 = game.players
        keeper = Instant(name="Keeper", mana_cost=ManaCost.parse("{U}"))
        chaff = Creature(name="Chaff", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[keeper, chaff])
        fresh = Instant(name="Fresh", mana_cost=ManaCost.parse("{R}"))
        _library_add(game, 0, fresh)
        # Opponent needs a library card for their draw step.
        _library_add(game, 1, Creature(name="OppCard", base_power=1, base_toughness=1))

        # Scripts: pass on the upkeep trigger, then discard Chaff.  The
        # loot draw (Fresh) is p1's first draw this turn and Fresh is an
        # instant → miracle triggers; decline it.
        p1._script.extend(["pass", chaff, "pass", False])
        p2._script.extend(["pass", "pass"])
        self._run_opponent_turn(game)

        assert game.get_graveyard(p1).contains(chaff)   # discarded
        assert game.get_hand(p1).contains(fresh)        # drew a card
        assert game.get_hand(p1).contains(keeper)

    def test_loot_declined(self) -> None:
        game, lorehold = _setup()
        p1, p2 = game.players
        keeper = Instant(name="Keeper", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, hand=[keeper])
        _library_add(game, 1, Creature(name="OppCard", base_power=1, base_toughness=1))

        p1._script.extend(["pass", None])
        p2._script.extend(["pass"])
        self._run_opponent_turn(game)

        assert game.get_hand(p1).contains(keeper)
        assert len(game.get_hand(p1)) == 1
        assert game.get_graveyard(p1).get_all() == []
