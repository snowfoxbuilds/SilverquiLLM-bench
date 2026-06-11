"""Tests for engine.card_queries — the card-facing Player Query helpers that
card implementations use instead of the deleted V1 ``player.choose_*`` methods.
"""

from __future__ import annotations

from engine.card import Creature
from engine.card_queries import choose_color, choose_mode, choose_object, query_yes_no
from engine.decisions import Decision, GameRef
from engine.game_state import GameState
from engine.intent_player import DeterministicPlayer, Intent
from engine.types import ManaCost, Zone


def _game():
    p0, p1 = DeterministicPlayer("P0"), DeterministicPlayer("P1")
    return GameState([p0, p1])


def _creature(name, **kw):
    return Creature(name=name, mana_cost=ManaCost(generic=1),
                    base_power=1, base_toughness=1, **kw)


def _put(game, player, zone, card):
    card.owner = player
    card.controller = player
    player.zones[zone].add(card)
    return card


class TestChooseObject:
    def test_returns_the_preferred_object(self):
        game = _game()
        p0 = game.players[0]
        bear = _put(game, p0, Zone.BATTLEFIELD, _creature("Bear"))
        ox = _put(game, p0, Zone.BATTLEFIELD, _creature("Ox"))
        bear.instance_id = game.refs.instance_id(bear, "battlefield")
        p0.set_baseline(Intent(pattern=GameRef(),
                               preferences=(Decision.obj(instance=bear.instance_id),)))
        chosen = choose_object(game, p0, [bear, ox], "pick one", source_card=None)
        assert chosen is bear

    def test_optional_decline_returns_none(self):
        game = _game()
        p0 = game.players[0]
        a = _put(game, p0, Zone.BATTLEFIELD, _creature("A"))
        p0.set_baseline(Intent(pattern=GameRef(), preferences=()))  # no preference
        chosen = choose_object(game, p0, [a], "optional", optional=True)
        assert chosen is None

    def test_multi_select_returns_list_of_preferred_objects(self):
        game = _game()
        p0 = game.players[0]
        bear = _put(game, p0, Zone.BATTLEFIELD, _creature("Bear"))
        ox = _put(game, p0, Zone.BATTLEFIELD, _creature("Ox"))
        elk = _put(game, p0, Zone.BATTLEFIELD, _creature("Elk"))
        bear_iid = game.refs.instance_id(bear, "battlefield")
        elk_iid = game.refs.instance_id(elk, "battlefield")
        p0.set_baseline(Intent(
            pattern=GameRef(),
            preferences=(
                Decision.obj(instance=bear_iid),
                Decision.obj(instance=elk_iid),
            ),
        ))
        chosen = choose_object(
            game, p0, [bear, ox, elk], "pick any number",
            min=0, max=3, optional=True,
        )
        assert isinstance(chosen, list)
        assert chosen == [bear, elk]

    def test_no_candidates_returns_empty_or_none(self):
        game = _game()
        p0 = game.players[0]
        p0.set_baseline(Intent(pattern=GameRef(), preferences=()))
        # max == 1 → None
        assert choose_object(game, p0, [], "nothing") is None
        # max > 1 → []
        assert choose_object(game, p0, [], "nothing", min=0, max=2,
                             optional=True) == []


class TestChooseYesNo:
    def test_yes_and_no(self):
        game = _game()
        p0 = game.players[0]
        p0.set_baseline(Intent(pattern=GameRef(), preferences=(Decision.yes(),)))
        assert query_yes_no(game, p0, "?") is True
        p0.set_baseline(Intent(pattern=GameRef(), preferences=(Decision.no(),)))
        assert query_yes_no(game, p0, "?") is False


class TestChooseMode:
    def test_returns_chosen_mode_name(self):
        game = _game()
        p0 = game.players[0]
        p0.set_baseline(Intent(pattern=GameRef(),
                               preferences=(Decision.mode("token"),)))
        chosen = choose_mode(game, p0, ["flicker", "token"], "choose mode")
        assert chosen == "token"


class TestChooseColor:
    def test_returns_chosen_color_letter(self):
        game = _game()
        p0 = game.players[0]
        p0.set_baseline(Intent(pattern=GameRef(),
                               preferences=(Decision.color("R"),)))
        chosen = choose_color(game, p0, "pick a color")
        assert chosen == "R"
