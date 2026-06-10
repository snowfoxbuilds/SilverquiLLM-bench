"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from engine.state_based_actions import resolve_state_based_actions
from test_utils import create_game, set_board_state, cast_spell


def _resolve(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class TestProperties:
    def test_front_face(self):
        c = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert c.name == "Emeritus of Truce // Swords to Plowshares"
        assert isinstance(c, Creature)
        assert (c.base_power, c.base_toughness) == (3, 3)
        assert {"Cat", "Cleric"} <= c.subtypes
        assert c.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_swords_face(self):
        s = SwordsToPlowshares(owner=None)
        assert isinstance(s, Instant)
        assert s.name == "Swords to Plowshares"
        assert s.mana_cost == ManaCost.parse("{W}")


class TestETB:
    def test_inkling_to_target_player_not_prepared(self):
        game = create_game()
        p0, p1 = game.players
        set_board_state(game, 0, hand=[EmeritusOfTruceSwordsToPlowshares(owner=None)],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        p0._script.append(p0)  # target player = me
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
        inkling = next((c for c in game.get_battlefield(p0).get_all()
                        if getattr(c, "name", "") == "Inkling"), None)
        assert inkling is not None
        assert Keyword.FLYING in inkling.keywords
        emeritus = next(c for c in game.get_battlefield(p0).get_all()
                        if getattr(c, "name", "").startswith("Emeritus"))
        assert emeritus.prepared is False  # I control 2, opponent 0

    def test_prepared_when_opponent_has_more(self):
        game = create_game()
        p0, p1 = game.players
        set_board_state(game, 1, battlefield=[
            Creature(name="B1", base_power=2, base_toughness=2),
            Creature(name="B2", base_power=2, base_toughness=2),
        ])
        set_board_state(game, 0, hand=[EmeritusOfTruceSwordsToPlowshares(owner=None)],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        p0._script.append(p1)  # Inkling to opponent
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares")
        emeritus = next(c for c in game.get_battlefield(p0).get_all()
                        if getattr(c, "name", "").startswith("Emeritus"))
        # opponent now controls 3, I control 1 (Emeritus) → prepared.
        assert emeritus.prepared is True


class TestPreparedSpell:
    def test_cast_prepared_copy_exiles_and_gains_life(self):
        game = create_game()
        p0, p1 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p0, controller=p0)
        emeritus._prepared = True
        bear = Creature(name="Big Bear", base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[bear], life=20)
        ok = emeritus.cast_prepared_copy(game, target=bear)
        _resolve(game)
        assert ok is True
        assert p1.zones[Zone.EXILE].contains(bear)  # exiled
        assert p1.life == 24  # controller gains life = power (4)
        assert emeritus.prepared is False  # unprepared

    def test_swords_no_target_noop(self):
        game = create_game()
        s = SwordsToPlowshares(owner=game.players[0], controller=game.players[0])
        assert s.get_targets(game) == []
        s.on_resolve(game)  # must not raise
