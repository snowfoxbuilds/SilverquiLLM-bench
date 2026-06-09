"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, Supertype
from test_utils import create_game, set_board_state, cast_spell


class MarkerSpell(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Marker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 1


def _setup(scripts_p0):
    game = create_game(scripts=(scripts_p0, []))
    p0 = game.players[0]
    sq = SilverquillTheDisputant(owner=None)
    bear = Creature(name="Bear", base_power=2, base_toughness=2)
    set_board_state(game, 0, battlefield=[sq, bear],
                    hand=[MarkerSpell(owner=None)], mana={ManaType.COLORLESS: 1})
    sq.register_triggers(game)
    return game, p0, sq, bear


class TestProperties:
    def test_basics(self):
        c = SilverquillTheDisputant(owner=None)
        assert c.name == "Silverquill, the Disputant"
        assert c.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert c.base_power == 4 and c.base_toughness == 4
        assert Keyword.FLYING in c.keywords and Keyword.VIGILANCE in c.keywords
        assert Supertype.LEGENDARY in c.supertypes


class TestCasualty:
    def test_casualty_taken_copies_spell(self):
        game, p0, sq, bear = _setup([True, None])  # yes, then choose victim below
        # Script: choose_yes_no -> True, choose_card -> bear
        p0._script.clear()
        p0._script.extend([True, bear])
        cast_spell(game, 0, "Marker")
        # Original + copy both resolved → +2 life; bear sacrificed.
        assert p0.life == 22
        assert game.get_graveyard(p0).contains(bear)

    def test_casualty_declined(self):
        game = create_game(scripts=([False], []))
        p0 = game.players[0]
        sq = SilverquillTheDisputant(owner=None)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[sq, bear],
                        hand=[MarkerSpell(owner=None)], mana={ManaType.COLORLESS: 1})
        sq.register_triggers(game)
        cast_spell(game, 0, "Marker")
        # Declined → only original resolved (+1), bear survives.
        assert p0.life == 21
        assert not game.get_graveyard(p0).contains(bear)

    def test_creature_spell_not_affected(self):
        game = create_game(scripts=([], []))
        p0 = game.players[0]
        sq = SilverquillTheDisputant(owner=None)
        set_board_state(game, 0, battlefield=[sq],
                        hand=[Creature(name="Ally", base_power=1, base_toughness=1,
                                       mana_cost=ManaCost.parse("{1}"))],
                        mana={ManaType.COLORLESS: 1})
        sq.register_triggers(game)
        # Casting a creature must not trigger casualty (no script consumed).
        cast_spell(game, 0, "Ally")
        assert "Ally" in [c.name for c in game.get_battlefield(p0).get_all()]
