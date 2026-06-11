"""Tests for SOS 108 — Artistic Process."""

from __future__ import annotations

import pytest

from cards.sos.sos_108.card_impl import ArtisticProcess
from engine.card import Creature, Sorcery
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestArtisticProcessProperties:
    """Static card data should match SOS 108 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(ArtisticProcess(owner=None), Sorcery)

    def test_name(self) -> None:
        assert ArtisticProcess(owner=None).name == "Artistic Process"

    def test_mana_cost(self) -> None:
        assert ArtisticProcess(owner=None).mana_cost == ManaCost.parse("{3}{R}{R}")


class TestArtisticProcessMode1:
    """Mode 1: Deal 6 damage to target creature."""

    def test_deals_6_damage_to_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Big Beast", owner=p2, controller=p2, base_power=4, base_toughness=7)
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        spell = ArtisticProcess(owner=p1, controller=p1)
        spell.chosen_mode = 1
        spell.chosen_targets = [target]
        spell.on_resolve(game)
        assert target.damage_taken == 6

    def test_kills_creature_with_6_or_less_toughness(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Small", owner=p2, controller=p2, base_power=2, base_toughness=4)
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        spell = ArtisticProcess(owner=p1, controller=p1)
        spell.chosen_mode = 1
        spell.chosen_targets = [target]
        spell.on_resolve(game)
        # 6 damage to 4 toughness creature is lethal
        assert target.damage_taken == 6


class TestArtisticProcessMode2:
    """Mode 2: Deal 2 damage to each creature you don't control."""

    def test_deals_2_to_opponent_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        opp1 = Creature(name="Opp1", owner=p2, controller=p2, base_power=2, base_toughness=3)
        opp1.card_types = {CardType.CREATURE}
        opp2 = Creature(name="Opp2", owner=p2, controller=p2, base_power=1, base_toughness=4)
        opp2.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(opp1)
        game.get_battlefield(p2).add(opp2)

        spell = ArtisticProcess(owner=p1, controller=p1)
        spell.chosen_mode = 2
        spell.on_resolve(game)
        assert opp1.damage_taken == 2
        assert opp2.damage_taken == 2

    def test_does_not_damage_own_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        own = Creature(name="MyCreature", owner=p1, controller=p1, base_power=3, base_toughness=3)
        own.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(own)

        opp = Creature(name="OppCreature", owner=p2, controller=p2, base_power=2, base_toughness=3)
        opp.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(opp)

        spell = ArtisticProcess(owner=p1, controller=p1)
        spell.chosen_mode = 2
        spell.on_resolve(game)
        assert own.damage_taken == 0
        assert opp.damage_taken == 2


class TestArtisticProcessMode3:
    """Mode 3: Create a 3/3 blue and red Elemental with flying and haste."""

    def test_creates_token(self) -> None:
        game = create_game()
        p1 = game.players[0]

        spell = ArtisticProcess(owner=p1, controller=p1)
        spell.chosen_mode = 3
        spell.on_resolve(game)

        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield if c.name == "Elemental"]
        assert len(tokens) == 1

    def test_token_stats(self) -> None:
        game = create_game()
        p1 = game.players[0]

        spell = ArtisticProcess(owner=p1, controller=p1)
        spell.chosen_mode = 3
        spell.on_resolve(game)

        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield if c.name == "Elemental"]
        token = tokens[0]
        assert token.power == 3
        assert token.toughness == 3
        assert Keyword.FLYING in token.keywords
        assert Keyword.HASTE in token.keywords
