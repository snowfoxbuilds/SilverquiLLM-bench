"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares (Preparation)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_13.card_impl import (
    EmeritusOfTruceSwordsToPlowshares,
    _SwordsToPlowshares,
)
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


def _emeritus(player: Any) -> EmeritusOfTruceSwordsToPlowshares:
    return EmeritusOfTruceSwordsToPlowshares(owner=player, controller=player)


def _bear(player: Any, name: str = "Bear", power: int = 2) -> Creature:
    return Creature(
        name=name, owner=player, controller=player, base_power=power, base_toughness=2
    )


def _resolve_stack(game: Any) -> None:
    """Pop and resolve the stack, running SBAs after each resolution."""
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _inklings(game: Any, player: Any) -> list[Any]:
    return [
        o
        for o in game.get_battlefield(player).get_all()
        if getattr(o, "name", None) == "Inkling"
    ]


def _stp_in_exile(player: Any) -> list[Any]:
    return [
        o
        for o in player.zones[Zone.EXILE].get_all()
        if getattr(o, "name", None) == "Swords to Plowshares"
    ]


class TestEmeritusProperties:
    def test_name(self) -> None:
        assert (
            EmeritusOfTruceSwordsToPlowshares().name
            == "Emeritus of Truce // Swords to Plowshares"
        )

    def test_mana_cost(self) -> None:
        assert EmeritusOfTruceSwordsToPlowshares().mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_power_toughness(self) -> None:
        c = EmeritusOfTruceSwordsToPlowshares()
        assert c.base_power == 3
        assert c.base_toughness == 3

    def test_types_and_colors(self) -> None:
        c = EmeritusOfTruceSwordsToPlowshares()
        assert CardType.CREATURE in c.card_types
        assert {"Cat", "Cleric"} <= c.subtypes
        assert c.colors == ["W"]

    def test_starts_unprepared(self) -> None:
        c = EmeritusOfTruceSwordsToPlowshares()
        assert c.prepared is False


class TestEmeritusETB:
    def _fire_etb(self, game: Any, emeritus: Any, controller: Any) -> None:
        emeritus.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=controller),
        )
        _resolve_stack(game)

    def test_etb_creates_inkling_for_chosen_player(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        emeritus = _emeritus(p1)
        set_board_state(game, 0, battlefield=[emeritus])
        p1._script.append(p1)  # choose self as the token's player
        self._fire_etb(game, emeritus, p1)

        tokens = _inklings(game, p1)
        assert len(tokens) == 1
        assert _inklings(game, p2) == []

    def test_inkling_token_characteristics(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        emeritus = _emeritus(p1)
        set_board_state(game, 0, battlefield=[emeritus])
        p1._script.append(p1)
        self._fire_etb(game, emeritus, p1)

        token = _inklings(game, p1)[0]
        assert token.power == 1
        assert token.toughness == 1
        assert Keyword.FLYING in token.keywords
        assert "Inkling" in token.subtypes
        assert token.colors == ["W", "B"]
        assert token.is_token is True

    def test_etb_token_can_go_to_opponent(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        emeritus = _emeritus(p1)
        set_board_state(game, 0, battlefield=[emeritus])
        p1._script.append(p2)  # gift the token to the opponent
        self._fire_etb(game, emeritus, p1)

        assert len(_inklings(game, p2)) == 1
        assert _inklings(game, p1) == []

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        emeritus = _emeritus(p1)
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(
            game, 1, battlefield=[_bear(p2), _bear(p2, "B2"), _bear(p2, "B3")]
        )
        p1._script.append(p1)  # token to self → p1 controls 2 creatures
        self._fire_etb(game, emeritus, p1)

        # p1: emeritus + inkling = 2; p2: 3 bears → opponent has more.
        assert emeritus.prepared is True
        assert len(_stp_in_exile(p1)) == 1

    def test_not_prepared_when_you_have_at_least_as_many(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        emeritus = _emeritus(p1)
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[_bear(p2)])
        p1._script.append(p1)  # token to self → p1 controls 2, p2 controls 1
        self._fire_etb(game, emeritus, p1)

        assert emeritus.prepared is False
        assert _stp_in_exile(p1) == []

    def test_become_prepared_is_idempotent(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        emeritus = _emeritus(p1)
        set_board_state(game, 0, battlefield=[emeritus])
        emeritus._become_prepared(game)
        emeritus._become_prepared(game)
        assert emeritus.prepared is True
        assert len(_stp_in_exile(p1)) == 1


class TestSwordsToPlowsharesProperties:
    def test_prepare_spell_is_white_instant(self) -> None:
        stp = _SwordsToPlowshares()
        assert stp.name == "Swords to Plowshares"
        assert stp.mana_cost == ManaCost.parse("{W}")
        assert CardType.INSTANT in stp.card_types
        assert stp.colors == ["W"]


class TestCastPrepared:
    def _prepared_setup(self):
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        emeritus = _emeritus(p1)
        set_board_state(game, 0, battlefield=[emeritus], mana={ManaType.WHITE: 1})
        emeritus._become_prepared(game)
        return game, p1, p2, emeritus

    def test_cannot_cast_when_not_prepared(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        emeritus = _emeritus(p1)
        set_board_state(game, 0, battlefield=[emeritus], mana={ManaType.WHITE: 1})
        assert emeritus.can_cast_prepared(game) is False
        assert emeritus.cast_prepared(game) is False

    def test_cannot_cast_without_mana(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        emeritus = _emeritus(p1)
        set_board_state(game, 0, battlefield=[emeritus])
        emeritus._become_prepared(game)
        assert emeritus.can_cast_prepared(game) is False
        assert emeritus.cast_prepared(game) is False
        # Still prepared — the failed cast did not consume the designation.
        assert emeritus.prepared is True

    def test_cast_prepared_exiles_creature_and_gains_life(self) -> None:
        game, p1, p2, emeritus = self._prepared_setup()
        target = _bear(p2, "Victim", power=4)
        set_board_state(game, 1, battlefield=[target], life=20)
        p1._script.append(target)  # target choice for Swords to Plowshares

        assert emeritus.cast_prepared(game) is True
        _resolve_stack(game)

        assert p2.zones[Zone.EXILE].contains(target)
        assert p2.life == 24  # gains life equal to exiled creature's power
        assert p1.mana_pool.get(ManaType.WHITE) == 0

    def test_cast_prepared_unprepares(self) -> None:
        game, p1, p2, emeritus = self._prepared_setup()
        target = _bear(p2, "Victim", power=2)
        set_board_state(game, 1, battlefield=[target])
        p1._script.append(target)

        emeritus.cast_prepared(game)
        _resolve_stack(game)

        assert emeritus.prepared is False
        assert emeritus._stp_copy is None

    def test_cast_copy_ceases_to_exist_after_resolution(self) -> None:
        game, p1, p2, emeritus = self._prepared_setup()
        target = _bear(p2, "Victim", power=2)
        set_board_state(game, 1, battlefield=[target])
        p1._script.append(target)

        emeritus.cast_prepared(game)
        _resolve_stack(game)

        # The cast copy is not a real card — it leaves no trace.
        assert _stp_in_exile(p1) == []
        assert not any(
            getattr(o, "name", None) == "Swords to Plowshares"
            for o in p1.zones[Zone.GRAVEYARD].get_all()
        )
