"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant
from engine.casting import resolve_top
from engine.game import draw_card
from engine.turn import run_turn
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class LifeProbe(Instant):
    """Test-local instant: you gain 1 life. Mana value 5."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Life Probe")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 1


def _setup(game, mana=None):
    p1 = game.players[0]
    lh = LoreholdTheHistorian(owner=p1)
    set_board_state(game, 0, battlefield=[lh],
                    mana=mana if mana is not None else {})
    lh.register_triggers(game)
    return lh


def _stock_library(player, cards):
    library = player.zones[Zone.LIBRARY]
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


class TestMiracle:
    def test_first_drawn_instant_cast_for_two(self):
        """A 5-MV instant drawn first this turn is cast for just {2}."""
        game = create_game()
        p1 = game.players[0]
        _setup(game, mana={ManaType.COLORLESS: 2})
        probe = LifeProbe(owner=p1)
        _stock_library(p1, [probe])

        draw_card(game, p1)
        assert len(game.stack) == 1  # miracle trigger
        p1._script.append(True)
        resolve_top(game)  # trigger → pays {2}, casts from hand
        resolve_top(game)  # the spell itself

        assert p1.life == 21
        assert p1.zones[Zone.GRAVEYARD].contains(probe)
        assert p1.mana_pool.total() == 0

    def test_second_draw_gets_no_miracle(self):
        game = create_game()
        p1 = game.players[0]
        _setup(game, mana={ManaType.COLORLESS: 2})
        probe = LifeProbe(owner=p1)
        filler = Creature(name="Filler", base_power=1, base_toughness=1,
                          mana_cost=ManaCost.parse("{1}"))
        _stock_library(p1, [probe, filler])  # filler on top

        draw_card(game, p1)  # first draw: creature — no miracle
        assert game.stack.is_empty()
        draw_card(game, p1)  # second draw: the instant — too late
        assert game.stack.is_empty()
        assert p1.zones[Zone.HAND].contains(probe)

    def test_may_decline_miracle(self):
        game = create_game()
        p1 = game.players[0]
        _setup(game, mana={ManaType.COLORLESS: 2})
        probe = LifeProbe(owner=p1)
        _stock_library(p1, [probe])

        draw_card(game, p1)
        p1._script.append(False)
        resolve_top(game)

        assert game.stack.is_empty()
        assert p1.zones[Zone.HAND].contains(probe)
        assert p1.mana_pool.total() == 2  # nothing paid

    def test_no_mana_no_miracle_cast(self):
        """With less than {2} available the card simply stays in hand."""
        game = create_game()
        p1 = game.players[0]
        _setup(game, mana={ManaType.COLORLESS: 1})
        probe = LifeProbe(owner=p1)
        _stock_library(p1, [probe])

        draw_card(game, p1)
        resolve_top(game)  # no prompt consumed — script stays empty

        assert p1.zones[Zone.HAND].contains(probe)
        assert len(p1._script) == 0

    def test_keywords(self):
        lh = LoreholdTheHistorian(owner=None)
        assert Keyword.FLYING in lh.keywords
        assert Keyword.HASTE in lh.keywords


class TestOpponentUpkeepLoot:
    def _run_two_turns(self, game, p1_choices):
        """Run p1's turn 1 and p2's turn 2 through the real turn loop."""
        p1, p2 = game.players
        # Turn 1 (p1): only prompt is declare-attackers (decline).
        p1._script.append(None)
        run_turn(game)
        # Turn 2 (p2): upkeep trigger → both pass priority, then choices.
        p2._script.append("pass")
        p1._script.append("pass")
        p1._script.extend(p1_choices)
        run_turn(game)

    def test_discard_to_draw_on_opponents_upkeep(self):
        game = create_game()
        p1, p2 = game.players
        _setup(game)
        filler = Creature(name="Hand Filler", base_power=1, base_toughness=1,
                          mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[filler])
        drawn = Creature(name="Drawn Card", base_power=1, base_toughness=1,
                         mana_cost=ManaCost.parse("{1}"))
        _stock_library(p1, [drawn])
        _stock_library(p2, [Creature(name="P2 Draw", base_power=1,
                                     base_toughness=1)])

        self._run_two_turns(game, p1_choices=[filler])

        assert p1.zones[Zone.GRAVEYARD].contains(filler)
        assert p1.zones[Zone.HAND].contains(drawn)

    def test_loot_may_be_declined(self):
        game = create_game()
        p1, p2 = game.players
        _setup(game)
        filler = Creature(name="Hand Filler", base_power=1, base_toughness=1,
                          mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[filler])
        _stock_library(p2, [Creature(name="P2 Draw", base_power=1,
                                     base_toughness=1)])

        self._run_two_turns(game, p1_choices=[None])

        assert p1.zones[Zone.HAND].contains(filler)
        assert len(p1.zones[Zone.GRAVEYARD]) == 0
