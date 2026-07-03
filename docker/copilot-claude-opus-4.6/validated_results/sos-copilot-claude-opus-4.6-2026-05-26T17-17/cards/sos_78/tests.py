"""Tests for SOS 78 — Decorum Dissertation.

Sorcery — Lesson for {3}{B}{B}. Target player draws two cards and loses 2 life.
Has Paradigm (exile after resolution; after first resolve, cast copy free
at beginning of each first main phase).
"""

from __future__ import annotations

from cards.sos.sos_78.card_impl import DecorumDissertation
from engine.card import Sorcery
from engine.types import Keyword, ManaCost, Zone
from test_utils import create_game


class TestDecorumDissertationProperties:
    """Static card data should match the SOS 78 spec."""

    def test_name(self) -> None:
        card = DecorumDissertation(owner=None)
        assert card.name == "Decorum Dissertation"

    def test_mana_cost(self) -> None:
        card = DecorumDissertation(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{B}{B}")

    def test_is_sorcery(self) -> None:
        card = DecorumDissertation(owner=None)
        assert isinstance(card, Sorcery)

    def test_has_paradigm_keyword(self) -> None:
        card = DecorumDissertation(owner=None)
        assert Keyword.PARADIGM in card.keywords


class TestDecorumDissertationResolution:
    """Target player draws two cards and loses 2 life."""

    def test_target_player_draws_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        from engine.card import Card
        for i in range(5):
            c = Card(name=f"Card {i}", owner=p1)
            game.get_library(p1).add(c)
        spell = DecorumDissertation(owner=p1, controller=p1)
        spell.chosen_targets = [p1]
        hand_before = len(game.get_hand(p1).get_all())
        spell.on_resolve(game)
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after - hand_before == 2

    def test_target_player_loses_two_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        from engine.card import Card
        for i in range(5):
            c = Card(name=f"Card {i}", owner=p1)
            game.get_library(p1).add(c)
        spell = DecorumDissertation(owner=p1, controller=p1)
        spell.chosen_targets = [p1]
        life_before = p1.life
        spell.on_resolve(game)
        assert p1.life == life_before - 2

    def test_paradigm_exiles_after_resolution(self) -> None:
        """After resolution, the spell should be exiled (Paradigm)."""
        game = create_game()
        p1 = game.players[0]
        from engine.card import Card
        for i in range(5):
            c = Card(name=f"Card {i}", owner=p1)
            game.get_library(p1).add(c)
        spell = DecorumDissertation(owner=p1, controller=p1)
        spell.chosen_targets = [p1]
        spell.on_resolve(game)
        # The card should end up in exile
        exile_cards = game.get_exile(p1).get_all()
        assert spell in exile_cards
