"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state, cast_spell


class _LifeSpell(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Life Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 3


class TestProperties:
    def test_static(self):
        c = SilverquillTheDisputant(owner=None)
        assert c.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert Keyword.FLYING in c.keywords
        assert Keyword.VIGILANCE in c.keywords
        assert Supertype.LEGENDARY in c.supertypes
        assert (c.base_power, c.base_toughness) == (4, 4)


class TestCasualty:
    def test_pay_casualty_copies_spell(self):
        game = create_game()
        p0 = game.players[0]
        sq = SilverquillTheDisputant(owner=p0, controller=p0)
        fodder = Creature(name="Fodder", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[sq, fodder],
                        hand=[_LifeSpell()], mana={ManaType.RED: 1}, life=20)
        sq.register_triggers(game)
        # Pay casualty (yes), sacrifice the Fodder.
        p0._script.extend([True, fodder])
        cast_spell(game, 0, "Life Spell")
        # Original + 1 copy = +6 life; Fodder sacrificed.
        assert p0.life == 26
        assert p0.zones[Zone.GRAVEYARD].contains(fodder)

    def test_decline_casualty_no_copy(self):
        game = create_game()
        p0 = game.players[0]
        sq = SilverquillTheDisputant(owner=p0, controller=p0)
        fodder = Creature(name="Fodder", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[sq, fodder],
                        hand=[_LifeSpell()], mana={ManaType.RED: 1}, life=20)
        sq.register_triggers(game)
        p0._script.extend([False])  # decline casualty
        cast_spell(game, 0, "Life Spell")
        assert p0.life == 23  # original only
        assert not p0.zones[Zone.GRAVEYARD].contains(fodder)
        assert game.get_battlefield(p0).contains(fodder)

    def test_creature_spell_no_casualty(self):
        game = create_game()
        p0 = game.players[0]
        sq = SilverquillTheDisputant(owner=p0, controller=p0)
        bear = Creature(name="Plain Bear", mana_cost=ManaCost.parse("{1}"),
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[sq],
                        hand=[bear], mana={ManaType.COLORLESS: 1}, life=20)
        sq.register_triggers(game)
        # No casualty offered for a creature spell — no script needed.
        cast_spell(game, 0, "Plain Bear")
        # Bear resolved to battlefield; no extra copies, no life change.
        assert game.get_battlefield(p0).contains(bear)
        assert p0.life == 20
