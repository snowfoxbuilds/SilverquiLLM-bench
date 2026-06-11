"""Tests for SOS 73 — Arcane Omens."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_73.card_impl import ArcaneOmens
from benchmarks.sos.workspace.engine.card import CardImpl, Sorcery
from benchmarks.sos.workspace.engine.types import Color, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestArcaneOmensProperties:
    """Static card data should match the SOS 73 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(ArcaneOmens(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = ArcaneOmens(owner=None)
        assert card.name == "Arcane Omens"
        assert card.mana_cost == ManaCost.parse("{4}{B}")


class TestArcaneOmensTargeting:
    """Arcane Omens should target a single player."""

    def test_returns_single_target_requirement(self) -> None:
        game = create_game()
        reqs = ArcaneOmens(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_players_and_rejects_non_players(self) -> None:
        game = create_game()
        p1 = game.players[0]
        req = ArcaneOmens(owner=p1, controller=p1).get_targets(game)[0]
        non_player = CardImpl(name="Lecture Notes", owner=p1, controller=p1)

        assert req.filter_fn(game.players[0]) is True
        assert req.filter_fn(game.players[1]) is True
        assert req.filter_fn(non_player) is False


class TestArcaneOmensResolution:
    """Arcane Omens should make the target player discard based on distinct colors spent."""

    def test_target_player_discards_one_card_per_distinct_color_spent(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card_a = CardImpl(name="Card A", owner=p2, controller=p2)
        card_b = CardImpl(name="Card B", owner=p2, controller=p2)
        card_c = CardImpl(name="Card C", owner=p2, controller=p2)
        set_board_state(game, 1, hand=[card_a, card_b, card_c])
        p2._script.extend([card_a, card_c])

        spell = ArcaneOmens(owner=p1, controller=p1)
        spell.colors_spent = [Color.BLACK, Color.BLUE, Color.BLUE]
        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        assert not game.get_hand(p2).contains(card_a)
        assert game.get_hand(p2).contains(card_b)
        assert not game.get_hand(p2).contains(card_c)
        assert game.get_graveyard(p2).contains(card_a)
        assert game.get_graveyard(p2).contains(card_c)

    def test_zero_colors_spent_is_a_noop_even_with_a_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card_a = CardImpl(name="Card A", owner=p2, controller=p2)
        card_b = CardImpl(name="Card B", owner=p2, controller=p2)
        set_board_state(game, 1, hand=[card_a, card_b])

        spell = ArcaneOmens(owner=p1, controller=p1)
        spell.colors_spent = []
        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        assert game.get_hand(p2).get_all() == [card_a, card_b]
        assert game.get_graveyard(p2).get_all() == []

    def test_target_player_discards_all_available_cards_when_x_exceeds_hand_size(self) -> None:
        game = create_game()
        p1, p2 = game.players
        only_card = CardImpl(name="Only Card", owner=p2, controller=p2)
        set_board_state(game, 1, hand=[only_card])
        p2._script.append(only_card)

        spell = ArcaneOmens(owner=p1, controller=p1)
        spell.colors_spent = [Color.WHITE, Color.BLUE, Color.BLACK]
        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        assert game.get_hand(p2).get_all() == []
        assert game.get_graveyard(p2).contains(only_card)

