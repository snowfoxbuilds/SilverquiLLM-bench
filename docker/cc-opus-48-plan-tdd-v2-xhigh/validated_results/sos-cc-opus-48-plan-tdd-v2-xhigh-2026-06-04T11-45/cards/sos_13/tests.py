"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from test_utils import create_game, set_board_state


def _bear(name: str) -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


class TestEmeritusProperties:
    def test_name(self) -> None:
        c = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert c.name == "Emeritus of Truce // Swords to Plowshares"

    def test_cost(self) -> None:
        c = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert c.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_pt_subtypes(self) -> None:
        c = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert c.base_power == 3 and c.base_toughness == 3
        assert {"Cat", "Cleric"} <= c.subtypes

    def test_not_legendary(self) -> None:
        c = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert Supertype.LEGENDARY not in c.supertypes

    def test_starts_unprepared(self) -> None:
        assert EmeritusOfTruceSwordsToPlowshares(owner=None)._is_prepared is False


class TestEmeritusETB:
    def test_creates_inkling_token(self) -> None:
        game = create_game()
        p1, _ = game.players
        em = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        em.chosen_targets = [p1]
        em.on_resolve(game)
        toks = [o for o in game.get_battlefield(p1).get_all()
                if "Inkling" in getattr(o, "subtypes", set())]
        assert len(toks) == 1
        tok = toks[0]
        assert tok.base_power == 1 and tok.base_toughness == 1
        assert Keyword.FLYING in tok.keywords
        assert getattr(tok, "is_token", False) is True

    def test_token_goes_to_target_player(self) -> None:
        game = create_game()
        p1, p2 = game.players
        em = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        em.chosen_targets = [p2]
        em.on_resolve(game)
        assert any("Inkling" in getattr(o, "subtypes", set())
                   for o in game.get_battlefield(p2).get_all())

    def test_becomes_prepared_when_opponent_has_more(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 1, battlefield=[_bear("A"), _bear("B"), _bear("C")])
        em = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        em.chosen_targets = [p1]  # token to self
        em.on_resolve(game)
        assert em._is_prepared is True

    def test_not_prepared_when_even(self) -> None:
        game = create_game()
        p1, p2 = game.players
        em = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        em.chosen_targets = [p1]
        em.on_resolve(game)
        assert em._is_prepared is False


class TestEmeritusPreparedAbility:
    def test_stp_exiles_and_grants_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        victim = Creature(name="Ox", base_power=4, base_toughness=4)
        set_board_state(game, 1, battlefield=[victim], life=20)
        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        em = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        em._is_prepared = True

        ability = em.get_activated_abilities()[0]
        em._current_target = victim
        assert ability.cost(game, em) is True
        ability.effect(game)

        assert game.get_exile(p2).contains(victim)
        assert p2.life == 24
        assert em._is_prepared is False

    def test_ability_unavailable_when_not_prepared(self) -> None:
        game = create_game()
        p1, _ = game.players
        set_board_state(game, 0, mana={ManaType.WHITE: 1})
        em = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        em._is_prepared = False
        ability = em.get_activated_abilities()[0]
        assert ability.cost(game, em) is False
