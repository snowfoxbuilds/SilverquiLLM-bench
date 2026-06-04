"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares (Prepared)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell, _resolve_top_of_stack


def _creature(name: str, owner: Any) -> Creature:
    c = Creature(name=name, owner=owner, controller=owner,
                 base_power=2, base_toughness=2)
    c.card_types = {CardType.CREATURE}
    return c


class TestProperties:
    def test_is_creature(self) -> None:
        c = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(c, Creature)

    def test_name_cost_pt(self) -> None:
        c = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert c.name == "Emeritus of Truce // Swords to Plowshares"
        assert c.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert c.base_power == 3
        assert c.base_toughness == 3

    def test_starts_unprepared(self) -> None:
        c = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert c.prepared is False


class TestEnters:
    def test_etb_creates_inkling_token(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})

        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares",
                   targets=[p1])

        bf = p1.zones[Zone.BATTLEFIELD].get_all()
        inklings = [c for c in bf if getattr(c, "name", "") == "Inkling"]
        assert len(inklings) == 1
        assert Keyword.FLYING in inklings[0].keywords
        assert getattr(inklings[0], "is_token", False) is True

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        set_board_state(game, 1, battlefield=[_creature(f"Opp{i}", p2)
                                              for i in range(3)])

        # Target self: p1 ends with Emeritus + Inkling = 2; p2 has 3 → prepared.
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares",
                   targets=[p1])

        assert emeritus.prepared is True

    def test_not_prepared_when_you_have_at_least_as_many(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[emeritus],
                        mana={ManaType.COLORLESS: 1, ManaType.WHITE: 2})
        # p2 has no creatures.
        cast_spell(game, 0, "Emeritus of Truce // Swords to Plowshares",
                   targets=[p1])

        assert emeritus.prepared is False


class TestPreparedSpell:
    def _activate_stp(self, game: Any, player: Any, emeritus: Any) -> None:
        ability = emeritus.get_activated_abilities(game)[0]
        inst = ActivatedAbilityInstance(
            source=emeritus, controller=player,
            cost=ability.cost, effect=ability.effect,
        )
        activate_ability(game, player, inst)
        _resolve_top_of_stack(game)

    def test_no_ability_while_unprepared(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[emeritus])
        assert emeritus.get_activated_abilities(game) == []

    def test_prepared_exiles_creature_and_grants_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        victim = Creature(name="Victim", owner=p2, controller=p2,
                          base_power=4, base_toughness=4)
        victim.card_types = {CardType.CREATURE}
        set_board_state(game, 0, battlefield=[emeritus],
                        mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[victim], life=20)
        emeritus.prepared = True
        p1._script.append(victim)  # choose_card target for StP

        self._activate_stp(game, p1, emeritus)

        assert victim in p2.zones[Zone.EXILE].get_all()
        assert p2.life == 24  # gained life equal to victim's power (4)
        assert emeritus.prepared is False  # unprepared after casting the copy

    def test_prepared_consumed_only_once(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emeritus = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        victim = Creature(name="Victim", owner=p2, controller=p2,
                          base_power=1, base_toughness=1)
        victim.card_types = {CardType.CREATURE}
        set_board_state(game, 0, battlefield=[emeritus],
                        mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[victim], life=20)
        emeritus.prepared = True
        p1._script.append(victim)

        self._activate_stp(game, p1, emeritus)
        # After casting, the ability is no longer offered.
        assert emeritus.get_activated_abilities(game) == []
