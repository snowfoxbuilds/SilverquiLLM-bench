"""Tests for SOS 142 — Chelonian Tackle."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_142.card_impl import ChelonianTackle
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestChelonianTackleProperties:
    """Static card data should match the SOS 142 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(ChelonianTackle(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = ChelonianTackle(owner=None)

        assert card.name == "Chelonian Tackle"
        assert card.mana_cost == ManaCost.parse("{2}{G}")


class TestChelonianTackleTargeting:
    """Chelonian Tackle should target your creature, plus up to one opposing creature."""

    def test_returns_two_battlefield_target_requirements_with_optional_second_target(self) -> None:
        game = create_game()
        reqs = ChelonianTackle(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert isinstance(reqs[0], TargetRequirement)
        assert isinstance(reqs[1], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert reqs[1].zone == Zone.BATTLEFIELD
        assert getattr(reqs[1], "min_targets", 1) == 0

    def test_target_filters_accept_your_creature_then_an_opponents_creature(self) -> None:
        game = create_game()
        p1, p2 = game.players
        reqs = ChelonianTackle(owner=p1, controller=p1).get_targets(game)

        your_creature = Creature(
            name="Helpful Bear",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        opposing_creature = Creature(
            name="Opposing Bear",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
        )
        non_creature = CardImpl(name="Lecture Notes", owner=p1, controller=p1)

        assert reqs[0].filter_fn(your_creature) is True
        assert reqs[0].filter_fn(opposing_creature) is False
        assert reqs[0].filter_fn(non_creature) is False
        assert reqs[1].filter_fn(your_creature) is False
        assert reqs[1].filter_fn(opposing_creature) is True
        assert reqs[1].filter_fn(non_creature) is False


class TestChelonianTackleResolution:
    """Chelonian Tackle should add toughness before an optional fight."""

    def test_on_resolve_gives_plus_zero_plus_ten_then_fights_the_optional_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        your_creature = Creature(
            name="Sturdy Turtle",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        opposing_creature = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=4,
            base_toughness=12,
        )
        set_board_state(game, 0, battlefield=[your_creature])
        set_board_state(game, 1, battlefield=[opposing_creature])

        spell = ChelonianTackle(owner=p1, controller=p1)
        spell.chosen_targets = [your_creature, opposing_creature]
        spell.on_resolve(game)

        assert your_creature.power == 3
        assert your_creature.toughness == 13
        assert your_creature.damage_marked == 4
        assert opposing_creature.damage_marked == 3

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert your_creature.toughness == 3

    def test_on_resolve_allows_omitting_the_fight_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        your_creature = Creature(
            name="Sturdy Turtle",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        witness = Creature(
            name="Untouched Bear",
            owner=p2,
            controller=p2,
            base_power=4,
            base_toughness=4,
        )
        set_board_state(game, 0, battlefield=[your_creature])
        set_board_state(game, 1, battlefield=[witness])

        spell = ChelonianTackle(owner=p1, controller=p1)
        spell.chosen_targets = [your_creature, None]
        spell.on_resolve(game)

        assert your_creature.toughness == 13
        assert your_creature.damage_marked == 0
        assert witness.damage_marked == 0
