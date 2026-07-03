"""Tests for SOS 81 — End of the Hunt."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_81.card_impl import EndOfTheHunt
from benchmarks.sos.workspace.engine.card import Creature, Planeswalker, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestEndOfTheHuntProperties:
    """Static card data should match the SOS 81 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(EndOfTheHunt(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = EndOfTheHunt(owner=None)
        assert card.name == "End of the Hunt"
        assert card.mana_cost == ManaCost.parse("{1}{B}")


class TestEndOfTheHuntTargeting:
    """End of the Hunt should target an opponent, not a permanent."""

    def test_returns_single_target_requirement(self) -> None:
        game = create_game()
        reqs = EndOfTheHunt(owner=game.players[0], controller=game.players[0]).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_opponents_and_rejects_self_and_nonplayers(self) -> None:
        game = create_game()
        p1, p2 = game.players
        req = EndOfTheHunt(owner=p1, controller=p1).get_targets(game)[0]
        creature = Creature(name="Study Bear", base_power=2, base_toughness=2)

        assert req.filter_fn(p2) is True
        assert req.filter_fn(p1) is False
        assert req.filter_fn(creature) is False


class TestEndOfTheHuntResolution:
    """End of the Hunt should exile the target opponent's greatest permanent."""

    def test_exiles_the_creature_or_planeswalker_with_the_greatest_mana_value(self) -> None:
        game = create_game()
        p1, p2 = game.players
        smaller_creature = Creature(
            name="Smaller Creature",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}{B}"),
            base_power=3,
            base_toughness=3,
        )
        greatest_planeswalker = Planeswalker(
            name="Greatest Walker",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{4}{B}"),
            starting_loyalty=4,
        )
        game.get_battlefield(p2).add(smaller_creature)
        game.get_battlefield(p2).add(greatest_planeswalker)

        spell = EndOfTheHunt(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        assert game.get_exile(p2).contains(greatest_planeswalker)
        assert not game.get_battlefield(p2).contains(greatest_planeswalker)
        assert game.get_battlefield(p2).contains(smaller_creature)

    def test_target_opponent_chooses_which_permanent_to_exile_among_tied_greatest_mana_values(self) -> None:
        game = create_game()
        p1, p2 = game.players
        greatest_creature = Creature(
            name="Greatest Creature",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{4}{B}"),
            base_power=5,
            base_toughness=5,
        )
        greatest_planeswalker = Planeswalker(
            name="Greatest Walker",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{4}{B}"),
            starting_loyalty=5,
        )
        lesser_creature = Creature(
            name="Lesser Creature",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}{B}"),
            base_power=2,
            base_toughness=2,
        )
        p2._script.append(greatest_planeswalker)
        game.get_battlefield(p2).add(greatest_creature)
        game.get_battlefield(p2).add(greatest_planeswalker)
        game.get_battlefield(p2).add(lesser_creature)

        spell = EndOfTheHunt(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        assert game.get_exile(p2).contains(greatest_planeswalker)
        assert game.get_battlefield(p2).contains(greatest_creature)
        assert game.get_battlefield(p2).contains(lesser_creature)

    def test_target_opponent_with_no_creatures_or_planeswalkers_is_a_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = EndOfTheHunt(owner=p1, controller=p1)
        spell.chosen_targets = [p2]

        spell.on_resolve(game)

        assert game.get_exile(p1).get_all() == []
        assert game.get_exile(p2).get_all() == []
