"""Tests for SOS 226 — Silverquill, the Disputant (Casualty 1)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state, cast_spell


class ZapInstant(Instant):
    """Test spell: deal 3 damage to the opponent. No targets (auto opponent)."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game) -> None:
        from engine.game import deal_damage

        opp = [p for p in game.players if p is not self.controller][0]
        deal_damage(game, self, opp, 3)


def _setup(extra_battlefield=None):
    game = create_game()
    p1, p2 = game.players
    silver = SilverquillTheDisputant(owner=p1, controller=p1)
    bf = [silver] + (extra_battlefield or [])
    set_board_state(game, 0, battlefield=bf)
    silver.register_triggers(game)
    return game, p1, p2, silver


class TestProperties:
    def test_static(self):
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert card.base_power == 4 and card.base_toughness == 4
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes


class TestCasualty:
    def test_casualty_taken_copies_spell(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p1, p2, silver = _setup([bear])
        zap = ZapInstant(owner=None)
        set_board_state(game, 0, battlefield=[silver, bear], hand=[zap],
                        mana={ManaType.RED: 1})
        p1._script.append(bear)  # sacrifice the bear for casualty
        cast_spell(game, 0, "Zap")
        # Original + copy each deal 3 → opponent takes 6.
        assert p2.life == 14
        assert game.get_graveyard(p1).contains(bear)
        assert not game.get_battlefield(p1).contains(bear)

    def test_casualty_declined(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p1, p2, silver = _setup([bear])
        zap = ZapInstant(owner=None)
        set_board_state(game, 0, battlefield=[silver, bear], hand=[zap],
                        mana={ManaType.RED: 1})
        p1._script.append(None)  # decline
        cast_spell(game, 0, "Zap")
        # No copy → opponent takes 3 only; bear survives.
        assert p2.life == 17
        assert game.get_battlefield(p1).contains(bear)

    def test_only_power_one_plus_offered(self):
        # A 0/3 Wall is not a legal casualty sacrifice; scripting it declines.
        wall = Creature(name="Wall", base_power=0, base_toughness=3)
        game, p1, p2, silver = _setup([wall])
        zap = ZapInstant(owner=None)
        set_board_state(game, 0, battlefield=[silver, wall], hand=[zap],
                        mana={ManaType.RED: 1})
        p1._script.append(wall)  # wall is power 0 → not in candidates → no-op
        cast_spell(game, 0, "Zap")
        assert p2.life == 17  # no copy
        assert game.get_battlefield(p1).contains(wall)

    def test_silverquill_itself_is_valid_sacrifice(self):
        game, p1, p2, silver = _setup([])  # only Silverquill (power 4)
        zap = ZapInstant(owner=None)
        set_board_state(game, 0, battlefield=[silver], hand=[zap],
                        mana={ManaType.RED: 1})
        p1._script.append(silver)  # sacrifice Silverquill itself
        cast_spell(game, 0, "Zap")
        assert p2.life == 14  # copy still made (when-you-do reflexive)
        assert game.get_graveyard(p1).contains(silver)

    def test_creature_spell_does_not_trigger_casualty(self):
        # Casting a creature (not instant/sorcery) must not prompt casualty.
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p1, p2, silver = _setup([bear])
        ogre = Creature(name="Ogre", mana_cost=ManaCost.parse("{2}"),
                        base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[silver, bear], hand=[ogre],
                        mana={ManaType.COLORLESS: 2})
        # No script entry needed — no casualty prompt should occur.
        cast_spell(game, 0, "Ogre")
        assert game.get_battlefield(p1).contains(bear)  # bear not sacrificed
        assert game.get_battlefield(p1).contains(ogre)
