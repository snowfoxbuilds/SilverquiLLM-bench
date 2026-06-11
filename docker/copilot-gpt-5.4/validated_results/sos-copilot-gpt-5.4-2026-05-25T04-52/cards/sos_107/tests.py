"""Tests for SOS 107 — Archaic's Agony."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_107.card_impl import ArchaicsAgony
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.types import Color, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestArchaicsAgonyProperties:
    """Static card data should match the SOS 107 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(ArchaicsAgony(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = ArchaicsAgony(owner=None)
        assert card.name == "Archaic's Agony"
        assert card.mana_cost == ManaCost.parse("{4}{R}")


class TestArchaicsAgonyTargeting:
    """Archaic's Agony should target a single creature on the battlefield."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = ArchaicsAgony(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_rejects_noncreatures(self) -> None:
        game = create_game()
        req = ArchaicsAgony(owner=None).get_targets(game)[0]

        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        non_creature = CardImpl(name="Lecture Notes")

        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_creature) is False


class TestArchaicsAgonyResolution:
    """Archaic's Agony should use distinct colors spent for damage and excess exile."""

    def test_distinct_colors_spent_determine_damage_and_excess_cards_exiled(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Small Assistant",
            owner=p2,
            controller=p2,
            base_power=1,
            base_toughness=1,
        )
        top = CardImpl(name="Top Card", owner=p1, controller=p1)
        next_card = CardImpl(name="Next Card", owner=p1, controller=p1)
        bottom = CardImpl(name="Bottom Card", owner=p1, controller=p1)
        set_board_state(game, 1, battlefield=[target])
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(next_card)
        game.get_library(p1).add(top)

        spell = ArchaicsAgony(owner=p1, controller=p1)
        spell.colors_spent = [Color.RED, Color.BLUE, Color.GREEN]
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert target.damage_marked == 3
        assert game.get_exile(p1).contains(top)
        assert game.get_exile(p1).contains(next_card)
        assert not game.get_library(p1).contains(top)
        assert not game.get_library(p1).contains(next_card)
        assert game.get_library(p1).contains(bottom)

    def test_excess_cards_get_controller_only_play_permission_until_end_of_next_turn(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Small Assistant",
            owner=p2,
            controller=p2,
            base_power=1,
            base_toughness=1,
        )
        top = CardImpl(name="Top Card", owner=p1, controller=p1)
        next_card = CardImpl(name="Next Card", owner=p1, controller=p1)
        bottom = CardImpl(name="Bottom Card", owner=p1, controller=p1)
        set_board_state(game, 1, battlefield=[target])
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(next_card)
        game.get_library(p1).add(top)

        spell = ArchaicsAgony(owner=p1, controller=p1)
        spell.colors_spent = [Color.RED, Color.BLUE, Color.GREEN]
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        permissions = game.get_exile_play_permissions(player=p1)

        assert game.can_player_play_exiled_card(p1, top) is True
        assert game.can_player_play_exiled_card(p1, next_card) is True
        assert game.can_player_play_exiled_card(p1, bottom) is False
        assert game.can_player_play_exiled_card(p2, top) is False
        assert len(permissions) == 2
        assert {permission.card for permission in permissions} == {top, next_card}
        assert all(permission.source is spell for permission in permissions)

    def test_damage_without_excess_exiles_no_cards(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Study Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        library_card = CardImpl(name="Library Card", owner=p1, controller=p1)
        set_board_state(game, 1, battlefield=[target])
        game.get_library(p1).add(library_card)

        spell = ArchaicsAgony(owner=p1, controller=p1)
        spell.colors_spent = [Color.RED, Color.BLUE]
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert target.damage_marked == 2
        assert game.get_exile(p1).get_all() == []
        assert game.get_library(p1).contains(library_card)

    def test_zero_colors_spent_is_a_noop_even_with_a_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Study Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        library_card = CardImpl(name="Library Card", owner=p1, controller=p1)
        set_board_state(game, 1, battlefield=[target])
        game.get_library(p1).add(library_card)

        spell = ArchaicsAgony(owner=p1, controller=p1)
        spell.colors_spent = []
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert target.damage_marked == 0
        assert game.get_exile(p1).get_all() == []
        assert game.get_library(p1).contains(library_card)

    def test_excess_card_play_permission_expires_after_controllers_next_turn(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Small Assistant",
            owner=p2,
            controller=p2,
            base_power=1,
            base_toughness=1,
        )
        top = CardImpl(name="Top Card", owner=p1, controller=p1)
        next_card = CardImpl(name="Next Card", owner=p1, controller=p1)
        set_board_state(game, 1, battlefield=[target])
        game.get_library(p1).add(next_card)
        game.get_library(p1).add(top)

        spell = ArchaicsAgony(owner=p1, controller=p1)
        spell.colors_spent = [Color.RED, Color.BLUE, Color.GREEN]
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert game.can_player_play_exiled_card(p1, top) is True
        assert game.can_player_play_exiled_card(p1, next_card) is True

        for _ in range(12):
            game.advance_phase()
        assert game.can_player_play_exiled_card(p1, top) is True
        assert game.can_player_play_exiled_card(p1, next_card) is True

        for _ in range(12):
            game.advance_phase()
        assert game.can_player_play_exiled_card(p1, top) is True
        assert game.can_player_play_exiled_card(p1, next_card) is True

        for _ in range(12):
            game.advance_phase()
        assert game.can_player_play_exiled_card(p1, top) is False
        assert game.can_player_play_exiled_card(p1, next_card) is False
