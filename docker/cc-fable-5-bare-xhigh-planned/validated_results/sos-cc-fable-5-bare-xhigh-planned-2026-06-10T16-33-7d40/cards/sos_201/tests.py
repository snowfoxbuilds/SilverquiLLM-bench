"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.game import draw_card
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType, Phase, Step, Zone
from test_utils import create_game, set_board_state


class GainOne(Instant):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Gain One")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{W}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 1


def _setup(library_cards=None, hand=None, mana=None):
    game = create_game()
    lorehold = LoreholdTheHistorian(owner=None)
    set_board_state(game, 0, battlefield=[lorehold], hand=hand or [],
                    mana=mana or {})
    lorehold.register_triggers(game)
    p0 = game.players[0]
    for card in library_cards or []:
        card.owner = p0
        card.controller = p0
        p0.zones[Zone.LIBRARY].add(card)  # last added ends up on top
    return game, lorehold


class TestLoreholdProperties:
    def test_static_data(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords
        assert card.base_power == 5 and card.base_toughness == 5


class TestMiracle:
    def test_first_drawn_instant_cast_for_two(self) -> None:
        gain = GainOne()
        game, _ = _setup(library_cards=[gain],
                         mana={ManaType.COLORLESS: 2})
        p0, p1 = game.players
        draw_card(game, p0)
        # Miracle trigger is on the stack; resolve it, accept, resolve spell.
        p0._script.extend(["pass", True, "pass"])
        p1._script.extend(["pass", "pass"])
        priority_loop(game)
        assert p0.life == 21
        assert gain in p0.zones[Zone.GRAVEYARD].get_all()
        # {2} miracle cost paid instead of {4}{W}.
        assert p0.mana_pool.total() == 0

    def test_not_first_draw_no_miracle(self) -> None:
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        gain = GainOne()
        # bear on top, gain below it: first draw is the creature.
        game, _ = _setup(library_cards=[gain, bear],
                         mana={ManaType.COLORLESS: 2})
        p0, p1 = game.players
        draw_card(game, p0)   # first draw: creature, no trigger
        assert game.stack.is_empty()
        draw_card(game, p0)   # second draw: instant, but not first
        assert game.stack.is_empty()
        assert gain in p0.zones[Zone.HAND].get_all()

    def test_resets_each_turn(self) -> None:
        gain = GainOne()
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, _ = _setup(library_cards=[gain, bear],
                         mana={ManaType.COLORLESS: 2})
        p0, p1 = game.players
        draw_card(game, p0)   # turn 1 first draw: creature
        assert game.stack.is_empty()
        game.turn_number += 1
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        draw_card(game, p0)   # turn 2 first draw: the instant
        assert len(game.stack) == 1
        p0._script.extend(["pass", True, "pass"])
        p1._script.extend(["pass", "pass"])
        priority_loop(game)
        assert p0.life == 21

    def test_may_decline_miracle(self) -> None:
        gain = GainOne()
        game, _ = _setup(library_cards=[gain],
                         mana={ManaType.COLORLESS: 2})
        p0, p1 = game.players
        draw_card(game, p0)
        p0._script.extend(["pass", False])
        p1._script.extend(["pass"])
        priority_loop(game)
        assert gain in p0.zones[Zone.HAND].get_all()
        assert p0.mana_pool.total() == 2

    def test_no_mana_no_miracle_prompt(self) -> None:
        gain = GainOne()
        game, _ = _setup(library_cards=[gain])  # no mana available
        p0, p1 = game.players
        draw_card(game, p0)
        # Trigger still resolves but cannot pay {2}: no yes/no consumed.
        p0._script.extend(["pass"])
        p1._script.extend(["pass"])
        priority_loop(game)
        assert gain in p0.zones[Zone.HAND].get_all()


class TestLoot:
    def test_loot_at_opponents_upkeep(self) -> None:
        from engine.turn import run_turn

        spare = Instant(name="Spare", mana_cost=ManaCost.parse("{U}"))
        top = Creature(name="TopCard", base_power=1, base_toughness=1)
        game, _ = _setup(library_cards=[top], hand=[spare])
        p0, p1 = game.players
        # Give the opponent a library card for their draw step.
        filler = Creature(name="OppCard", base_power=1, base_toughness=1)
        filler.owner = filler.controller = p1
        p1.zones[Zone.LIBRARY].add(filler)

        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.BEGINNING
        game.step = Step.UNTAP
        # Upkeep trigger: both pass, then p0 chooses the discard.
        p1._script.extend(["pass", []])
        p0._script.extend(["pass", spare])
        run_turn(game)

        assert spare in p0.zones[Zone.GRAVEYARD].get_all()
        hand_names = [c.name for c in p0.zones[Zone.HAND].get_all()]
        assert "TopCard" in hand_names

    def test_loot_decline(self) -> None:
        from engine.turn import run_turn

        spare = Instant(name="Spare", mana_cost=ManaCost.parse("{U}"))
        top = Creature(name="TopCard", base_power=1, base_toughness=1)
        game, _ = _setup(library_cards=[top], hand=[spare])
        p0, p1 = game.players
        filler = Creature(name="OppCard", base_power=1, base_toughness=1)
        filler.owner = filler.controller = p1
        p1.zones[Zone.LIBRARY].add(filler)

        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.BEGINNING
        game.step = Step.UNTAP
        p1._script.extend(["pass", []])
        p0._script.extend(["pass", None])
        run_turn(game)

        assert spare in p0.zones[Zone.HAND].get_all()
        assert top not in p0.zones[Zone.HAND].get_all()
