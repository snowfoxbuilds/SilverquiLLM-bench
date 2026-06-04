"""Tests for SOS 201 — Lorehold, the Historian."""

from __future__ import annotations

from cards.sos.sos_201.card_impl import LoreholdTheHistorian
from engine.card import Creature, Sorcery
from engine.events import BeginningOfUpkeepTriggeredEvent
from engine.game import draw_card
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state, _resolve_top_of_stack


class _GainLife(Sorcery):
    """A no-target sorcery: gain 3 life on resolve. Printed cost is {4}{R}."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Recollect")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 3


def _creature(name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2)


def _set_library(game, player, cards):
    lib = player.zones[Zone.LIBRARY]
    for c in lib.get_all():
        lib.remove(c)
    for c in cards:  # given bottom-to-top
        c.owner = player
        c.controller = player
        lib.add(c)


def _lorehold(game, player_index=0):
    lh = LoreholdTheHistorian(owner=None)
    set_board_state(game, player_index, battlefield=[lh])
    return lh


class TestProperties:
    def test_is_creature(self):
        assert isinstance(LoreholdTheHistorian(owner=None), Creature)

    def test_name(self):
        assert LoreholdTheHistorian(owner=None).name == "Lorehold, the Historian"

    def test_mana_cost(self):
        assert LoreholdTheHistorian(owner=None).mana_cost == ManaCost.parse("{3}{R}{W}")

    def test_power_toughness(self):
        c = LoreholdTheHistorian(owner=None)
        assert c.base_power == 5 and c.base_toughness == 5

    def test_legendary(self):
        assert Supertype.LEGENDARY in LoreholdTheHistorian(owner=None).supertypes

    def test_keywords(self):
        kw = LoreholdTheHistorian(owner=None).keywords
        assert Keyword.FLYING in kw and Keyword.HASTE in kw


class TestMiracle:
    def test_first_instant_draw_cast_for_two(self):
        game = create_game()
        p0 = game.players[0]
        lh = LoreholdTheHistorian(owner=None)
        set_board_state(game, 0, battlefield=[lh],
                        mana={ManaType.COLORLESS: 2}, life=20)
        lh.register_triggers(game)
        spell = _GainLife(owner=None)
        _set_library(game, p0, [spell])
        p0.cards_drawn_this_turn = 0
        p0._script.append(True)  # accept the miracle cast
        draw_card(game, p0)
        _resolve_top_of_stack(game)
        assert spell in p0.zones[Zone.GRAVEYARD].get_all()
        assert spell not in p0.zones[Zone.HAND].get_all()
        assert p0.life == 23
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0

    def test_decline_miracle_keeps_card(self):
        game = create_game()
        p0 = game.players[0]
        lh = LoreholdTheHistorian(owner=None)
        set_board_state(game, 0, battlefield=[lh],
                        mana={ManaType.COLORLESS: 2}, life=20)
        lh.register_triggers(game)
        spell = _GainLife(owner=None)
        _set_library(game, p0, [spell])
        p0.cards_drawn_this_turn = 0
        p0._script.append(False)  # decline
        draw_card(game, p0)
        _resolve_top_of_stack(game)
        assert spell in p0.zones[Zone.HAND].get_all()
        assert p0.life == 20
        assert p0.mana_pool.get(ManaType.COLORLESS) == 2

    def test_non_first_draw_no_miracle(self):
        game = create_game()
        p0 = game.players[0]
        lh = LoreholdTheHistorian(owner=None)
        set_board_state(game, 0, battlefield=[lh],
                        mana={ManaType.COLORLESS: 2})
        lh.register_triggers(game)
        spell = _GainLife(owner=None)
        _set_library(game, p0, [spell])
        p0.cards_drawn_this_turn = 1  # already drew once -> this is the 2nd
        draw_card(game, p0)
        _resolve_top_of_stack(game)
        assert spell in p0.zones[Zone.HAND].get_all()

    def test_noncreature_required(self):
        game = create_game()
        p0 = game.players[0]
        lh = LoreholdTheHistorian(owner=None)
        set_board_state(game, 0, battlefield=[lh])
        lh.register_triggers(game)
        bear = _creature("Drawn Bear")
        _set_library(game, p0, [bear])
        p0.cards_drawn_this_turn = 0
        draw_card(game, p0)
        _resolve_top_of_stack(game)
        assert bear in p0.zones[Zone.HAND].get_all()

    def test_only_controller_draws_trigger(self):
        game = create_game()
        p0, p1 = game.players
        lh = LoreholdTheHistorian(owner=None)
        set_board_state(game, 0, battlefield=[lh])
        lh.register_triggers(game)
        spell = _GainLife(owner=None)
        _set_library(game, p1, [spell])
        p1.cards_drawn_this_turn = 0
        draw_card(game, p1)
        _resolve_top_of_stack(game)
        assert spell in p1.zones[Zone.HAND].get_all()


class TestLoot:
    def test_loot_on_opponent_upkeep(self):
        game = create_game()
        p0, p1 = game.players
        lh = LoreholdTheHistorian(owner=None)
        junk = _creature("Junk")
        set_board_state(game, 0, battlefield=[lh], hand=[junk])
        lh.register_triggers(game)
        drawn = _creature("Fresh")
        _set_library(game, p0, [drawn])
        game.active_player_index = 1  # opponent's upkeep
        p0._script.append(True)   # discard?
        p0._script.append(junk)   # which card to discard
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_top_of_stack(game)
        assert junk in p0.zones[Zone.GRAVEYARD].get_all()
        assert drawn in p0.zones[Zone.HAND].get_all()

    def test_loot_declined_no_draw(self):
        game = create_game()
        p0, p1 = game.players
        lh = LoreholdTheHistorian(owner=None)
        junk = _creature("Junk")
        set_board_state(game, 0, battlefield=[lh], hand=[junk])
        lh.register_triggers(game)
        drawn = _creature("Fresh")
        _set_library(game, p0, [drawn])
        game.active_player_index = 1
        p0._script.append(False)  # decline
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_top_of_stack(game)
        assert junk in p0.zones[Zone.HAND].get_all()
        assert drawn in p0.zones[Zone.LIBRARY].get_all()

    def test_no_loot_on_own_upkeep(self):
        game = create_game()
        p0, p1 = game.players
        lh = LoreholdTheHistorian(owner=None)
        junk = _creature("Junk")
        set_board_state(game, 0, battlefield=[lh], hand=[junk])
        lh.register_triggers(game)
        drawn = _creature("Fresh")
        _set_library(game, p0, [drawn])
        game.active_player_index = 0  # controller's own upkeep
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        _resolve_top_of_stack(game)
        assert junk in p0.zones[Zone.HAND].get_all()
        assert drawn in p0.zones[Zone.LIBRARY].get_all()
