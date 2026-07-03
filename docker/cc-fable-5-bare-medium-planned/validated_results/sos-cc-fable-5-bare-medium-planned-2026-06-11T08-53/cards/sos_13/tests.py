"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.abilities import AbilityError, ActivatedAbilityInstance, activate_ability
from engine.card import Creature
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType
from test_utils import cast_spell, create_game, set_board_state


def _bears(n: int) -> list[Creature]:
    return [
        Creature(name=f"Bear {n_}", base_power=2, base_toughness=2)
        for n_ in range(n)
    ]


def _ability_instance(card, player):
    aa = card.get_activated_abilities()[0]
    return ActivatedAbilityInstance(
        source=card, controller=player, cost=aa.cost, effect=aa.effect
    )


class TestEmeritusETB:
    def test_full_name_and_bare_construction(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == "Emeritus of Truce // Swords to Plowshares"
        assert card.base_power == 3 and card.base_toughness == 3
        assert {"Cat", "Cleric"} <= card.subtypes

    def test_etb_token_and_becomes_prepared(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=_bears(2))
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})

        # Token to the opponent: they end with 3 creatures vs my 1.
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares",
                   targets=[p2])

        tokens = [
            c for c in game.get_battlefield(p2).get_all()
            if c.name == "Inkling"
        ]
        assert len(tokens) == 1
        assert tokens[0].is_token
        assert Keyword.FLYING in tokens[0].keywords
        assert tokens[0].power == 1 and tokens[0].toughness == 1
        assert emeritus.is_prepared

    def test_not_prepared_when_opponent_has_fewer(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})

        # Token to me: I end with 2 creatures vs opponent's 0.
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares",
                   targets=[p1])
        assert not emeritus.is_prepared
        assert any(
            c.name == "Inkling" for c in game.get_battlefield(p1).get_all()
        )


class TestPreparedCast:
    def _prepared_setup(self, game):
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=_bears(2))
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.WHITE: 2, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares",
                   targets=[p2])
        assert emeritus.is_prepared
        return emeritus

    def test_cast_copy_exiles_creature_and_unprepares(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        emeritus = self._prepared_setup(game)
        bear = game.get_battlefield(p2).get_all()[0]
        p2_life = p2.life

        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        # script order: pass (ability on stack), target, pass (spell on stack)
        p1._script.extend(["pass", bear, "pass"])
        p2._script.extend(["pass", "pass"])
        activate_ability(game, p1, _ability_instance(emeritus, p1))
        priority_loop(game)

        assert game.get_exile(p2).contains(bear)
        assert p2.life == p2_life + 2  # gained life equal to its power
        assert not emeritus.is_prepared
        assert p1.mana_pool.total() == 0  # paid {W}

    def test_cannot_activate_when_not_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        set_board_state(game, 0, battlefield=[emeritus],
                        mana={ManaType.WHITE: 1})
        try:
            activate_ability(game, p1, _ability_instance(emeritus, p1))
            raised = False
        except AbilityError:
            raised = True
        assert raised

    def test_cannot_activate_twice(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        emeritus = self._prepared_setup(game)
        bear = game.get_battlefield(p2).get_all()[0]
        set_board_state(game, 0, mana={ManaType.WHITE: 2})
        p1._script.extend(["pass", bear, "pass"])
        p2._script.extend(["pass", "pass"])
        activate_ability(game, p1, _ability_instance(emeritus, p1))
        priority_loop(game)
        assert not emeritus.is_prepared

        # Unprepared now — a second activation is illegal.
        try:
            activate_ability(game, p1, _ability_instance(emeritus, p1))
            raised = False
        except AbilityError:
            raised = True
        assert raised
