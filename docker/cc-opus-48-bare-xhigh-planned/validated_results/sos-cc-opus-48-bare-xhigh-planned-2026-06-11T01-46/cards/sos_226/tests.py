"""Tests for Silverquill, the Disputant (sos_226) — granted Casualty 1."""

from __future__ import annotations

import pytest

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.types import Keyword, ManaCost, ManaType, Supertype
from test_utils import create_game, set_board_state, cast_spell


class DamageInstant(Instant):
    """{R}: deal 3 damage to the non-active player."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Damage Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        from engine.game import deal_damage
        deal_damage(game, self, game.non_active_player, 3)


def _setup(scripts_p0):
    game = create_game(scripts=(scripts_p0, []))
    p0, p1 = game.players
    silver = SilverquillTheDisputant(owner=None)
    return game, p0, p1, silver


class TestProperties:
    def test_static(self):
        c = SilverquillTheDisputant(owner=None)
        assert c.name == "Silverquill, the Disputant"
        assert c.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert Keyword.FLYING in c.keywords and Keyword.VIGILANCE in c.keywords
        assert c.base_power == 4 and c.base_toughness == 4
        assert Supertype.LEGENDARY in c.supertypes


class TestCasualty:
    def test_sacrifice_copies_spell(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p0, p1, silver = _setup([bear])  # choose to sac the bear
        set_board_state(game, 0, battlefield=[silver, bear])
        silver.register_triggers(game)
        set_board_state(game, 0, hand=[DamageInstant(owner=None)], mana={ManaType.RED: 1})
        cast_spell(game, 0, "Damage Instant")
        # Original + copy each deal 3 → 6 total.
        assert p1.life == 14
        assert game.get_graveyard(p0).contains(bear)

    def test_decline_casualty(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p0, p1, silver = _setup([None])  # decline
        set_board_state(game, 0, battlefield=[silver, bear])
        silver.register_triggers(game)
        set_board_state(game, 0, hand=[DamageInstant(owner=None)], mana={ManaType.RED: 1})
        cast_spell(game, 0, "Damage Instant")
        assert p1.life == 17           # only the original resolved
        assert not game.get_graveyard(p0).contains(bear)

    def test_casualty_applies_to_sorcery(self):
        class DamageSorcery(Sorcery):
            def __init__(self, **kwargs):
                kwargs.setdefault("name", "Damage Sorcery")
                kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
                super().__init__(**kwargs)

            def on_resolve(self, game):
                from engine.game import deal_damage
                deal_damage(game, self, game.non_active_player, 3)

        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p0, p1, silver = _setup([bear])
        set_board_state(game, 0, battlefield=[silver, bear])
        silver.register_triggers(game)
        set_board_state(game, 0, hand=[DamageSorcery(owner=None)], mana={ManaType.RED: 1})
        cast_spell(game, 0, "Damage Sorcery")
        assert p1.life == 14
        assert game.get_graveyard(p0).contains(bear)

    def test_no_casualty_for_creature_spell(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game, p0, p1, silver = _setup([])
        set_board_state(game, 0, battlefield=[silver, bear])
        silver.register_triggers(game)
        dork = Creature(name="Dork", base_power=1, base_toughness=1,
                        mana_cost=ManaCost.parse("{G}"))
        set_board_state(game, 0, hand=[dork], mana={ManaType.GREEN: 1})
        cast_spell(game, 0, "Dork")
        # Bear not sacrificed (no casualty on a creature spell).
        assert not game.get_graveyard(p0).contains(bear)
