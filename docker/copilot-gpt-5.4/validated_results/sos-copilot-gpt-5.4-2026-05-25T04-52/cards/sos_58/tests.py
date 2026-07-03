"""Tests for SOS 58 — Mathemagics."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_58.card_impl import Mathemagics
from benchmarks.sos.workspace.engine.card import CardImpl, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestMathemagicsProperties:
    """Static card data should match the SOS 58 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(Mathemagics(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = Mathemagics(owner=None)
        assert card.name == "Mathemagics"
        assert card.mana_cost == ManaCost.parse("{X}{X}{U}{U}")


class TestMathemagicsTargeting:
    """Mathemagics should target a player."""

    def test_returns_a_single_player_target_requirement(self) -> None:
        game = create_game()
        reqs = Mathemagics(owner=game.players[0], controller=game.players[0]).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert reqs[0].filter_fn(game.players[0]) is True
        assert reqs[0].filter_fn(game.players[1]) is True


class TestMathemagicsResolution:
    """Mathemagics should draw 2^X cards for the chosen player."""

    def test_x_value_zero_draws_one_card_for_the_target_player(self) -> None:
        game = create_game()
        p1, p2 = game.players
        drawn_card = CardImpl(name="Single Insight", owner=p2, controller=p2)
        game.get_library(p2).add(drawn_card)
        spell = Mathemagics(owner=p1, controller=p1)
        spell.x_value = 0  # type: ignore[attr-defined]
        spell.chosen_targets = [p2]

        spell.on_resolve(game)

        assert game.get_hand(p2).contains(drawn_card)
        assert len(game.get_hand(p2).get_all()) == 1
        assert len(game.get_library(p2).get_all()) == 0

    def test_x_value_three_draws_eight_cards_for_the_target_player_only(self) -> None:
        game = create_game()
        p1, p2 = game.players
        drawn_cards = [CardImpl(name=f"Insight {idx}", owner=p2, controller=p2) for idx in range(8)]
        for card in drawn_cards:
            game.get_library(p2).add(card)
        spell = Mathemagics(owner=p1, controller=p1)
        spell.x_value = 3  # type: ignore[attr-defined]
        spell.chosen_targets = [p2]

        spell.on_resolve(game)

        assert len(game.get_hand(p2).get_all()) == 8
        assert all(game.get_hand(p2).contains(card) for card in drawn_cards)
        assert len(game.get_library(p2).get_all()) == 0
        assert len(game.get_hand(p1).get_all()) == 0
