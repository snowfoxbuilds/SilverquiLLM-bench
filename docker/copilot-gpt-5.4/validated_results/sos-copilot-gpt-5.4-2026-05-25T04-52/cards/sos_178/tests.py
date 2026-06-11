"""Tests for SOS 178 — Borrowed Knowledge."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_178.card_impl import BorrowedKnowledge
from benchmarks.sos.workspace.engine.card import CardImpl, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestBorrowedKnowledgeProperties:
    """Static card data should match the SOS 178 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(BorrowedKnowledge(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = BorrowedKnowledge(owner=None)

        assert card.name == "Borrowed Knowledge"
        assert card.mana_cost == ManaCost.parse("{2}{R}{W}")


class TestBorrowedKnowledgeModes:
    """Borrowed Knowledge should expose its printed modes and targeting."""

    def test_exposes_the_two_printed_modes(self) -> None:
        modes = BorrowedKnowledge(owner=None).get_modes()

        assert len(modes) == 2
        assert "target opponent's hand" in modes[0].description
        assert "cards discarded this way" in modes[1].description

    def test_first_mode_targets_a_single_opponent(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = BorrowedKnowledge(owner=p1, controller=p1)
        spell.selected_mode = 0
        reqs = spell.get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert reqs[0].filter_fn(p1) is False
        assert reqs[0].filter_fn(p2) is True
        assert reqs[0].filter_fn(CardImpl(name="Not a player")) is False

    def test_second_mode_has_no_targets(self) -> None:
        game = create_game()
        spell = BorrowedKnowledge(owner=game.players[0], controller=game.players[0])
        spell.selected_mode = 1

        assert spell.get_targets(game) == []


class TestBorrowedKnowledgeResolution:
    """Each mode should discard your hand first, then draw the right amount."""

    def test_first_mode_discards_your_hand_then_draws_equal_to_targets_hand_size(self) -> None:
        game = create_game()
        p1, p2 = game.players
        discard_a = CardImpl(name="Spent Note A", owner=p1, controller=p1)
        discard_b = CardImpl(name="Spent Note B", owner=p1, controller=p1)
        opp_a = CardImpl(name="Opposing Card A", owner=p2, controller=p2)
        opp_b = CardImpl(name="Opposing Card B", owner=p2, controller=p2)
        opp_c = CardImpl(name="Opposing Card C", owner=p2, controller=p2)
        draw_a = CardImpl(name="Fresh Card A", owner=p1, controller=p1)
        draw_b = CardImpl(name="Fresh Card B", owner=p1, controller=p1)
        draw_c = CardImpl(name="Fresh Card C", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[discard_a, discard_b])
        set_board_state(game, 1, hand=[opp_a, opp_b, opp_c])
        game.get_library(p1).add(draw_a)
        game.get_library(p1).add(draw_b)
        game.get_library(p1).add(draw_c)

        spell = BorrowedKnowledge(owner=p1, controller=p1)
        spell.selected_mode = 0
        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        assert game.get_graveyard(p1).contains(discard_a)
        assert game.get_graveyard(p1).contains(discard_b)
        assert not game.get_hand(p1).contains(discard_a)
        assert not game.get_hand(p1).contains(discard_b)
        assert game.get_hand(p1).contains(draw_a)
        assert game.get_hand(p1).contains(draw_b)
        assert game.get_hand(p1).contains(draw_c)

    def test_second_mode_discards_your_hand_then_draws_equal_to_cards_discarded_this_way(self) -> None:
        game = create_game()
        p1 = game.players[0]
        discard_a = CardImpl(name="Spent Note A", owner=p1, controller=p1)
        discard_b = CardImpl(name="Spent Note B", owner=p1, controller=p1)
        draw_a = CardImpl(name="Fresh Card A", owner=p1, controller=p1)
        draw_b = CardImpl(name="Fresh Card B", owner=p1, controller=p1)
        draw_c = CardImpl(name="Fresh Card C", owner=p1, controller=p1)
        set_board_state(game, 0, hand=[discard_a, discard_b])
        game.get_library(p1).add(draw_a)
        game.get_library(p1).add(draw_b)
        game.get_library(p1).add(draw_c)

        spell = BorrowedKnowledge(owner=p1, controller=p1)
        spell.selected_mode = 1
        spell.on_resolve(game)

        assert game.get_graveyard(p1).contains(discard_a)
        assert game.get_graveyard(p1).contains(discard_b)
        assert game.get_hand(p1).contains(draw_a)
        assert game.get_hand(p1).contains(draw_b)
        assert not game.get_hand(p1).contains(draw_c)

