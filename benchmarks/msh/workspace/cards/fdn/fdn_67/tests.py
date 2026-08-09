"""Reference test for FDN 67 — Revenge of the Rats.

Regression guard for the ``is_tapped`` attribute fix: the Rat tokens this
sorcery makes must enter **tapped**, and "tapped" is the engine field
``is_tapped`` (not a stray ``.tapped``). Verifies token count tracks creature
cards in the graveyard and each token is tapped.
"""

from __future__ import annotations

from cards.fdn.fdn_67.card_impl import RevengeOfTheRats
from engine.card import Creature
from engine.types import CardType, ManaCost, ManaType
from test_utils import cast_spell, create_game, set_board_state


def _creature(name):
    return Creature(name=name, base_power=1, base_toughness=1)


def _rats(game, player):
    bf = game.get_battlefield(player)
    return [o for o in bf.get_all() if getattr(o, "name", None) == "Rat"]


class TestRevengeOfTheRatsProperties:
    def test_static_data(self):
        c = RevengeOfTheRats(owner=None)
        assert c.name == "Revenge of the Rats"
        assert c.mana_cost == ManaCost.parse("{2}{B}{B}")
        assert CardType.SORCERY in c.card_types


class TestRevengeOfTheRatsResolve:
    def test_creates_one_tapped_rat_per_creature_in_graveyard(self):
        game = create_game()
        p1 = game.players[0]
        revenge = RevengeOfTheRats(owner=p1, controller=p1)
        gy = [_creature("A"), _creature("B"), _creature("C")]
        set_board_state(game, 0, hand=[revenge], graveyard=gy,
                        mana={ManaType.BLACK: 4})
        cast_spell(game, 0, "Revenge of the Rats")
        rats = _rats(game, p1)
        assert len(rats) == 3
        for r in rats:
            assert (r.base_power, r.base_toughness) == (1, 1)
            assert r.is_tapped is True  # tokens enter tapped

    def test_no_creatures_in_graveyard_makes_no_rats(self):
        game = create_game()
        p1 = game.players[0]
        revenge = RevengeOfTheRats(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[revenge], graveyard=[],
                        mana={ManaType.BLACK: 4})
        cast_spell(game, 0, "Revenge of the Rats")
        assert _rats(game, p1) == []
