"""Tests for SOS 51 — Fractalize."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_51.card_impl import Fractalize
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestFractalizeProperties:
    """Static card data should match the SOS 51 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(Fractalize(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = Fractalize(owner=None)
        assert card.name == "Fractalize"
        assert card.mana_cost == ManaCost.parse("{X}{U}")


class TestFractalizeTargeting:
    """Fractalize should target a creature on the battlefield."""

    def test_returns_single_creature_target_requirement(self) -> None:
        game = create_game()
        reqs = Fractalize(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_rejects_noncreatures(self) -> None:
        game = create_game()
        req = Fractalize(owner=None).get_targets(game)[0]
        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        non_creature = CardImpl(name="Campus Notes")

        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_creature) is False


class TestFractalizeResolution:
    """Fractalize should temporarily overwrite a creature's colors, types, and base stats."""

    def test_x_zero_turns_target_into_a_1_1_green_and_blue_fractal(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Curious Adept",
            owner=p1,
            controller=p1,
            subtypes={"Elf", "Wizard"},
            base_power=2,
            base_toughness=3,
        )
        target.colors = {Color.RED}
        game.get_battlefield(p1).add(target)

        spell = Fractalize(owner=p1, controller=p1)
        spell.x_value = 0  # type: ignore[attr-defined]
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert get_colors(target) == {Color.GREEN, Color.BLUE}
        assert target.subtypes == {"Fractal"}
        assert target.power == 1
        assert target.toughness == 1

    def test_effect_expires_at_end_of_turn_restoring_original_colors_types_and_stats(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Curious Adept",
            owner=p1,
            controller=p1,
            subtypes={"Elf", "Wizard"},
            base_power=2,
            base_toughness=3,
        )
        target.colors = {Color.RED}
        game.get_battlefield(p1).add(target)

        spell = Fractalize(owner=p1, controller=p1)
        spell.x_value = 2  # type: ignore[attr-defined]
        spell.chosen_targets = [target]
        spell.on_resolve(game)
        assert get_colors(target) == {Color.GREEN, Color.BLUE}
        assert target.subtypes == {"Fractal"}
        assert target.power == 3
        assert target.toughness == 3

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert get_colors(target) == {Color.RED}
        assert target.subtypes == {"Elf", "Wizard"}
        assert target.power == 2
        assert target.toughness == 3
