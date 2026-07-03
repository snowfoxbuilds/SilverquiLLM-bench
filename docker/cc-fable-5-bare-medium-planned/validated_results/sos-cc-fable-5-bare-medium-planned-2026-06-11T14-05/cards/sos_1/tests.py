"""Tests for The Dawning Archaic (sos_1)."""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Instant, Sorcery
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import (
    TestSetupError,
    create_game,
    declare_attackers,
    set_board_state,
)


class PlainShock(Instant):
    """Targetless helper instant for free-cast tests."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Plain Shock")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        game.players[1].life -= 2


class TestTheDawningArchaic:
    def test_cost_reduced_by_graveyard_instants_and_sorceries(self):
        game = create_game()
        yard = [PlainShock(), Sorcery(name="Filler Sorcery", mana_cost=ManaCost.parse("{1}")),
                PlainShock()]
        set_board_state(game, 0, hand=[TheDawningArchaic(owner=None)],
                        graveyard=yard, mana={ManaType.COLORLESS: 7})
        from test_utils import cast_spell
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.get_battlefield(game.players[0]).get_all()[-1].name == "The Dawning Archaic"

    def test_no_reduction_with_empty_graveyard(self):
        game = create_game()
        set_board_state(game, 0, hand=[TheDawningArchaic(owner=None)],
                        graveyard=[], mana={ManaType.COLORLESS: 7})
        with pytest.raises(TestSetupError):
            from test_utils import cast_spell
            cast_spell(game, 0, "The Dawning Archaic")

    def test_reduction_clamps_at_zero(self):
        game = create_game()
        yard = [PlainShock() for _ in range(12)]
        set_board_state(game, 0, hand=[TheDawningArchaic(owner=None)],
                        graveyard=yard, mana={})
        from test_utils import cast_spell
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.get_battlefield(game.players[0]).get_all()[-1].name == "The Dawning Archaic"

    def test_has_reach(self):
        assert Keyword.REACH in TheDawningArchaic().keywords

    def test_attack_trigger_free_casts_and_exiles_spell(self):
        game = create_game(scripts=(["pass", "pass"], ["pass", "pass"]))
        p0, p1 = game.players
        archaic = TheDawningArchaic()
        shock = PlainShock()
        set_board_state(game, 0, battlefield=[archaic], graveyard=[shock])
        archaic.register_triggers(game)  # set_board_state skips ETB hooks
        archaic.summoning_sick = False
        declare_attackers(game, ["The Dawning Archaic"])
        assert len(game.stack) == 1  # the attack trigger
        priority_loop(game)
        # Spell was cast for free and resolved: 2 damage to opponent.
        assert p1.life == 18
        # Exiled instead of returning to the graveyard.
        assert p0.zones[Zone.EXILE].contains(shock)
        assert not p0.zones[Zone.GRAVEYARD].contains(shock)

    def test_attack_trigger_empty_graveyard_no_effect(self):
        game = create_game(scripts=(["pass", "pass"], ["pass", "pass"]))
        p0, p1 = game.players
        archaic = TheDawningArchaic()
        set_board_state(game, 0, battlefield=[archaic], graveyard=[])
        archaic.register_triggers(game)
        archaic.summoning_sick = False
        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)
        assert p1.life == 20
        assert len(p0.zones[Zone.EXILE]) == 0
