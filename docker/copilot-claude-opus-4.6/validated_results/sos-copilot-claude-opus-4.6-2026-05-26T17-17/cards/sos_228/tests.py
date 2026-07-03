"""Tests for SOS 228 — Social Snub.

Sorcery for {1}{W}{B}.
When you cast this spell while you control a creature, you may copy this spell.
Each player sacrifices a creature of their choice.
Each opponent loses 1 life and you gain 1 life.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_228.card_impl import SocialSnub
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestSocialSnubProperties:
    """Static card data should match the SOS 228 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(SocialSnub(owner=None), Sorcery)

    def test_name(self) -> None:
        assert SocialSnub(owner=None).name == "Social Snub"

    def test_mana_cost(self) -> None:
        assert SocialSnub(owner=None).mana_cost == ManaCost.parse("{1}{W}{B}")


class TestSocialSnubResolution:
    """Each player sacrifices a creature; each opponent loses 1 life, you gain 1."""

    def test_each_player_sacrifices_creature(self) -> None:
        """Both players should sacrifice a creature on resolution."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        snub = SocialSnub(owner=p1, controller=p1)
        bear1 = Creature(name="Bear A", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear2 = Creature(name="Bear B", owner=p2, controller=p2, base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear1)
        game.get_battlefield(p2).add(bear2)

        set_board_state(game, 0, hand=[snub], mana={ManaType.WHITE: 1, ManaType.BLACK: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Social Snub")

        # Both creatures should have been sacrificed (moved to graveyard)
        assert bear1 not in game.get_battlefield(p1)
        assert bear2 not in game.get_battlefield(p2)

    def test_opponent_loses_1_life(self) -> None:
        """Each opponent loses 1 life on resolution."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        snub = SocialSnub(owner=p1, controller=p1)
        bear1 = Creature(name="Bear A", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear2 = Creature(name="Bear B", owner=p2, controller=p2, base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear1)
        game.get_battlefield(p2).add(bear2)

        life_before = p2.life
        set_board_state(game, 0, hand=[snub], mana={ManaType.WHITE: 1, ManaType.BLACK: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Social Snub")

        assert p2.life == life_before - 1

    def test_caster_gains_1_life(self) -> None:
        """Caster gains 1 life on resolution."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        snub = SocialSnub(owner=p1, controller=p1)
        bear1 = Creature(name="Bear A", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear2 = Creature(name="Bear B", owner=p2, controller=p2, base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear1)
        game.get_battlefield(p2).add(bear2)

        life_before = p1.life
        set_board_state(game, 0, hand=[snub], mana={ManaType.WHITE: 1, ManaType.BLACK: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Social Snub")

        assert p1.life == life_before + 1


class TestSocialSnubCopyTrigger:
    """When cast while you control a creature, you may copy this spell."""

    def test_copied_when_controlling_creature(self) -> None:
        """If you control a creature when you cast, the spell is copied (double effect)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        snub = SocialSnub(owner=p1, controller=p1)
        # p1 controls two creatures (one for each sacrifice)
        bear1 = Creature(name="Bear A", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear2 = Creature(name="Bear C", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear3 = Creature(name="Bear B", owner=p2, controller=p2, base_power=2, base_toughness=2)
        bear4 = Creature(name="Bear D", owner=p2, controller=p2, base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear1)
        game.get_battlefield(p1).add(bear2)
        game.get_battlefield(p2).add(bear3)
        game.get_battlefield(p2).add(bear4)

        life_before_p2 = p2.life
        set_board_state(game, 0, hand=[snub], mana={ManaType.WHITE: 1, ManaType.BLACK: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Social Snub")

        # With copy, opponent should lose 2 life total (1 per resolution)
        assert p2.life == life_before_p2 - 2

    def test_no_copy_when_no_creature(self) -> None:
        """If you control no creature when you cast, no copy is made."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        snub = SocialSnub(owner=p1, controller=p1)
        # Only opponent has a creature
        bear = Creature(name="Bear B", owner=p2, controller=p2, base_power=2, base_toughness=2)
        game.get_battlefield(p2).add(bear)

        life_before_p2 = p2.life
        set_board_state(game, 0, hand=[snub], mana={ManaType.WHITE: 1, ManaType.BLACK: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Social Snub")

        # Only one resolution — opponent loses 1 life
        assert p2.life == life_before_p2 - 1
