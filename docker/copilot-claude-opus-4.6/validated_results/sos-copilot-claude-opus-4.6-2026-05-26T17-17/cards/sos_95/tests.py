"""Tests for SOS 95 — Pull from the Grave."""

from __future__ import annotations

import pytest

from cards.sos.sos_95.card_impl import PullFromTheGrave
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestPullFromTheGraveProperties:
    """Static card data should match the SOS 95 spec."""

    def test_is_sorcery(self) -> None:
        card = PullFromTheGrave(owner=None)
        assert CardType.SORCERY in card.card_types

    def test_name(self) -> None:
        assert PullFromTheGrave(owner=None).name == "Pull from the Grave"

    def test_mana_cost(self) -> None:
        assert PullFromTheGrave(owner=None).mana_cost == ManaCost.parse("{2}{B}")


class TestPullFromTheGraveEffect:
    """Return up to two target creature cards from graveyard to hand. Gain 2 life."""

    def test_returns_two_creatures_to_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]

        spell = PullFromTheGrave(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        wolf = Creature(name="Dire Wolf", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)

        set_board_state(game, 0, hand=[spell], graveyard=[bear, wolf],
                        mana={ManaType.BLACK: 1, ManaType.COLORLESS: 2})

        cast_spell(game, 0, "Pull from the Grave", targets=[bear, wolf])

        hand = game.get_hand(p1)
        hand_names = [c.name for c in hand]
        assert "Grizzly Bears" in hand_names
        assert "Dire Wolf" in hand_names

    def test_returns_one_creature_to_hand(self) -> None:
        """'Up to two' means you can choose just one target."""
        game = create_game()
        p1 = game.players[0]

        spell = PullFromTheGrave(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)

        set_board_state(game, 0, hand=[spell], graveyard=[bear],
                        mana={ManaType.BLACK: 1, ManaType.COLORLESS: 2})

        cast_spell(game, 0, "Pull from the Grave", targets=[bear])

        hand = game.get_hand(p1)
        hand_names = [c.name for c in hand]
        assert "Grizzly Bears" in hand_names

    def test_gains_two_life(self) -> None:
        game = create_game()
        p1 = game.players[0]

        spell = PullFromTheGrave(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)

        set_board_state(game, 0, hand=[spell], graveyard=[bear],
                        mana={ManaType.BLACK: 1, ManaType.COLORLESS: 2})

        life_before = p1.life
        cast_spell(game, 0, "Pull from the Grave", targets=[bear])

        assert p1.life == life_before + 2

    def test_gains_life_even_with_no_targets(self) -> None:
        """You should still gain 2 life even if you choose zero targets."""
        game = create_game()
        p1 = game.players[0]

        spell = PullFromTheGrave(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell],
                        mana={ManaType.BLACK: 1, ManaType.COLORLESS: 2})

        life_before = p1.life
        cast_spell(game, 0, "Pull from the Grave", targets=[])

        assert p1.life == life_before + 2
