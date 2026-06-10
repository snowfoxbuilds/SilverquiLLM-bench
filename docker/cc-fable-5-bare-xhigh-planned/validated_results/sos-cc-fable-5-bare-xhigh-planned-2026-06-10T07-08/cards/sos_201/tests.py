"""Tests for SOS 201 — Lorehold, the Historian (miracle grant + loot)."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.game import draw_card
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType, Phase, Step, Zone
from test_utils import create_game, set_board_state


def _instant(name: str = "Bolt") -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse("{3}{R}"))


def _bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _setup(library_top, *, mana=None):
    """Lorehold on p1's battlefield with triggers registered."""
    game = create_game()
    p1 = game.players[0]
    lorehold = LoreholdTheHistorian()
    set_board_state(game, 0, battlefield=[lorehold], mana=mana or {})
    lorehold.register_triggers(game)
    for card in library_top:
        card.owner = card.controller = p1
        p1.zones[Zone.LIBRARY].add(card)
    # Fresh-turn draw counters for a clean "first draw this turn".
    p1.cards_drawn_this_turn = 0
    return game, lorehold


class TestProperties:
    def test_static_data(self) -> None:
        card = LoreholdTheHistorian()
        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords
        assert {"Elder", "Dragon"} <= card.subtypes
        assert card.base_power == 5 and card.base_toughness == 5


class TestMiracle:
    def test_first_drawn_instant_cast_for_two(self) -> None:
        bolt = _instant()
        game, _ = _setup([bolt], mana={ManaType.COLORLESS: 2})
        p1, p2 = game.players

        draw_card(game, p1)
        assert len(game.stack) == 1  # miracle window trigger
        p1._script.extend(["pass", True, "pass"])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)

        assert p1.zones[Zone.GRAVEYARD].contains(bolt)  # resolved
        assert not p1.zones[Zone.HAND].contains(bolt)
        assert p1.mana_pool.total() == 0  # the {2} was paid

    def test_second_draw_no_miracle(self) -> None:
        """A creature eats the first draw; the instant drawn second gets no window."""
        bolt, bear = _instant(), _bear()
        game, _ = _setup([bolt, bear])  # bear on top, bolt below
        p1 = game.players[0]

        draw_card(game, p1)  # bear — not instant/sorcery, no trigger
        assert game.stack.is_empty()
        draw_card(game, p1)  # bolt — but not the first draw this turn
        assert game.stack.is_empty()
        assert p1.zones[Zone.HAND].contains(bolt)

    def test_decline_miracle_card_stays_in_hand(self) -> None:
        bolt = _instant()
        game, _ = _setup([bolt], mana={ManaType.COLORLESS: 2})
        p1, p2 = game.players

        draw_card(game, p1)
        p1._script.extend(["pass", False])
        p2._script.extend(["pass"])
        priority_loop(game)

        assert p1.zones[Zone.HAND].contains(bolt)
        assert p1.mana_pool.total() == 2  # nothing paid

    def test_no_mana_no_cast(self) -> None:
        bolt = _instant()
        game, _ = _setup([bolt])  # no mana available
        p1, p2 = game.players

        draw_card(game, p1)
        p1._script.extend(["pass", True])
        p2._script.extend(["pass"])
        priority_loop(game)

        assert p1.zones[Zone.HAND].contains(bolt)


class TestOpponentUpkeepLoot:
    def test_loot_on_opponents_upkeep(self) -> None:
        """During p2's turn, p1 may discard a card to draw a card."""
        game, _ = _setup([])
        p1, p2 = game.players
        stale = _bear("Stale")
        fresh = _bear("Fresh")
        set_board_state(game, 0, hand=[stale])
        fresh.owner = fresh.controller = p1
        p1.zones[Zone.LIBRARY].add(fresh)
        # p2 needs library for their draw step.
        for i in range(2):
            c = _bear(f"P2-{i}")
            c.owner = c.controller = p2
            p2.zones[Zone.LIBRARY].add(c)

        # Run p2's full turn through the real turn loop.
        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.BEGINNING
        game.step = Step.UNTAP
        p1._script.extend(["pass", stale])
        p2._script.extend(["pass"])
        from engine.turn import run_turn

        run_turn(game)

        assert p1.zones[Zone.GRAVEYARD].contains(stale)
        assert p1.zones[Zone.HAND].contains(fresh)

    def test_no_loot_on_own_upkeep(self) -> None:
        """No prompt on your own upkeep — an unscripted choose would raise."""
        game, _ = _setup([_bear("Draw1"), _bear("Draw2")])
        p1 = game.players[0]
        set_board_state(game, 0, hand=[_bear("Handcard")])
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.BEGINNING
        game.step = Step.UNTAP
        # Only the declare-attackers choice is scripted (attack with nothing);
        # an upkeep loot prompt would exhaust the script and raise.
        p1._script.extend([[]])
        from engine.turn import run_turn

        run_turn(game)

        assert len(p1.zones[Zone.GRAVEYARD]) == 0
