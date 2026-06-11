"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Instant, Sorcery
from engine.casting import resolve_top
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class _LifeZap(Instant):
    """Test instant ({4}): you gain 2 life."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Life Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 2


def _fill_library(player, cards):
    library = player.zones[Zone.LIBRARY]
    for c in cards:
        c.owner = player
        c.controller = player
        library.add(c)


def _resolve_all(game):
    while not game.stack.is_empty():
        resolve_top(game)


def _setup_lorehold(game, hand=None, mana=None):
    dragon = LoreholdTheHistorian(owner=None)
    set_board_state(game, 0, battlefield=[dragon], hand=hand or [],
                    mana=mana or {})
    dragon.register_triggers(game)
    return dragon


class TestLoreholdStatic:
    def test_card_data(self):
        card = LoreholdTheHistorian(owner=None)
        assert card.name == "Lorehold, the Historian"
        assert card.mana_cost == ManaCost.parse("{3}{R}{W}")
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords
        assert card.base_power == 5 and card.base_toughness == 5


class TestLoreholdMiracle:
    def test_first_drawn_instant_cast_for_two(self):
        game = create_game()
        p1 = game.players[0]
        _setup_lorehold(game, mana={ManaType.COLORLESS: 2})
        zap = _LifeZap()
        _fill_library(p1, [zap])

        p1._script.append(True)  # cast for miracle cost
        draw_card(game, p1)
        _resolve_all(game)

        assert p1.life == 22, "cast for {2} despite the {4} printed cost"
        assert p1.zones[Zone.GRAVEYARD].contains(zap)
        assert p1.mana_pool.total() == 0, "the miracle {2} was deducted"

    def test_miracle_decline_keeps_card_in_hand(self):
        game = create_game()
        p1 = game.players[0]
        _setup_lorehold(game, mana={ManaType.COLORLESS: 2})
        zap = _LifeZap()
        _fill_library(p1, [zap])

        p1._script.append(False)
        draw_card(game, p1)
        _resolve_all(game)

        assert p1.zones[Zone.HAND].contains(zap)
        assert p1.mana_pool.total() == 2, "nothing was paid"
        assert p1.life == 20

    def test_second_draw_this_turn_has_no_miracle(self):
        game = create_game()
        p1 = game.players[0]
        _setup_lorehold(game, mana={ManaType.COLORLESS: 2})
        filler = Creature(name="Filler", base_power=1, base_toughness=1)
        zap = _LifeZap()
        _fill_library(p1, [zap, filler])  # filler on top, zap below

        draw_card(game, p1)  # first draw: a creature — no miracle
        _resolve_all(game)
        draw_card(game, p1)  # second draw: the instant — too late
        _resolve_all(game)

        assert p1.zones[Zone.HAND].contains(zap), "no miracle prompt"
        assert p1.life == 20

    def test_miracle_resets_next_turn(self):
        from test_utils import advance_to_phase
        from engine.types import Phase, Step

        game = create_game()
        p1 = game.players[0]
        _setup_lorehold(game, mana={ManaType.COLORLESS: 2})
        filler = Creature(name="Filler", base_power=1, base_toughness=1)
        zap = _LifeZap()
        _fill_library(p1, [zap, filler])

        draw_card(game, p1)  # turn 1's first draw (creature)
        _resolve_all(game)

        # Next turn: the zap is the first card drawn this turn.
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        game.advance_phase()  # wraps to turn 2
        set_board_state(game, 0, mana={ManaType.COLORLESS: 2})
        p1._script.append(True)
        draw_card(game, p1)
        _resolve_all(game)

        assert p1.life == 22
        assert p1.zones[Zone.GRAVEYARD].contains(zap)


class TestLoreholdLoot:
    def test_loot_on_opponents_upkeep(self):
        game = create_game()
        p1 = game.players[0]
        junk = Creature(name="Junk", base_power=1, base_toughness=1)
        dragon = _setup_lorehold(game, hand=[junk])
        fresh = Creature(name="Fresh", base_power=1, base_toughness=1)
        _fill_library(p1, [fresh])

        game.active_player_index = 1  # opponent's turn
        p1._script.append(junk)  # discard choice
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_all(game)

        assert p1.zones[Zone.GRAVEYARD].contains(junk)
        assert p1.zones[Zone.HAND].contains(fresh), "drew after discarding"

    def test_loot_declinable(self):
        game = create_game()
        p1 = game.players[0]
        junk = Creature(name="Junk", base_power=1, base_toughness=1)
        _setup_lorehold(game, hand=[junk])
        _fill_library(p1, [Creature(name="Fresh", base_power=1, base_toughness=1)])

        game.active_player_index = 1
        p1._script.append(None)
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_all(game)

        assert p1.zones[Zone.HAND].contains(junk)
        assert len(p1.zones[Zone.LIBRARY]) == 1, "no draw"

    def test_no_trigger_on_own_upkeep(self):
        game = create_game()
        p1 = game.players[0]
        junk = Creature(name="Junk", base_power=1, base_toughness=1)
        _setup_lorehold(game, hand=[junk])

        game.active_player_index = 0  # own upkeep
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        assert game.stack.is_empty(), "no trigger on your own upkeep"
