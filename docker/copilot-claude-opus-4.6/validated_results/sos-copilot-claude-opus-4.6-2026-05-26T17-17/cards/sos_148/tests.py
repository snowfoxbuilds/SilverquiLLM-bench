"""Tests for SOS 148 — Follow the Lumarets."""

from __future__ import annotations

import pytest

from cards.sos.sos_148.card_impl import FollowTheLumarets
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestFollowTheLumaretsProperties:
    """Static card data should match the SOS 148 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(FollowTheLumarets(owner=None), Sorcery)

    def test_name(self) -> None:
        assert FollowTheLumarets(owner=None).name == "Follow the Lumarets"

    def test_mana_cost(self) -> None:
        assert FollowTheLumarets(owner=None).mana_cost == ManaCost.parse("{1}{G}")


class TestFollowTheLumaretsResolution:
    """Look at top 4, reveal creature/land to hand, rest on bottom."""

    def test_reveals_creature_from_top_four(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Grizzly Bears", owner=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        from engine.card import Land
        dummy1 = Sorcery(name="Dummy1", owner=p1)
        dummy2 = Sorcery(name="Dummy2", owner=p1)
        dummy3 = Sorcery(name="Dummy3", owner=p1)
        # Library top 4: bear, dummy1, dummy2, dummy3
        library = game.get_library(p1)
        library.extend([dummy3, dummy2, dummy1, bear])  # bear on top
        spell = FollowTheLumarets(owner=p1, controller=p1)
        spell.on_resolve(game)
        hand = game.get_hand(p1)
        assert any(c.name == "Grizzly Bears" for c in hand)

    def test_reveals_land_from_top_four(self) -> None:
        game = create_game()
        p1 = game.players[0]
        from engine.card import Land
        forest = Land(name="Forest", owner=p1)
        dummy1 = Sorcery(name="Dummy1", owner=p1)
        dummy2 = Sorcery(name="Dummy2", owner=p1)
        dummy3 = Sorcery(name="Dummy3", owner=p1)
        library = game.get_library(p1)
        library.extend([dummy3, dummy2, dummy1, forest])
        spell = FollowTheLumarets(owner=p1, controller=p1)
        spell.on_resolve(game)
        hand = game.get_hand(p1)
        assert any(c.name == "Forest" for c in hand)

    def test_rest_go_to_bottom(self) -> None:
        """Cards not chosen go to the bottom of library."""
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Grizzly Bears", owner=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        dummy1 = Sorcery(name="Dummy1", owner=p1)
        dummy2 = Sorcery(name="Dummy2", owner=p1)
        dummy3 = Sorcery(name="Dummy3", owner=p1)
        library = game.get_library(p1)
        library.extend([dummy3, dummy2, dummy1, bear])
        spell = FollowTheLumarets(owner=p1, controller=p1)
        spell.on_resolve(game)
        # Remaining 3 cards should be on bottom of library
        lib = game.get_library(p1)
        bottom_names = {c.name for c in lib[:3]}
        assert "Dummy1" in bottom_names
        assert "Dummy2" in bottom_names
        assert "Dummy3" in bottom_names

    def test_infusion_gained_life_reveals_two(self) -> None:
        """If you gained life this turn, may reveal two creature/land cards."""
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Grizzly Bears", owner=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        from engine.card import Land
        forest = Land(name="Forest", owner=p1)
        dummy1 = Sorcery(name="Dummy1", owner=p1)
        dummy2 = Sorcery(name="Dummy2", owner=p1)
        library = game.get_library(p1)
        library.extend([dummy2, dummy1, forest, bear])
        # Mark that player gained life this turn
        p1.life_gained_this_turn = 3
        spell = FollowTheLumarets(owner=p1, controller=p1)
        spell.on_resolve(game)
        hand = game.get_hand(p1)
        hand_names = [c.name for c in hand]
        assert "Grizzly Bears" in hand_names
        assert "Forest" in hand_names

    def test_no_creature_or_land_in_top_four(self) -> None:
        """If no creature or land among top 4, all go to bottom."""
        game = create_game()
        p1 = game.players[0]
        dummy1 = Sorcery(name="Dummy1", owner=p1)
        dummy2 = Sorcery(name="Dummy2", owner=p1)
        dummy3 = Sorcery(name="Dummy3", owner=p1)
        dummy4 = Sorcery(name="Dummy4", owner=p1)
        library = game.get_library(p1)
        library.extend([dummy4, dummy3, dummy2, dummy1])
        spell = FollowTheLumarets(owner=p1, controller=p1)
        spell.on_resolve(game)
        hand = game.get_hand(p1)
        assert len(hand) == 0
