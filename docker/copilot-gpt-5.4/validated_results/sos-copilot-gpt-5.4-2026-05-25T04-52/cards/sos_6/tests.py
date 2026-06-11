"""Tests for SOS 6 — Ajani's Response."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_6.card_impl import AjanisResponse
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import (
    TestSetupError as CastSetupError,
    cast_spell,
    create_game,
    set_board_state,
)


class TestAjanisResponseProperties:
    """Static card data should match the SOS 6 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(AjanisResponse(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = AjanisResponse(owner=None)
        assert card.name == "Ajani's Response"
        assert card.mana_cost == ManaCost.parse("{4}{W}")


class TestAjanisResponseTargeting:
    """The spell should target a creature on the battlefield."""

    def test_returns_single_battlefield_creature_target_requirement(self) -> None:
        game = create_game()
        reqs = AjanisResponse(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_rejects_noncreatures(self) -> None:
        game = create_game()
        req = AjanisResponse(owner=None).get_targets(game)[0]

        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        non_creature = CardImpl(name="Mysterious Relic")

        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_creature) is False


class TestAjanisResponseResolutionAndCostReduction:
    """The spell should destroy its target and apply the tapped-target discount."""

    def test_on_resolve_destroys_the_chosen_target_creature(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Opponent Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 1, battlefield=[target])

        spell = AjanisResponse(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert not game.get_battlefield(p2).contains(target)
        assert game.get_graveyard(p2).contains(target)

    def test_cast_uses_reduced_cost_when_target_is_tapped(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Tapped Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        target.is_tapped = True
        spell = AjanisResponse(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.WHITE: 2},
        )
        set_board_state(game, 1, battlefield=[target])

        cast_spell(game, 0, "Ajani's Response", targets=[target])

        assert not game.get_battlefield(p2).contains(target)
        assert game.get_graveyard(p2).contains(target)
        assert game.get_graveyard(p1).contains(spell)

    def test_cast_without_tapped_target_reduction_still_requires_full_cost(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Untapped Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        spell = AjanisResponse(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.WHITE: 2},
        )
        set_board_state(game, 1, battlefield=[target])

        with pytest.raises(CastSetupError):
            cast_spell(game, 0, "Ajani's Response", targets=[target])
