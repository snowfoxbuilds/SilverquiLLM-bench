"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.casting import resolve_top
from engine.game import draw_card
from engine.turn import run_turn
from engine.types import Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import advance_to_phase, create_game, set_board_state


class LifeSip(Instant):
    """Observable test instant: gain 1 life."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Life Sip")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        super().__init__(**kwargs)

    def on_resolve(self, game) -> None:
        if self.controller is not None:
            self.controller.life += 1


def _put_on_library(game, player_index, cards_top_first):
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for card in reversed(cards_top_first):
        card.owner = player
        card.controller = player
        library.add(card)


def _setup_with_lorehold():
    game = create_game()
    p1 = game.players[0]
    lorehold = LoreholdTheHistorian(owner=p1)
    set_board_state(game, 0, battlefield=[lorehold])
    lorehold.register_triggers(game)
    # Move to a fresh turn so the registration turn's "already drawn"
    # stamp doesn't block the first test draw.
    while game.turn_number == 1:
        game.advance_phase()
    return game, p1, lorehold


class TestLoreholdStatics:
    def test_keywords(self):
        card = LoreholdTheHistorian()
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords
        assert card.base_power == 5 and card.base_toughness == 5


class TestLoreholdMiracle:
    def test_first_drawn_instant_can_be_miracle_cast_for_2(self):
        game, p1, _ = _setup_with_lorehold()
        sip = LifeSip()
        _put_on_library(game, 0, [sip])
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        draw_card(game, p1)
        assert len(game.stack) == 1  # miracle trigger
        p1._script.append(True)  # cast it for {2}
        resolve_top(game)        # trigger: pays {2}, casts from hand
        resolve_top(game)        # Life Sip resolves
        assert p1.life == 21
        assert game.get_graveyard(p1).contains(sip)
        assert p1.mana_pool.total() == 0

    def test_second_draw_no_miracle(self):
        game, p1, _ = _setup_with_lorehold()
        filler = Creature(name="Filler", base_power=1, base_toughness=1)
        sip = LifeSip()
        _put_on_library(game, 0, [filler, sip])
        draw_card(game, p1)  # first draw: a creature — no trigger
        assert game.stack.is_empty()
        draw_card(game, p1)  # second draw: instant, but not first
        assert game.stack.is_empty()
        assert game.get_hand(p1).contains(sip)

    def test_decline_miracle_keeps_card_in_hand(self):
        game, p1, _ = _setup_with_lorehold()
        sip = LifeSip()
        _put_on_library(game, 0, [sip])
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        draw_card(game, p1)
        p1._script.append(False)
        resolve_top(game)
        assert game.get_hand(p1).contains(sip)
        assert p1.mana_pool.total() == 2  # nothing was paid

    def test_cannot_pay_miracle_cost_keeps_card(self):
        game, p1, _ = _setup_with_lorehold()
        sip = LifeSip()
        _put_on_library(game, 0, [sip])
        set_board_state(game, 0, mana={ManaType.COLORLESS: 1})
        draw_card(game, p1)
        p1._script.append(True)
        resolve_top(game)
        assert game.get_hand(p1).contains(sip)
        assert p1.life == 20

    def test_next_turn_first_draw_eligible_again(self):
        game, p1, _ = _setup_with_lorehold()
        first = Creature(name="First", base_power=1, base_toughness=1)
        sip = LifeSip()
        _put_on_library(game, 0, [first, sip])
        draw_card(game, p1)  # consumes this turn's first draw
        start_turn = game.turn_number
        while game.turn_number == start_turn:
            game.advance_phase()
        draw_card(game, p1)  # new turn: first draw again, instant
        assert len(game.stack) == 1


class TestLoreholdLoot:
    def test_loot_at_opponents_upkeep(self):
        game = create_game()
        p1, p2 = game.players
        lorehold = LoreholdTheHistorian(owner=p1)
        spare = Creature(name="Spare Card", base_power=1, base_toughness=1)
        draw_me = Creature(name="Drawn Card", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[lorehold], hand=[spare])
        lorehold.register_triggers(game)
        _put_on_library(game, 0, [draw_me])
        _put_on_library(game, 1, [
            Creature(name=f"P2 Card {i}", base_power=1, base_toughness=1)
            for i in range(2)
        ])
        # p1's own turn first: no loot at own upkeep.
        p1._script.append(None)  # decline attacking with Lorehold
        run_turn(game)
        assert game.get_hand(p1).contains(spare)
        # p2's turn: loot triggers at p2's upkeep.
        p2._script.append("pass")
        p1._script.append("pass")
        p1._script.append(spare)  # discard choice
        run_turn(game)
        assert game.get_graveyard(p1).contains(spare)
        assert game.get_hand(p1).contains(draw_me)
