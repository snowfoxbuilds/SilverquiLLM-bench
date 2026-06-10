"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    SwordsToPlowshares,
)
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell

_NAME = "Emeritus of Truce // Swords to Plowshares"


def _resolve_stack(game) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _bear(name: str, power: int = 2) -> Creature:
    return Creature(name=name, base_power=power, base_toughness=2)


def _inklings(game, pidx: int):
    return [
        c
        for c in game.players[pidx].zones[Zone.BATTLEFIELD].get_all()
        if "Inkling" in getattr(c, "subtypes", set())
    ]


class TestProperties:
    def test_emeritus_data(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares()
        assert card.name == _NAME
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert card.base_power == 3 and card.base_toughness == 3
        assert {"Cat", "Cleric"} <= card.subtypes

    def test_swords_data(self) -> None:
        s = SwordsToPlowshares()
        assert isinstance(s, Instant)
        assert s.name == "Swords to Plowshares"
        assert s.mana_cost == ManaCost.parse("{W}")


class TestEnterEffect:
    def test_token_to_opponent_triggers_prepared(self) -> None:
        game = create_game()
        p0, p1 = game.players
        set_board_state(game, 1, battlefield=[_bear("B1"), _bear("B2")])
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        p0._script.append(p1)  # token to the opponent
        cast_spell(game, 0, _NAME)
        # Token entered under p1; p1 now has 3 creatures vs your 1 (Emeritus).
        assert len(_inklings(game, 1)) == 1
        inkling = _inklings(game, 1)[0]
        assert Keyword.FLYING in inkling.keywords
        assert emeritus._prepared is True

    def test_token_to_self_avoids_prepared(self) -> None:
        game = create_game()
        p0, p1 = game.players
        set_board_state(game, 1, battlefield=[_bear("B1"), _bear("B2")])
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p0, controller=p0)
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        p0._script.append(p0)  # token to yourself
        cast_spell(game, 0, _NAME)
        # You: Inkling + Emeritus = 2; opponent: 2 → not more → not prepared.
        assert len(_inklings(game, 0)) == 1
        assert emeritus._prepared is False


class TestPreparedCast:
    def test_prepared_cast_exiles_and_gains_life(self) -> None:
        game = create_game()
        p0, p1 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p0, controller=p0)
        bear = _bear("Victim", power=2)
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[bear])
        emeritus._prepared = True

        # Swords' target (the bear) is scripted into the free cast.
        p0._script.append(bear)
        ability = emeritus.get_activated_abilities()[0]
        inst = ActivatedAbilityInstance(
            source=emeritus, controller=p0, cost=ability.cost,
            effect=ability.effect, is_mana_ability=False,
        )
        activate_ability(game, p0, inst)
        _resolve_stack(game)

        assert game.get_exile(p1).contains(bear)  # exiled
        assert not game.get_battlefield(p1).contains(bear)
        assert p1.life == 22  # its controller gains life = power (2)
        assert emeritus._prepared is False  # unprepared

    def test_not_prepared_has_no_ability(self) -> None:
        emeritus = EmeritusOfTruceSwordsToPlowshares()
        emeritus._prepared = False
        assert emeritus.get_activated_abilities() == []
