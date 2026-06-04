"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import _resolve_top_of_stack, create_game, set_board_state


def _bear(name: str = "Bear", power: int = 2, toughness: int = 2) -> Creature:
    return Creature(name=name, base_power=power, base_toughness=toughness)


def _fire_etb(game: Any, emeritus: Any, controller: Any) -> None:
    game.trigger_manager.fire_event(
        game,
        EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=controller),
    )
    _resolve_top_of_stack(game)


class TestEmeritusProperties:
    def test_is_creature(self) -> None:
        assert isinstance(EmeritusOfTruceSwordsToPlowshares(owner=None), Creature)

    def test_name(self) -> None:
        assert (
            EmeritusOfTruceSwordsToPlowshares(owner=None).name == "Emeritus of Truce"
        )

    def test_mana_cost(self) -> None:
        assert EmeritusOfTruceSwordsToPlowshares(
            owner=None
        ).mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_pt(self) -> None:
        c = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert c.base_power == 3
        assert c.base_toughness == 3

    def test_cat_cleric_not_legendary(self) -> None:
        c = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cat" in c.subtypes
        assert "Cleric" in c.subtypes
        assert Supertype.LEGENDARY not in c.supertypes

    def test_starts_unprepared(self) -> None:
        assert EmeritusOfTruceSwordsToPlowshares(owner=None)._prepared is False


class TestEmeritusETB:
    def test_creates_inkling_for_target_player(self) -> None:
        game = create_game()
        p0, p1 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[])
        emeritus.register_triggers(game)

        p0._script.append(p0)  # target self
        _fire_etb(game, emeritus, p0)

        tokens = [
            obj
            for obj in p0.zones[Zone.BATTLEFIELD].get_all()
            if getattr(obj, "name", None) == "Inkling"
        ]
        assert len(tokens) == 1
        inkling = tokens[0]
        assert inkling.base_power == 1
        assert inkling.base_toughness == 1
        assert Keyword.FLYING in inkling.keywords
        assert "Inkling" in inkling.subtypes
        assert inkling.is_token is True

    def test_token_goes_to_chosen_opponent(self) -> None:
        game = create_game()
        p0, p1 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[])
        emeritus.register_triggers(game)

        p0._script.append(p1)  # give the token to the opponent
        _fire_etb(game, emeritus, p0)

        assert any(
            getattr(o, "name", None) == "Inkling"
            for o in p1.zones[Zone.BATTLEFIELD].get_all()
        )
        assert not any(
            getattr(o, "name", None) == "Inkling"
            for o in p0.zones[Zone.BATTLEFIELD].get_all()
        )

    def test_becomes_prepared_when_opponent_has_more(self) -> None:
        game = create_game()
        p0, p1 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[_bear(), _bear(), _bear()])
        emeritus.register_triggers(game)

        p0._script.append(p0)  # token to self → p0 has 2, p1 has 3
        _fire_etb(game, emeritus, p0)

        assert emeritus._prepared is True

    def test_not_prepared_when_you_have_at_least_as_many(self) -> None:
        game = create_game()
        p0, p1 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[])
        emeritus.register_triggers(game)

        p0._script.append(p0)  # p0 has 2 creatures, p1 has 0
        _fire_etb(game, emeritus, p0)

        assert emeritus._prepared is False


class TestEmeritusSwords:
    def test_no_ability_when_unprepared(self) -> None:
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert emeritus.get_activated_abilities() == []

    def test_prepared_exposes_ability(self) -> None:
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=None)
        emeritus._prepared = True
        assert len(emeritus.get_activated_abilities()) == 1

    def test_swords_exiles_and_gains_life(self) -> None:
        game = create_game()
        p0, p1 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p0, controller=p0)
        emeritus._prepared = True
        victim = _bear(power=4, toughness=4)
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[victim], life=20)

        ability = emeritus.get_activated_abilities()[0]
        p0._script.append(victim)  # creature to exile

        assert ability.cost(game) is True
        ability.effect(game)

        assert p1.zones[Zone.EXILE].contains(victim)
        assert not p1.zones[Zone.BATTLEFIELD].contains(victim)
        assert p1.life == 24  # gained life equal to the creature's power (4)
        assert emeritus._prepared is False  # casting the copy unprepares it

    def test_swords_zero_power_gains_no_life(self) -> None:
        game = create_game()
        p0, p1 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p0, controller=p0)
        emeritus._prepared = True
        wall = _bear(name="Wall", power=0, toughness=4)
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[wall], life=20)

        ability = emeritus.get_activated_abilities()[0]
        p0._script.append(wall)
        ability.cost(game)
        ability.effect(game)

        assert p1.zones[Zone.EXILE].contains(wall)
        assert p1.life == 20
