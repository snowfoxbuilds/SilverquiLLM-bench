"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


def _bear(name: str, power: int = 2) -> Creature:
    c = Creature(name=name, base_power=power, base_toughness=2)
    c.card_types = {CardType.CREATURE}
    return c


class TestProperties:
    def test_basics(self) -> None:
        c = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert c.name == "Emeritus of Truce"
        assert c.mana_cost == ManaCost.parse("{1}{W}{W}")
        assert c.base_power == 3 and c.base_toughness == 3
        assert {"Cat", "Cleric"} <= c.subtypes
        assert isinstance(c, Creature)


class TestEnters:
    def test_token_and_prepared_when_behind(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emer = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[])
        set_board_state(
            game, 1, battlefield=[_bear("O1"), _bear("O2"), _bear("O3")]
        )
        emer.chosen_targets = [p1]
        emer.on_resolve(game)
        tokens = [
            c for c in game.get_battlefield(p1).get_all() if c.name == "Inkling"
        ]
        assert len(tokens) == 1
        token = tokens[0]
        assert token.base_power == 1 and token.base_toughness == 1
        assert token.keywords & Keyword.FLYING
        # your creatures = 1 token + the entering Emeritus = 2; opponent has 3.
        assert emer._prepared is True

    def test_not_prepared_when_ahead(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emer = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[])
        set_board_state(game, 1, battlefield=[])
        emer.chosen_targets = [p1]
        emer.on_resolve(game)
        assert emer._prepared is False


class TestPrepared:
    def test_swords_exiles_and_gains_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        emer = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        emer._prepared = True
        victim = _bear("Victim", power=3)
        set_board_state(game, 0, battlefield=[emer], mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[victim], life=20)
        ability = emer.get_activated_abilities()[0]
        p1._script.extend([victim])  # choose target to exile
        assert ability.cost(game, emer) is True
        ability.effect(game)
        assert victim not in game.get_battlefield(p2).get_all()
        assert victim in p2.zones[Zone.EXILE].get_all()
        assert p2.life == 23  # gained life equal to victim's power (3)
        assert emer._prepared is False

    def test_cost_blocked_when_not_prepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        emer = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        emer._prepared = False
        set_board_state(game, 0, battlefield=[emer], mana={ManaType.WHITE: 1})
        ability = emer.get_activated_abilities()[0]
        assert ability.cost(game, emer) is False
