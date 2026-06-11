"""Tests for SOS 95 — Pull from the Grave."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_95.card_impl import PullFromTheGrave
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestPullFromTheGraveProperties:
    """Static card data should match the SOS 95 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(PullFromTheGrave(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = PullFromTheGrave(owner=None)

        assert card.name == "Pull from the Grave"
        assert card.mana_cost == ManaCost.parse("{2}{B}")


class TestPullFromTheGraveTargeting:
    """Pull from the Grave should target creature cards in your graveyard."""

    def test_returns_a_single_graveyard_target_requirement(self) -> None:
        game = create_game()
        p1 = game.players[0]
        reqs = PullFromTheGrave(owner=p1, controller=p1).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.GRAVEYARD

    def test_target_filter_accepts_your_creature_cards_and_rejects_opponents_and_noncreatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        req = PullFromTheGrave(owner=p1, controller=p1).get_targets(game)[0]
        your_creature = Creature(
            name="Your Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opponents_creature = Creature(
            name="Opposing Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        non_creature = CardImpl(name="Lecture Notes", owner=p1, controller=p1)

        assert req.filter_fn(your_creature) is True
        assert req.filter_fn(opponents_creature) is False
        assert req.filter_fn(non_creature) is False


class TestPullFromTheGraveResolution:
    """Pull from the Grave should return up to two creatures and gain life."""

    def test_on_resolve_returns_up_to_two_chosen_creature_cards_from_your_graveyard_to_your_hand_and_you_gain_two_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature_a = Creature(
            name="Returned Bear A",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        creature_b = Creature(
            name="Returned Bear B",
            owner=p1,
            controller=p1,
            base_power=3,
            base_toughness=3,
        )
        filler = CardImpl(name="Unreturned Notes", owner=p1, controller=p1)
        game.get_graveyard(p1).add(creature_a)
        game.get_graveyard(p1).add(creature_b)
        game.get_graveyard(p1).add(filler)

        card = PullFromTheGrave(owner=p1, controller=p1)
        card.chosen_targets = [creature_a, creature_b]
        card.on_resolve(game)

        assert game.get_hand(p1).contains(creature_a)
        assert game.get_hand(p1).contains(creature_b)
        assert not game.get_graveyard(p1).contains(creature_a)
        assert not game.get_graveyard(p1).contains(creature_b)
        assert game.get_graveyard(p1).contains(filler)
        assert p1.life == 22

    def test_on_resolve_still_gains_two_life_when_you_return_only_one_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = Creature(
            name="Returned Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        game.get_graveyard(p1).add(creature)

        card = PullFromTheGrave(owner=p1, controller=p1)
        card.chosen_targets = [creature]
        card.on_resolve(game)

        assert game.get_hand(p1).contains(creature)
        assert not game.get_graveyard(p1).contains(creature)
        assert p1.life == 22
