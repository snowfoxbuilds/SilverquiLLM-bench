"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import cast_spell, create_game, set_board_state


class _GainThree(Instant):
    """Controller gains 3 life. No targets."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Inspire")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 3


def _setup(scripts_p0):
    game = create_game(scripts=(scripts_p0, []))
    p0 = game.players[0]
    sq = SilverquillTheDisputant(owner=p0, controller=p0)
    return game, p0, sq


class TestProperties:
    def test_keywords_stats(self):
        c = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING in c.keywords and Keyword.VIGILANCE in c.keywords
        assert c.base_power == 4 and c.base_toughness == 4
        assert Supertype.LEGENDARY in c.supertypes
        assert c.mana_cost == ManaCost.parse("{2}{W}{B}")


class TestCasualty:
    def test_pay_casualty_copies_spell(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p0, sq = _setup([True, bear])
        spell = _GainThree(owner=None)
        set_board_state(game, 0, battlefield=[sq, bear], life=20,
                        hand=[spell], mana={ManaType.COLORLESS: 1})
        sq.register_triggers(game)
        cast_spell(game, 0, "Inspire")
        # Original + copy both resolve → +6 life; bear sacrificed.
        assert p0.life == 26
        assert game.get_graveyard(p0).contains(bear)
        assert not game.get_battlefield(p0).contains(bear)

    def test_decline_casualty(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p0, sq = _setup([False])
        spell = _GainThree(owner=None)
        set_board_state(game, 0, battlefield=[sq, bear], life=20,
                        hand=[spell], mana={ManaType.COLORLESS: 1})
        sq.register_triggers(game)
        cast_spell(game, 0, "Inspire")
        # Declined → only original resolves; bear stays.
        assert p0.life == 23
        assert game.get_battlefield(p0).contains(bear)

    def test_creature_spell_no_casualty(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p0, sq = _setup([])
        dude = Creature(name="Dude", base_power=1, base_toughness=1,
                        mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, battlefield=[sq, bear], life=20,
                        hand=[dude], mana={ManaType.COLORLESS: 1})
        sq.register_triggers(game)
        cast_spell(game, 0, "Dude")
        # Casualty applies only to instants/sorceries → bear not sacrificed.
        assert game.get_battlefield(p0).contains(bear)
