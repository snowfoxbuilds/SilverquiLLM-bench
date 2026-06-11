"""Tests for SOS 105 — Withering Curse."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_105.card_impl import WitheringCurse
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.state_based_actions import resolve_state_based_actions
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestWitheringCurseProperties:
    """Static card data should match the SOS 105 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(WitheringCurse(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = WitheringCurse(owner=None)

        assert card.name == "Withering Curse"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")


class TestWitheringCurseResolution:
    """Withering Curse should either shrink creatures or destroy them if infused."""

    def test_without_life_gain_all_creatures_get_minus_two_minus_two_until_end_of_turn(self) -> None:
        game = create_game()
        p1, p2 = game.players
        first = Creature(name="First Bear", owner=p1, controller=p1, base_power=3, base_toughness=3)
        second = Creature(name="Second Bear", owner=p2, controller=p2, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[first])
        set_board_state(game, 1, battlefield=[second])

        WitheringCurse(owner=p1, controller=p1).on_resolve(game)

        assert first.power == 1
        assert first.toughness == 1
        assert second.power == 2
        assert second.toughness == 2

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert first.power == 3
        assert first.toughness == 3
        assert second.power == 4
        assert second.toughness == 4

    def test_without_life_gain_creatures_reduced_to_zero_toughness_die(self) -> None:
        game = create_game()
        p1, p2 = game.players
        first = Creature(name="First Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        second = Creature(name="Second Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[first])
        set_board_state(game, 1, battlefield=[second])

        WitheringCurse(owner=p1, controller=p1).on_resolve(game)
        resolve_state_based_actions(game)

        assert game.get_graveyard(p1).contains(first)
        assert game.get_graveyard(p2).contains(second)

    def test_if_you_gained_life_this_turn_it_destroys_all_creatures_instead_of_shrinking_them(self) -> None:
        game = create_game()
        p1, p2 = game.players
        first = Creature(name="First Bear", owner=p1, controller=p1, base_power=3, base_toughness=3)
        second = Creature(name="Second Bear", owner=p2, controller=p2, base_power=5, base_toughness=5)
        set_board_state(game, 0, battlefield=[first])
        set_board_state(game, 1, battlefield=[second])
        p1.life_gained_this_turn = 1

        WitheringCurse(owner=p1, controller=p1).on_resolve(game)

        assert game.get_graveyard(p1).contains(first)
        assert game.get_graveyard(p2).contains(second)
        assert not game.get_battlefield(p1).contains(first)
        assert not game.get_battlefield(p2).contains(second)

    def test_infused_mode_uses_destroy_instead_so_an_indestructible_creature_survives_unchanged(self) -> None:
        game = create_game()
        p1, p2 = game.players
        doomed = Creature(name="Doomed Bear", owner=p1, controller=p1, base_power=3, base_toughness=3)
        indestructible = Creature(
            name="Stubborn Witness",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
            keywords=Keyword.INDESTRUCTIBLE,
        )
        set_board_state(game, 0, battlefield=[doomed])
        set_board_state(game, 1, battlefield=[indestructible])
        p1.life_gained_this_turn = 1

        WitheringCurse(owner=p1, controller=p1).on_resolve(game)

        assert game.get_graveyard(p1).contains(doomed)
        assert game.get_battlefield(p2).contains(indestructible)
        assert not game.get_graveyard(p2).contains(indestructible)
        assert indestructible.power == 3
        assert indestructible.toughness == 3
