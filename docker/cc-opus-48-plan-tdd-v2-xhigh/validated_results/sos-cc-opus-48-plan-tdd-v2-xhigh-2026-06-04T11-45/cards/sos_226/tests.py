"""Tests for SOS 226 — Silverquill, the Disputant (casualty granting)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Sorcery
from engine.types import Keyword, ManaCost, ManaType, Supertype
from test_utils import create_game, set_board_state


class _Ping(Sorcery):
    def __init__(self, **kw: Any) -> None:
        kw.setdefault("name", "Ping")
        kw.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kw)

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        opp = game.players[1] if self.controller is game.players[0] else game.players[0]
        deal_damage(game, self, opp, 3)


def _bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


class TestSilverquillProperties:
    def test_name(self) -> None:
        assert SilverquillTheDisputant(owner=None).name == "Silverquill, the Disputant"

    def test_cost(self) -> None:
        assert SilverquillTheDisputant(owner=None).mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_pt(self) -> None:
        c = SilverquillTheDisputant(owner=None)
        assert c.base_power == 4 and c.base_toughness == 4

    def test_keywords(self) -> None:
        c = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING in c.keywords and Keyword.VIGILANCE in c.keywords

    def test_legendary(self) -> None:
        assert Supertype.LEGENDARY in SilverquillTheDisputant(owner=None).supertypes


class TestSilverquillCasualty:
    def test_casualty_copies_instant_sorcery(self) -> None:
        game = create_game()
        p1, p2 = game.players
        sq = SilverquillTheDisputant(owner=p1, controller=p1)
        bear = _bear()
        ping = _Ping()
        set_board_state(game, 0, battlefield=[sq, bear], hand=[ping],
                        mana={ManaType.RED: 1})
        sq.register_triggers(game)

        # Casualty: choose_yes_no(True), then choose the bear to sacrifice.
        p1._script.append(True)
        p1._script.append(bear)

        from test_utils import cast_spell
        cast_spell(game, 0, "Ping")

        # Original + copy each deal 3 → 6 total.
        assert p2.life == 14
        assert game.get_graveyard(p1).contains(bear)

    def test_casualty_declined(self) -> None:
        game = create_game()
        p1, p2 = game.players
        sq = SilverquillTheDisputant(owner=p1, controller=p1)
        bear = _bear()
        ping = _Ping()
        set_board_state(game, 0, battlefield=[sq, bear], hand=[ping],
                        mana={ManaType.RED: 1})
        sq.register_triggers(game)

        p1._script.append(False)

        from test_utils import cast_spell
        cast_spell(game, 0, "Ping")

        assert p2.life == 17
        assert game.get_battlefield(p1).contains(bear)
