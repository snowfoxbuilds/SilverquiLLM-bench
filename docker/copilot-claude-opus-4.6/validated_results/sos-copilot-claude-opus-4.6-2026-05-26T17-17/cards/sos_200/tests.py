"""Tests for SOS 200 — Lorehold Charm."""

from __future__ import annotations

import pytest

from cards.sos.sos_200.card_impl import LoreholdCharm
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestLoreholdCharmProperties:
    """Static card data should match the SOS 200 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(LoreholdCharm(owner=None), Instant)

    def test_name(self) -> None:
        assert LoreholdCharm(owner=None).name == "Lorehold Charm"

    def test_mana_cost(self) -> None:
        assert LoreholdCharm(owner=None).mana_cost == ManaCost.parse("{R}{W}")


class TestLoreholdCharmMode1:
    """Mode 1: Each opponent sacrifices a nontoken artifact."""

    def test_opponent_sacrifices_nontoken_artifact(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Give opponent a nontoken artifact
        artifact = Creature(name="Sol Ring", owner=p2, controller=p2,
                            base_power=0, base_toughness=0)
        artifact.card_types = {CardType.ARTIFACT}
        artifact.is_token = False
        game.get_battlefield(p2).add(artifact)

        charm = LoreholdCharm(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[charm], mana={ManaType.RED: 1, ManaType.WHITE: 1})
        cast_spell(game, 0, "Lorehold Charm", mode=1)

        assert artifact not in game.get_battlefield(p2)
        assert artifact in game.get_graveyard(p2)

    def test_does_not_sacrifice_token_artifact(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Give opponent a token artifact
        token_art = Creature(name="Treasure", owner=p2, controller=p2,
                             base_power=0, base_toughness=0)
        token_art.card_types = {CardType.ARTIFACT}
        token_art.is_token = True
        game.get_battlefield(p2).add(token_art)

        charm = LoreholdCharm(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[charm], mana={ManaType.RED: 1, ManaType.WHITE: 1})
        cast_spell(game, 0, "Lorehold Charm", mode=1)

        # Token artifact should remain since it's a token
        assert token_art in game.get_battlefield(p2)

    def test_no_artifact_is_a_noop(self) -> None:
        """If opponent has no nontoken artifacts, nothing happens."""
        game = create_game()
        p1 = game.players[0]

        charm = LoreholdCharm(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[charm], mana={ManaType.RED: 1, ManaType.WHITE: 1})
        # Should not raise
        cast_spell(game, 0, "Lorehold Charm", mode=1)


class TestLoreholdCharmMode2:
    """Mode 2: Return artifact or creature card with MV <= 2 from graveyard to battlefield."""

    def test_returns_creature_mv2_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        bear.mana_cost = ManaCost.parse("{1}{G}")
        game.get_graveyard(p1).add(bear)

        charm = LoreholdCharm(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[charm], mana={ManaType.RED: 1, ManaType.WHITE: 1})
        cast_spell(game, 0, "Lorehold Charm", mode=2, targets=[bear])

        assert bear in game.get_battlefield(p1)
        assert bear not in game.get_graveyard(p1)

    def test_cannot_return_creature_mv3(self) -> None:
        """Cannot target creature with MV > 2."""
        game = create_game()
        p1 = game.players[0]

        big = Creature(name="Big Creature", owner=p1, controller=p1,
                       base_power=3, base_toughness=3)
        big.card_types = {CardType.CREATURE}
        big.mana_cost = ManaCost.parse("{2}{G}")  # MV = 3
        game.get_graveyard(p1).add(big)

        charm = LoreholdCharm(owner=p1, controller=p1)
        targets = charm.get_targets(game, mode=2)
        # big should not be a valid target
        if targets:
            req = targets[0]
            assert req.filter_fn(big) is False

    def test_returns_artifact_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]

        artifact = Creature(name="Signal Pest", owner=p1, controller=p1,
                            base_power=0, base_toughness=1)
        artifact.card_types = {CardType.ARTIFACT}
        artifact.mana_cost = ManaCost.parse("{1}")
        game.get_graveyard(p1).add(artifact)

        charm = LoreholdCharm(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[charm], mana={ManaType.RED: 1, ManaType.WHITE: 1})
        cast_spell(game, 0, "Lorehold Charm", mode=2, targets=[artifact])

        assert artifact in game.get_battlefield(p1)


class TestLoreholdCharmMode3:
    """Mode 3: Creatures you control get +1/+1 and gain trample until end of turn."""

    def test_creatures_get_plus_one(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        charm = LoreholdCharm(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[charm], mana={ManaType.RED: 1, ManaType.WHITE: 1})
        cast_spell(game, 0, "Lorehold Charm", mode=3)

        assert bear.power == 3
        assert bear.toughness == 3

    def test_creatures_gain_trample(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        charm = LoreholdCharm(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[charm], mana={ManaType.RED: 1, ManaType.WHITE: 1})
        cast_spell(game, 0, "Lorehold Charm", mode=3)

        assert Keyword.TRAMPLE in bear.keywords_granted

    def test_buff_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        charm = LoreholdCharm(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[charm], mana={ManaType.RED: 1, ManaType.WHITE: 1})
        cast_spell(game, 0, "Lorehold Charm", mode=3)

        game.end_turn()
        assert bear.power == 2
        assert bear.toughness == 2
        assert Keyword.TRAMPLE not in getattr(bear, 'keywords_granted', set())

    def test_does_not_affect_opponent_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        opp_bear = Creature(name="Opp Bear", owner=p2, controller=p2,
                            base_power=2, base_toughness=2)
        opp_bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(opp_bear)

        charm = LoreholdCharm(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[charm], mana={ManaType.RED: 1, ManaType.WHITE: 1})
        cast_spell(game, 0, "Lorehold Charm", mode=3)

        assert opp_bear.power == 2
        assert opp_bear.toughness == 2
