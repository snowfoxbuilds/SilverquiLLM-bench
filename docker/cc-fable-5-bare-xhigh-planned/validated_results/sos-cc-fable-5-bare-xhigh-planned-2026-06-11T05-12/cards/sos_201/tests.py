"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.game import draw_card
from engine.stack import priority_loop
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Step, Zone
from test_utils import advance_to_phase, create_game, set_board_state


class Zap(Instant):
    """Probe instant {R}: deal 2 damage to any target."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list[Any]:
        from engine.types import TargetRequirement

        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    hasattr(obj, "life")
                    or CardType.CREATURE in getattr(obj, "card_types", set())
                ),
                description="any target",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        chosen = getattr(self, "chosen_targets", None) or [None]
        if chosen[0] is not None:
            deal_damage(game, self, chosen[0], 2)


def _stock_library(game: Any, player_index: int, cards_top_first: list[Any]) -> None:
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for card in reversed(cards_top_first):
        card.owner = player
        card.controller = player
        library.add(card)


def _vanilla(n: int) -> list[Creature]:
    return [
        Creature(name=f"Filler {i}", base_power=1, base_toughness=1)
        for i in range(n)
    ]


def _setup_lorehold(game: Any, mana=None) -> Any:
    lh = LoreholdTheHistorian()
    set_board_state(game, 0, battlefield=[lh], mana=mana or {})
    lh.register_triggers(game)
    return lh


class TestProperties:
    def test_static_data(self) -> None:
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert card.base_power == 5 and card.base_toughness == 5
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords


class TestMiracle:
    def test_first_drawn_instant_may_be_miracle_cast(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _setup_lorehold(game, mana={ManaType.COLORLESS: 2})
        zap = Zap()
        _stock_library(game, 0, [zap])
        draw_card(game, p1)
        assert len(game.stack) == 1  # miracle trigger waiting
        p1._script.extend(["pass", True, p2, "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)
        assert p2.life == 18
        assert p1.zones[Zone.GRAVEYARD].contains(zap)
        assert p1.mana_pool.total() == 0  # {2} miracle cost was paid

    def test_not_first_draw_no_miracle(self) -> None:
        game = create_game()
        p1 = game.players[0]
        _setup_lorehold(game, mana={ManaType.COLORLESS: 2})
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        zap = Zap()
        _stock_library(game, 0, [bear, zap])
        draw_card(game, p1)  # first draw — a creature, no miracle
        draw_card(game, p1)  # the instant is the second draw
        assert game.stack.is_empty()
        assert p1.zones[Zone.HAND].contains(zap)

    def test_miracle_may_be_declined(self) -> None:
        game = create_game()
        p1 = game.players[0]
        _setup_lorehold(game, mana={ManaType.COLORLESS: 2})
        zap = Zap()
        _stock_library(game, 0, [zap])
        draw_card(game, p1)
        p1._script.extend(["pass", False])
        p2 = game.players[1]
        p2._script.extend(["pass"])
        priority_loop(game)
        assert p1.zones[Zone.HAND].contains(zap)
        assert p1.mana_pool.total() == 2

    def test_first_draw_resets_each_turn(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _setup_lorehold(game)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        zap = Zap()
        _stock_library(game, 0, [bear, zap])
        draw_card(game, p1)  # turn 1's first draw — a creature
        assert game.stack.is_empty()
        # Advance through a full turn rotation into player 1's next turn.
        for _ in range(2):
            advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
            game.advance_phase()
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        draw_card(game, p1)  # first draw of the new turn — the instant
        assert len(game.stack) == 1
        p1._script.extend(["pass", True, p2, "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)
        assert p2.life == 18


class TestUpkeepLoot:
    def test_opponent_upkeep_discard_to_draw(self) -> None:
        from engine.turn import run_turn

        game = create_game(deck1=_vanilla(12), deck2=_vanilla(12))
        p1, p2 = game.players
        lh = _setup_lorehold(game)
        discardme = Creature(name="Chaff", base_power=1, base_toughness=1)
        keeper = Creature(name="Keeper", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[discardme, keeper])
        library_before = len(p1.zones[Zone.LIBRARY])
        # Finish p1's turn 1 (decline attacking with Lorehold), then run
        # p2's turn — the loot trigger fires at p2's upkeep.
        p1._script.extend([None, "pass", discardme])
        p2._script.extend(["pass", None])
        run_turn(game)
        run_turn(game)
        assert p1.zones[Zone.GRAVEYARD].contains(discardme)
        assert p1.zones[Zone.HAND].contains(keeper)
        assert len(p1.zones[Zone.HAND]) == 2  # keeper + the drawn card
        assert len(p1.zones[Zone.LIBRARY]) == library_before - 1

    def test_loot_may_be_declined(self) -> None:
        from engine.turn import run_turn

        game = create_game(deck1=_vanilla(12), deck2=_vanilla(12))
        p1, p2 = game.players
        _setup_lorehold(game)
        keeper = Creature(name="Keeper", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[keeper])
        p1._script.extend([None, "pass", None])
        p2._script.extend(["pass", None])
        run_turn(game)
        run_turn(game)
        assert p1.zones[Zone.HAND].contains(keeper)
        assert len(p1.zones[Zone.HAND]) == 1
        assert len(p1.zones[Zone.GRAVEYARD]) == 0
