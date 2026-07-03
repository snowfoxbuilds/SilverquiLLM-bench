"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.game import draw_card
from engine.stack import priority_loop
from engine.turn import run_turn
from engine.types import Keyword, ManaCost, ManaType, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state


class ProbeInstant(Instant):
    """Test-only instant: controller gains 3 life on resolve."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Probe Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 3


def _lorehold_ready(game) -> LoreholdTheHistorian:
    card = LoreholdTheHistorian(owner=None)
    set_board_state(game, 0, battlefield=[card])
    card.register_triggers(game)
    return card


class TestLoreholdProperties:
    def test_static_data(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords
        assert card.base_power == 5 and card.base_toughness == 5
        assert Supertype.LEGENDARY in card.supertypes


class TestLoreholdMiracle:
    def test_first_drawn_instant_cast_for_miracle_cost(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _lorehold_ready(game)
        probe = ProbeInstant()
        probe.owner = p1
        game.get_library(p1).add(probe)
        set_board_state(game, 0, battlefield=[c for c in game.get_battlefield(p1).get_all()],
                        mana={ManaType.COLORLESS: 2})
        p1._script.extend(["pass", True, "pass"])
        p2._script.extend(["pass", "pass"])
        drawn = draw_card(game, p1)
        assert drawn is probe
        priority_loop(game)
        assert p1.life == 23  # probe resolved
        assert game.get_graveyard(p1).contains(probe)
        assert p1.mana_pool.total() == 0  # the {2} miracle cost was paid

    def test_miracle_may_be_declined(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _lorehold_ready(game)
        probe = ProbeInstant()
        probe.owner = p1
        game.get_library(p1).add(probe)
        set_board_state(game, 0, battlefield=[c for c in game.get_battlefield(p1).get_all()],
                        mana={ManaType.COLORLESS: 2})
        p1._script.extend(["pass", False])
        p2._script.extend(["pass"])
        draw_card(game, p1)
        priority_loop(game)
        assert game.get_hand(p1).contains(probe)  # stayed in hand
        assert p1.mana_pool.total() == 2  # nothing paid
        assert p1.life == 20

    def test_second_draw_is_not_a_miracle(self) -> None:
        """A creature eats the first draw; the instant drawn second gets
        no miracle window (empty scripts — any prompt would raise)."""
        game = create_game()
        p1 = game.players[0]
        _lorehold_ready(game)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        probe = ProbeInstant()
        lib = game.get_library(p1)
        for c in (probe, bear):  # bear on top — drawn first
            c.owner = p1
            lib.add(c)
        set_board_state(game, 0, battlefield=[c for c in game.get_battlefield(p1).get_all()],
                        mana={ManaType.COLORLESS: 2})
        draw_card(game, p1)
        assert game.stack.is_empty()  # creature → no miracle trigger
        draw_card(game, p1)
        assert game.stack.is_empty()  # second draw → no miracle trigger
        assert game.get_hand(p1).contains(probe)

    def test_no_mana_no_prompt(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _lorehold_ready(game)
        probe = ProbeInstant()
        probe.owner = p1
        game.get_library(p1).add(probe)
        set_board_state(game, 0, battlefield=[c for c in game.get_battlefield(p1).get_all()],
                        mana={})
        p1._script.extend(["pass"])
        p2._script.extend(["pass"])
        draw_card(game, p1)
        priority_loop(game)  # trigger resolves but cannot pay — no prompt
        assert game.get_hand(p1).contains(probe)


class TestLoreholdLoot:
    def test_loot_on_opponent_upkeep(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _lorehold_ready(game)
        spare = Creature(name="Spare", base_power=1, base_toughness=1)
        topdeck = Creature(name="Topdeck", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[spare])
        topdeck.owner = p1
        game.get_library(p1).add(topdeck)
        # p2 needs a library for their draw step.
        filler = Creature(name="Filler", base_power=1, base_toughness=1)
        filler.owner = p2
        game.get_library(p2).add(filler)

        # Run p2's whole turn; the loot trigger fires at their upkeep.
        game.active_player_index = 1
        game.priority_player_index = 1
        game._normal_next_index = 0
        game.phase = Phase.BEGINNING
        game.step = Step.UNTAP
        p2._script.extend(["pass"])
        p1._script.extend(["pass", spare])  # pass priority, then discard Spare
        run_turn(game)
        assert game.get_graveyard(p1).contains(spare)  # discarded
        assert game.get_hand(p1).contains(topdeck)  # drew a replacement

    def test_loot_decline(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _lorehold_ready(game)
        spare = Creature(name="Spare", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[spare])
        filler = Creature(name="Filler", base_power=1, base_toughness=1)
        filler.owner = p2
        game.get_library(p2).add(filler)
        game.active_player_index = 1
        game.priority_player_index = 1
        game._normal_next_index = 0
        game.phase = Phase.BEGINNING
        game.step = Step.UNTAP
        p2._script.extend(["pass"])
        p1._script.extend(["pass", None])  # decline the loot
        run_turn(game)
        assert game.get_hand(p1).contains(spare)
        assert len(game.get_graveyard(p1)) == 0
