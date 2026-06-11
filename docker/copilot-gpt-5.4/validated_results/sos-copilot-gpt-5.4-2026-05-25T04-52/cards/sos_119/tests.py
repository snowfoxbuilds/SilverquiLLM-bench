"""Tests for SOS 119 — Impractical Joke."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_119.card_impl import ImpracticalJoke
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Planeswalker, Sorcery
from benchmarks.sos.workspace.engine.game import deal_damage
from benchmarks.sos.workspace.engine.protection import ProtectionAbility
from benchmarks.sos.workspace.engine.turn import run_turn
from benchmarks.sos.workspace.engine.types import Color, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestImpracticalJokeProperties:
    """Static card data should match the SOS 119 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(ImpracticalJoke(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = ImpracticalJoke(owner=None)

        assert card.name == "Impractical Joke"
        assert card.mana_cost == ManaCost.parse("{R}")


class TestImpracticalJokeTargeting:
    """Impractical Joke should target up to one creature or planeswalker."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = ImpracticalJoke(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_planeswalkers_only(self) -> None:
        game = create_game()
        req = ImpracticalJoke(owner=None).get_targets(game)[0]

        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        planeswalker = Planeswalker(name="Visitor", starting_loyalty=3)
        non_target = CardImpl(name="Lecture Notes")

        assert req.filter_fn(creature) is True
        assert req.filter_fn(planeswalker) is True
        assert req.filter_fn(non_target) is False


class TestImpracticalJokeResolution:
    """Impractical Joke should damage its optional creature target."""

    def test_on_resolve_deals_three_damage_to_target_creature(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
        )
        game.get_battlefield(p2).add(target)

        spell = ImpracticalJoke(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.damage_marked == 3

    def test_on_resolve_makes_damage_unpreventable_for_the_rest_of_the_turn_only(self) -> None:
        game = create_game()
        p1, p2 = game.players
        p2.protections = [ProtectionAbility(quality=Color.RED)]

        spell = ImpracticalJoke(owner=p1, controller=p1)
        spell.chosen_targets = []
        spell.on_resolve(game)

        deal_damage(game, spell, p2, 3)

        assert p2.life == 17

        run_turn(game)

        deal_damage(game, spell, p2, 3)

        assert p2.life == 17

    def test_on_resolve_deals_three_damage_to_target_planeswalker(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Planeswalker(
            name="Target Walker",
            owner=p2,
            controller=p2,
            starting_loyalty=4,
        )
        game.get_battlefield(p2).add(target)

        spell = ImpracticalJoke(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.loyalty == 1
