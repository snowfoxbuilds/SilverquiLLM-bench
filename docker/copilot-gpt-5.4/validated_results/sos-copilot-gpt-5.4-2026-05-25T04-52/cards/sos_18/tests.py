"""Tests for SOS 18 — Harsh Annotation."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_18.card_impl import HarshAnnotation
from benchmarks.sos.workspace.engine.card import Creature, Instant, Planeswalker
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestHarshAnnotationProperties:
    """Static card data should match the SOS 18 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(HarshAnnotation(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = HarshAnnotation(owner=None)
        assert card.name == "Harsh Annotation"
        assert card.mana_cost == ManaCost.parse("{1}{W}")


class TestHarshAnnotationTargeting:
    """Harsh Annotation should target a creature on the battlefield."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = HarshAnnotation(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_rejects_noncreatures(self) -> None:
        game = create_game()
        req = HarshAnnotation(owner=None).get_targets(game)[0]

        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        non_creature = Planeswalker(name="Visitor", starting_loyalty=3)

        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_creature) is False


class TestHarshAnnotationResolution:
    """Harsh Annotation should destroy the target and replace it with an Inkling."""

    def test_destroys_target_creature_and_creates_an_inkling_for_its_controller(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Marked Creature",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
        )
        spell = HarshAnnotation(owner=p1, controller=p1)
        game.get_battlefield(p2).add(target)
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert game.get_battlefield(p2).contains(target) is False
        assert game.get_graveyard(p2).contains(target) is True

        tokens = game.get_battlefield(p2).get_all()
        assert len(tokens) == 1

        token = tokens[0]
        assert isinstance(token, Creature)
        assert token.is_token is True
        assert token.power == 1
        assert token.toughness == 1
        assert "Inkling" in token.subtypes
        assert Keyword.FLYING in token.keywords
        assert get_colors(token) == {Color.WHITE, Color.BLACK}

    def test_target_that_is_no_longer_on_the_battlefield_creates_no_token(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Missing Creature",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        spell = HarshAnnotation(owner=p1, controller=p1)

        set_board_state(game, 1, graveyard=[target])
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert game.get_graveyard(p2).contains(target) is True
        assert game.get_battlefield(p1).get_all() == []
        assert game.get_battlefield(p2).get_all() == []

