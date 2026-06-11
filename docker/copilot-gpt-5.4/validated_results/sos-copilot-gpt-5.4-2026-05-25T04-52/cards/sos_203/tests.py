"""Tests for SOS 203 — Mind Roots."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_203.card_impl import MindRoots
from benchmarks.sos.workspace.engine.card import CardImpl, Land, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestMindRootsProperties:
    """Static card data should match the SOS 203 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(MindRoots(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = MindRoots(owner=None)

        assert card.name == "Mind Roots"
        assert card.mana_cost == ManaCost.parse("{1}{B}{G}")


class TestMindRootsTargeting:
    """Mind Roots should target a player."""

    def test_returns_a_single_player_target_requirement(self) -> None:
        game = create_game()
        reqs = MindRoots(owner=game.players[0], controller=game.players[0]).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_players_and_rejects_nonplayers(self) -> None:
        game = create_game()
        req = MindRoots(owner=game.players[0], controller=game.players[0]).get_targets(game)[0]

        assert req.filter_fn(game.players[0]) is True
        assert req.filter_fn(game.players[1]) is True
        assert req.filter_fn(CardImpl(name="Not a player")) is False


class TestMindRootsResolution:
    """Mind Roots should make the target discard and optionally steal a discarded land."""

    def test_target_player_discards_two_cards_and_you_may_put_one_discarded_land_onto_the_battlefield_tapped(self) -> None:
        game = create_game()
        p1, p2 = game.players
        land = Land(name="Campus Grounds", owner=p2, controller=p2)
        spell_card = CardImpl(name="Loose Formula", owner=p2, controller=p2)

        set_board_state(game, 1, hand=[land, spell_card])
        p2._script.extend([land, spell_card])
        p1._script.extend([True, land])

        spell = MindRoots(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        assert game.get_battlefield(p1).contains(land)
        assert land.controller is p1
        assert land.is_tapped is True
        assert game.get_graveyard(p2).contains(spell_card)
        assert not game.get_graveyard(p2).contains(land)
        assert not game.get_hand(p2).contains(land)
        assert not game.get_hand(p2).contains(spell_card)

    def test_you_may_leave_the_discarded_land_in_the_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        land = Land(name="Unclaimed Campus", owner=p2, controller=p2)
        spell_card = CardImpl(name="Spent Notes", owner=p2, controller=p2)

        set_board_state(game, 1, hand=[land, spell_card])
        p2._script.extend([land, spell_card])
        p1._script.append(False)

        spell = MindRoots(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        assert game.get_graveyard(p2).contains(land)
        assert game.get_graveyard(p2).contains(spell_card)
        assert game.get_battlefield(p1).get_all() == []

    def test_only_a_land_discarded_this_way_can_be_put_onto_the_battlefield(self) -> None:
        game = create_game()
        p1, p2 = game.players
        old_land = Land(name="Old Campus", owner=p2, controller=p2)
        spell_a = CardImpl(name="Old Formula", owner=p2, controller=p2)
        spell_b = CardImpl(name="New Formula", owner=p2, controller=p2)

        set_board_state(game, 1, hand=[spell_a, spell_b], graveyard=[old_land])
        p2._script.extend([spell_a, spell_b])
        p1._script.extend([True, old_land])

        spell = MindRoots(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        assert game.get_graveyard(p2).contains(old_land)
        assert game.get_graveyard(p2).contains(spell_a)
        assert game.get_graveyard(p2).contains(spell_b)
        assert game.get_battlefield(p1).get_all() == []
