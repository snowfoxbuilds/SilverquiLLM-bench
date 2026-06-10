"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from engine.card import Creature, Instant
from engine.game import draw_card
from engine.stack import priority_loop
from engine.turn import run_turn
from engine.types import Keyword, ManaType, Phase, Step, Zone
from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from test_utils import create_game, set_board_state


def _put_on_library(player, cards) -> None:
    """cards[0] ends up on top."""
    for c in reversed(cards):
        c.owner = player
        c.controller = player
        player.zones[Zone.LIBRARY].add(c)


class TestMiracle:
    def test_first_drawn_spell_may_be_miracle_cast(self) -> None:
        """First draw of the turn is an instant → may cast it for {2}."""
        game = create_game(scripts=(["pass", True, "pass"], ["pass"] * 3))
        p1 = game.players[0]
        lore = LoreholdTheHistorian()
        zap = Instant(name="Zap")
        set_board_state(game, 0, battlefield=[lore],
                        mana={ManaType.COLORLESS: 2})
        lore.register_triggers(game)
        _put_on_library(p1, [zap])
        draw_card(game, p1)
        assert len(game.stack) == 1  # miracle trigger
        priority_loop(game)
        assert p1.zones[Zone.GRAVEYARD].contains(zap)  # cast + resolved
        assert p1.mana_pool.total() == 0  # {2} miracle cost paid

    def test_miracle_declined_card_stays_in_hand(self) -> None:
        game = create_game(scripts=(["pass", False], ["pass"] * 2))
        p1 = game.players[0]
        lore = LoreholdTheHistorian()
        zap = Instant(name="Zap")
        set_board_state(game, 0, battlefield=[lore],
                        mana={ManaType.COLORLESS: 2})
        lore.register_triggers(game)
        _put_on_library(p1, [zap])
        draw_card(game, p1)
        priority_loop(game)
        assert p1.zones[Zone.HAND].contains(zap)
        assert p1.mana_pool.total() == 2  # nothing paid

    def test_no_miracle_on_second_draw_or_non_spell(self) -> None:
        """A creature first, then an instant: neither offers miracle."""
        game = create_game()
        p1 = game.players[0]
        lore = LoreholdTheHistorian()
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        zap = Instant(name="Zap")
        set_board_state(game, 0, battlefield=[lore],
                        mana={ManaType.COLORLESS: 2})
        lore.register_triggers(game)
        _put_on_library(p1, [bear, zap])
        draw_card(game, p1)  # creature — not instant/sorcery
        assert game.stack.is_empty()
        draw_card(game, p1)  # instant — but second draw this turn
        assert game.stack.is_empty()

    def test_cannot_pay_miracle_cost_card_stays(self) -> None:
        game = create_game(scripts=(["pass", True], ["pass"] * 2))
        p1 = game.players[0]
        lore = LoreholdTheHistorian()
        zap = Instant(name="Zap")
        set_board_state(game, 0, battlefield=[lore],
                        mana={ManaType.COLORLESS: 1})  # not enough for {2}
        lore.register_triggers(game)
        _put_on_library(p1, [zap])
        draw_card(game, p1)
        priority_loop(game)
        assert p1.zones[Zone.HAND].contains(zap)
        assert p1.mana_pool.total() == 1


class TestUpkeepLoot:
    def test_opponent_upkeep_discard_to_draw(self) -> None:
        """During P2's upkeep (real turn loop) P1 may loot 1."""
        old_card = Instant(name="Old")
        new_card = Creature(name="New", base_power=1, base_toughness=1)
        # P1 prompts: priority pass at upkeep, loot choice, then passes.
        game = create_game(scripts=(["pass", old_card] + ["pass"] * 6,
                                    ["pass"] * 8 + [None]))
        p1, p2 = game.players
        lore = LoreholdTheHistorian()
        set_board_state(game, 0, battlefield=[lore], hand=[old_card])
        lore.register_triggers(game)
        _put_on_library(p1, [new_card])
        _put_on_library(p2, [Instant(name="P2Draw")])

        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.BEGINNING
        game.step = Step.UNTAP
        run_turn(game)

        assert p1.zones[Zone.GRAVEYARD].contains(old_card)
        assert p1.zones[Zone.HAND].contains(new_card)
        assert len(p1.zones[Zone.LIBRARY]) == 0

    def test_no_loot_on_own_upkeep(self) -> None:
        """P1's own turn: no loot prompt fires (empty script never popped)."""
        game = create_game(scripts=([None], [None]))
        p1, p2 = game.players
        lore = LoreholdTheHistorian()
        keep = Instant(name="Keep")
        set_board_state(game, 0, battlefield=[lore], hand=[keep])
        lore.register_triggers(game)
        _put_on_library(p1, [Creature(name="Top", base_power=1, base_toughness=1)])

        game.turn_number = 2  # not the no-draw first turn
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.BEGINNING
        game.step = Step.UNTAP
        run_turn(game)

        assert p1.zones[Zone.HAND].contains(keep)
        assert len(p1.zones[Zone.GRAVEYARD]) == 0

    def test_keywords(self) -> None:
        lore = LoreholdTheHistorian()
        assert Keyword.FLYING in lore.keywords
        assert Keyword.HASTE in lore.keywords
