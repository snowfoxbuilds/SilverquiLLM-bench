"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.game import draw_card
from engine.stack import priority_loop
from engine.turn import run_turn
from engine.types import Keyword, ManaCost, ManaType, Phase, Step
from test_utils import create_game, set_board_state


def _filler(name: str) -> Creature:
    return Creature(name=name, base_power=1, base_toughness=1,
                    mana_cost=ManaCost(generic=1))


def _add_to_library(game, player_index, card):
    player = game.players[player_index]
    card.owner = card.controller = player
    game.get_library(player).add(card)


def _setup_lorehold(game):
    lorehold = LoreholdTheHistorian()
    set_board_state(game, 0, battlefield=[lorehold])
    lorehold.register_triggers(game)
    return lorehold


class TestLoreholdStatic:
    def test_keywords(self) -> None:
        l = LoreholdTheHistorian()
        assert Keyword.FLYING in l.keywords
        assert Keyword.HASTE in l.keywords
        assert l.base_power == 5 and l.base_toughness == 5


class TestMiracle:
    def test_first_drawn_instant_cast_for_two(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        _setup_lorehold(game)
        trick = Instant(name="Costly Trick", mana_cost=ManaCost(generic=5))
        _add_to_library(game, 0, trick)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})

        p1._script.extend(["pass", True, "pass"])
        game.players[1]._script.extend(["pass", "pass"])
        draw_card(game, p1)  # first draw this turn
        priority_loop(game)

        # Cast for {2} instead of {5} and resolved.
        assert game.get_graveyard(p1).contains(trick)
        assert p1.mana_pool.total() == 0

    def test_miracle_declined_card_stays_in_hand(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        _setup_lorehold(game)
        trick = Instant(name="Costly Trick", mana_cost=ManaCost(generic=5))
        _add_to_library(game, 0, trick)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})

        p1._script.extend(["pass", False])
        game.players[1]._script.extend(["pass"])
        draw_card(game, p1)
        priority_loop(game)

        assert game.get_hand(p1).contains(trick)
        assert p1.mana_pool.total() == 2  # nothing paid

    def test_second_draw_no_miracle(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        _setup_lorehold(game)
        trick = Instant(name="Costly Trick", mana_cost=ManaCost(generic=5))
        bear = _filler("Bear")
        _add_to_library(game, 0, trick)
        _add_to_library(game, 0, bear)  # bear on top — drawn first
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})

        draw_card(game, p1)  # bear: not instant/sorcery — no trigger
        assert game.stack.is_empty()
        draw_card(game, p1)  # trick: not the first draw — no trigger
        assert game.stack.is_empty()
        assert game.get_hand(p1).contains(trick)

    def test_non_first_drawn_creature_no_miracle(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        _setup_lorehold(game)
        bear = _filler("Bear")
        _add_to_library(game, 0, bear)
        draw_card(game, p1)
        assert game.stack.is_empty()


class TestOpponentUpkeepLoot:
    def _run_p2_turn(self, game):
        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.BEGINNING
        game.step = Step.UNTAP
        run_turn(game)

    def test_discard_to_draw_on_opponent_upkeep(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        lorehold = _setup_lorehold(game)
        junk = _filler("Junk")
        fresh = _filler("Fresh")
        set_board_state(game, 0, hand=[junk])
        _add_to_library(game, 0, fresh)
        _add_to_library(game, 1, _filler("P2 Draw"))

        # p1: pass on the trigger, then discard Junk.
        p1._script.extend(["pass", junk])
        p2._script.extend(["pass"])
        self._run_p2_turn(game)

        assert game.get_graveyard(p1).contains(junk)
        assert game.get_hand(p1).contains(fresh)

    def test_loot_declined(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        _setup_lorehold(game)
        junk = _filler("Junk")
        fresh = _filler("Fresh")
        set_board_state(game, 0, hand=[junk])
        _add_to_library(game, 0, fresh)
        _add_to_library(game, 1, _filler("P2 Draw"))

        p1._script.extend(["pass", None])
        p2._script.extend(["pass"])
        self._run_p2_turn(game)

        assert game.get_hand(p1).contains(junk)
        assert game.get_library(p1).contains(fresh)  # no draw

    def test_no_loot_on_own_upkeep(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        _setup_lorehold(game)
        set_board_state(game, 0, hand=[_filler("Junk")])
        _add_to_library(game, 0, _filler("P1 Draw"))
        # P1's own turn: upkeep trigger must not fire.  The only prompt is
        # the attack declaration (Lorehold has haste) — decline it.
        p1._script.append(None)
        run_turn(game)
        assert len(game.get_graveyard(p1)) == 0
