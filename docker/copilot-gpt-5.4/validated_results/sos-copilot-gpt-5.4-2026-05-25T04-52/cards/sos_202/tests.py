"""Tests for SOS 202 — Mind into Matter."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_202.card_impl import MindIntoMatter
from benchmarks.sos.workspace.engine.card import Artifact, CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestMindIntoMatterProperties:
    """Static card data should match the SOS 202 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(MindIntoMatter(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = MindIntoMatter(owner=None)

        assert card.name == "Mind into Matter"
        assert card.mana_cost == ManaCost.parse("{X}{G}{U}")


class TestMindIntoMatterResolution:
    """Mind into Matter should draw X cards, then optionally deploy a permanent."""

    def test_draws_x_cards_and_may_put_an_eligible_permanent_onto_the_battlefield_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        drawn_one = CardImpl(name="First Insight", owner=p1, controller=p1)
        drawn_two = CardImpl(name="Second Insight", owner=p1, controller=p1)
        creature = Creature(
            name="Laboratory Beast",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}{G}"),
            base_power=2,
            base_toughness=2,
        )

        game.get_library(p1).add(drawn_one)
        game.get_library(p1).add(drawn_two)
        set_board_state(game, 0, hand=[creature])
        p1._script.extend([True, creature])

        spell = MindIntoMatter(owner=p1, controller=p1)
        spell.x_value = 2  # type: ignore[attr-defined]
        spell.on_resolve(game)

        assert game.get_hand(p1).contains(drawn_one)
        assert game.get_hand(p1).contains(drawn_two)
        assert game.get_battlefield(p1).contains(creature)
        assert creature.is_tapped is True
        assert not game.get_hand(p1).contains(creature)

    def test_may_decline_to_put_an_eligible_permanent_onto_the_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        drawn = CardImpl(name="Lecture Notes", owner=p1, controller=p1)
        artifact = Artifact(
            name="Study Relic",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}"),
        )

        game.get_library(p1).add(drawn)
        set_board_state(game, 0, hand=[artifact])
        p1._script.append(False)

        spell = MindIntoMatter(owner=p1, controller=p1)
        spell.x_value = 1  # type: ignore[attr-defined]
        spell.on_resolve(game)

        assert game.get_hand(p1).contains(drawn)
        assert game.get_hand(p1).contains(artifact)
        assert game.get_battlefield(p1).get_all() == []

    def test_ineligible_cards_do_not_get_put_onto_the_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        drawn_one = CardImpl(name="Fresh Theory", owner=p1, controller=p1)
        drawn_two = CardImpl(name="Fresh Practice", owner=p1, controller=p1)
        expensive_artifact = Artifact(
            name="Overbudget Engine",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{3}"),
        )
        nonpermanent = Sorcery(
            name="Still a Spell",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}{G}"),
        )

        game.get_library(p1).add(drawn_one)
        game.get_library(p1).add(drawn_two)
        set_board_state(game, 0, hand=[expensive_artifact, nonpermanent])
        p1._script.extend([True, expensive_artifact])

        spell = MindIntoMatter(owner=p1, controller=p1)
        spell.x_value = 2  # type: ignore[attr-defined]
        spell.on_resolve(game)

        assert game.get_battlefield(p1).get_all() == []
        assert game.get_hand(p1).contains(expensive_artifact)
        assert game.get_hand(p1).contains(nonpermanent)
        assert game.get_hand(p1).contains(drawn_one)
        assert game.get_hand(p1).contains(drawn_two)
