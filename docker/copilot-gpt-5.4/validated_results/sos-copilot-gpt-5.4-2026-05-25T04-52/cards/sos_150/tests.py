"""Tests for SOS 150 — Glorious Decay."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_150.card_impl import GloriousDecay
from benchmarks.sos.workspace.engine.card import Artifact, CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.card import Mode
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestGloriousDecayProperties:
    """Static card data should match the SOS 150 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(GloriousDecay(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = GloriousDecay(owner=None)

        assert card.name == "Glorious Decay"
        assert card.mana_cost == ManaCost.parse("{1}{G}")


class TestGloriousDecayModes:
    """Glorious Decay should expose its three printed modes."""

    def test_exposes_three_printed_modes(self) -> None:
        modes = GloriousDecay(owner=None).get_modes()

        assert len(modes) == 3
        assert all(isinstance(mode, Mode) for mode in modes)
        assert "Destroy target artifact" in modes[0].description
        assert "4 damage" in modes[1].description
        assert "Exile target card from a graveyard" in modes[2].description


class TestGloriousDecayTargeting:
    """Target requirements should follow the selected mode."""

    def test_artifact_mode_targets_a_single_artifact_on_the_battlefield(self) -> None:
        game = create_game()
        spell = GloriousDecay(owner=game.players[0], controller=game.players[0])
        spell.selected_mode = 0
        reqs = spell.get_targets(game)
        artifact = Artifact(name="Target Relic")
        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)

        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert reqs[0].filter_fn(artifact) is True
        assert reqs[0].filter_fn(creature) is False

    def test_flying_damage_mode_targets_a_single_flying_creature_on_the_battlefield(self) -> None:
        game = create_game()
        spell = GloriousDecay(owner=game.players[0], controller=game.players[0])
        spell.selected_mode = 1
        reqs = spell.get_targets(game)
        flying_creature = Creature(
            name="Flying Target",
            base_power=2,
            base_toughness=2,
            keywords=Keyword.FLYING,
        )
        ground_creature = Creature(name="Ground Target", base_power=2, base_toughness=2)

        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert reqs[0].filter_fn(flying_creature) is True
        assert reqs[0].filter_fn(ground_creature) is False

    def test_graveyard_mode_targets_a_single_card_in_a_graveyard(self) -> None:
        game = create_game()
        spell = GloriousDecay(owner=game.players[0], controller=game.players[0])
        spell.selected_mode = 2
        reqs = spell.get_targets(game)
        graveyard_card = CardImpl(name="Spent Notes")

        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.GRAVEYARD
        assert reqs[0].filter_fn(graveyard_card) is True


class TestGloriousDecayResolution:
    """Each Glorious Decay mode should resolve as printed."""

    def test_artifact_mode_destroys_the_target_artifact(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Artifact(name="Target Relic", owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[target])

        spell = GloriousDecay(owner=p1, controller=p1)
        spell.selected_mode = 0
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert game.get_graveyard(p2).contains(target)
        assert not game.get_battlefield(p2).contains(target)

    def test_flying_damage_mode_deals_four_damage_to_the_target_creature_with_flying(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Flying Target",
            owner=p2,
            controller=p2,
            base_power=4,
            base_toughness=4,
            keywords=Keyword.FLYING,
        )
        set_board_state(game, 1, battlefield=[target])

        spell = GloriousDecay(owner=p1, controller=p1)
        spell.selected_mode = 1
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.damage_marked == 4

    def test_graveyard_mode_exiles_the_target_card_and_draws_a_card(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = CardImpl(name="Spent Notes", owner=p2, controller=p2)
        drawn = CardImpl(name="Fresh Lesson", owner=p1, controller=p1)
        set_board_state(game, 1, graveyard=[target])
        game.get_library(p1).add(drawn)

        spell = GloriousDecay(owner=p1, controller=p1)
        spell.selected_mode = 2
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert game.get_exile(p2).contains(target)
        assert not game.get_graveyard(p2).contains(target)
        assert game.get_hand(p1).contains(drawn)
