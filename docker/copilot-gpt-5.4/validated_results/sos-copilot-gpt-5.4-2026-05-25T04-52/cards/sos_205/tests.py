"""Tests for SOS 205 — Moment of Reckoning."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_205.card_impl import MomentOfReckoning
from benchmarks.sos.workspace.engine.card import Artifact, CardImpl, Creature, Enchantment, Land, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestMomentOfReckoningProperties:
    """Static card data should match the SOS 205 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(MomentOfReckoning(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = MomentOfReckoning(owner=None)

        assert card.name == "Moment of Reckoning"
        assert card.mana_cost == ManaCost.parse("{3}{W}{W}{B}{B}")


class TestMomentOfReckoningModes:
    """Moment of Reckoning should expose its two repeatable printed modes."""

    def test_exposes_destroy_and_return_modes(self) -> None:
        modes = MomentOfReckoning(owner=None).get_modes()

        assert len(modes) == 2
        assert "Destroy target nonland permanent" in modes[0].description
        assert "Return target nonland permanent card from your graveyard" in modes[1].description


class TestMomentOfReckoningTargeting:
    """Target requirements should match each selected mode instance."""

    def test_destroy_modes_target_nonland_permanents_on_the_battlefield(self) -> None:
        game = create_game()
        spell = MomentOfReckoning(owner=game.players[0], controller=game.players[0])
        spell.selected_modes = [0, 0]  # type: ignore[attr-defined]
        reqs = spell.get_targets(game)
        artifact = Artifact(name="Relic", mana_cost=ManaCost.parse("{2}"))
        land = Land(name="Campus")

        assert len(reqs) == 2
        assert all(isinstance(req, TargetRequirement) for req in reqs)
        assert all(req.zone == Zone.BATTLEFIELD for req in reqs)
        assert all(req.filter_fn(artifact) is True for req in reqs)
        assert all(req.filter_fn(land) is False for req in reqs)

    def test_return_modes_target_nonland_permanent_cards_in_your_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = MomentOfReckoning(owner=p1, controller=p1)
        spell.selected_modes = [1, 1]  # type: ignore[attr-defined]
        your_creature = Creature(
            name="Recovered Student",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{2}"),
            base_power=2,
            base_toughness=2,
        )
        opponent_creature = Creature(
            name="Not Yours",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}"),
            base_power=2,
            base_toughness=2,
        )
        land = Land(name="Campus", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[your_creature, land])
        set_board_state(game, 1, graveyard=[opponent_creature])
        reqs = spell.get_targets(game)

        assert len(reqs) == 2
        assert all(req.zone == Zone.GRAVEYARD for req in reqs)
        assert all(req.filter_fn(your_creature) is True for req in reqs)
        assert all(req.filter_fn(land) is False for req in reqs)
        assert all(req.filter_fn(opponent_creature) is False for req in reqs)

    def test_repeated_modes_produce_one_target_requirement_per_mode_instance(self) -> None:
        game = create_game()
        spell = MomentOfReckoning(owner=game.players[0], controller=game.players[0])
        spell.selected_modes = [0, 0, 1, 1]  # type: ignore[attr-defined]
        reqs = spell.get_targets(game)

        assert len(reqs) == 4
        assert [req.zone for req in reqs] == [
            Zone.BATTLEFIELD,
            Zone.BATTLEFIELD,
            Zone.GRAVEYARD,
            Zone.GRAVEYARD,
        ]


class TestMomentOfReckoningResolution:
    """Moment of Reckoning should resolve each chosen mode, including repeats."""

    def test_destroy_and_return_modes_both_resolve(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_artifact = Artifact(
            name="Enemy Relic",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}"),
        )
        return_card = Creature(
            name="Recovered Student",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{2}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(game, 0, graveyard=[return_card])
        set_board_state(game, 1, battlefield=[target_artifact])

        spell = MomentOfReckoning(owner=p1, controller=p1)
        spell.selected_modes = [0, 1]  # type: ignore[attr-defined]
        spell.chosen_targets = [target_artifact, return_card]
        spell.on_resolve(game)

        assert game.get_graveyard(p2).contains(target_artifact)
        assert game.get_battlefield(p1).contains(return_card)
        assert not game.get_graveyard(p1).contains(return_card)

    def test_same_destroy_mode_can_be_chosen_more_than_once(self) -> None:
        game = create_game()
        p1, p2 = game.players
        artifact = Artifact(name="Enemy Relic", owner=p2, controller=p2, mana_cost=ManaCost.parse("{2}"))
        enchantment = Enchantment(name="Enemy Lesson", owner=p2, controller=p2, mana_cost=ManaCost.parse("{3}"))
        land = Land(name="Enemy Campus", owner=p2, controller=p2)

        set_board_state(game, 1, battlefield=[artifact, enchantment, land])

        spell = MomentOfReckoning(owner=p1, controller=p1)
        spell.selected_modes = [0, 0]  # type: ignore[attr-defined]
        spell.chosen_targets = [artifact, enchantment]
        spell.on_resolve(game)

        assert game.get_graveyard(p2).contains(artifact)
        assert game.get_graveyard(p2).contains(enchantment)
        assert game.get_battlefield(p2).contains(land)
