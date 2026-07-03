"""Tests for SOS 71 — Wisdom of Ages."""

from __future__ import annotations

import pytest

from cards.sos.sos_71.card_impl import WisdomOfAges
from engine.card import Sorcery, Creature, Instant
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestWisdomOfAgesProperties:
    """Static card data should match the SOS 71 spec."""

    def test_is_sorcery(self) -> None:
        card = WisdomOfAges(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        assert WisdomOfAges(owner=None).name == "Wisdom of Ages"

    def test_mana_cost(self) -> None:
        assert WisdomOfAges(owner=None).mana_cost == ManaCost.parse("{4}{U}{U}{U}")


class TestWisdomOfAgesResolution:
    """on_resolve returns all instants/sorceries from graveyard to hand."""

    def test_returns_instant_from_graveyard_to_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        bolt.card_types = {CardType.INSTANT}

        spell = WisdomOfAges(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[bolt], hand=[spell],
                        mana={ManaType.BLUE: 7, ManaType.COLORLESS: 4})

        spell.on_resolve(game)

        # The instant should be in hand now
        hand_names = [c.name for c in game.get_hand(p1)]
        assert "Lightning Bolt" in hand_names

    def test_returns_sorcery_from_graveyard_to_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]

        sorc = Sorcery(name="Divination", owner=p1, controller=p1)
        sorc.card_types = {CardType.SORCERY}

        spell = WisdomOfAges(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[sorc], hand=[spell],
                        mana={ManaType.BLUE: 7, ManaType.COLORLESS: 4})

        spell.on_resolve(game)

        hand_names = [c.name for c in game.get_hand(p1)]
        assert "Divination" in hand_names

    def test_does_not_return_creature_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}

        bolt = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        bolt.card_types = {CardType.INSTANT}

        spell = WisdomOfAges(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[bear, bolt], hand=[spell],
                        mana={ManaType.BLUE: 7, ManaType.COLORLESS: 4})

        spell.on_resolve(game)

        hand_names = [c.name for c in game.get_hand(p1)]
        assert "Lightning Bolt" in hand_names
        assert "Grizzly Bears" not in hand_names

    def test_no_maximum_hand_size_after_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]

        spell = WisdomOfAges(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[], hand=[spell],
                        mana={ManaType.BLUE: 7, ManaType.COLORLESS: 4})

        spell.on_resolve(game)

        # Player should have no maximum hand size
        assert p1.max_hand_size is None or p1.max_hand_size == float('inf')

    def test_exiles_itself_after_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]

        spell = WisdomOfAges(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[], hand=[spell],
                        mana={ManaType.BLUE: 7, ManaType.COLORLESS: 4})

        spell.on_resolve(game)

        # Wisdom of Ages should be in exile
        exile_names = [c.name for c in game.get_exile(p1)]
        assert "Wisdom of Ages" in exile_names

    def test_empty_graveyard_still_sets_no_max_hand_size(self) -> None:
        game = create_game()
        p1 = game.players[0]

        spell = WisdomOfAges(owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[], hand=[spell],
                        mana={ManaType.BLUE: 7, ManaType.COLORLESS: 4})

        spell.on_resolve(game)

        assert p1.max_hand_size is None or p1.max_hand_size == float('inf')
