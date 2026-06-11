"""Tests for SOS 41 — Chase Inspiration."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_41.card_impl import ChaseInspiration
from benchmarks.sos.workspace.engine.casting import CastingError, cast_spell as cast_spell_paid
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class CreatureTargetingTestInstant(Instant):
    """Simple instant used to exercise hexproof target legality."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Creature Targeting Test Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        super().__init__(**kwargs)

    def get_targets(self, game: object) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]


class TestChaseInspirationProperties:
    """Static card data should match the SOS 41 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(ChaseInspiration(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = ChaseInspiration(owner=None)
        assert card.name == "Chase Inspiration"
        assert card.mana_cost == ManaCost.parse("{U}")


class TestChaseInspirationTargeting:
    """Chase Inspiration should target a creature you control."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = ChaseInspiration(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_only_a_creature_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        req = ChaseInspiration(owner=p1, controller=p1).get_targets(game)[0]

        friendly_creature = Creature(
            name="Helpful Student",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opposing_creature = Creature(
            name="Opposing Student",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        non_creature = CardImpl(name="Campus Notes", owner=p1, controller=p1)

        assert req.filter_fn(friendly_creature) is True
        assert req.filter_fn(opposing_creature) is False
        assert req.filter_fn(non_creature) is False


class TestChaseInspirationResolution:
    """Chase Inspiration should grant toughness and hexproof until end of turn."""

    def test_target_gets_plus_zero_plus_three_and_hexproof(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Thoughtful Adept",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p1).add(target)
        card = ChaseInspiration(owner=p1, controller=p1)
        card.chosen_targets = [target]

        card.on_resolve(game)

        assert target.power == 2
        assert target.toughness == 5
        assert Keyword.HEXPROOF in target.keywords

    def test_granted_bonus_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Thoughtful Adept",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p1).add(target)
        card = ChaseInspiration(owner=p1, controller=p1)
        card.chosen_targets = [target]

        card.on_resolve(game)
        assert target.toughness == 5
        assert Keyword.HEXPROOF in target.keywords

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert target.power == 2
        assert target.toughness == 2
        assert Keyword.HEXPROOF not in target.keywords

    def test_opponents_cannot_cast_targeting_spells_at_creature_with_granted_hexproof(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Thoughtful Adept",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        hostile_spell = CreatureTargetingTestInstant(owner=p2, controller=p2)
        chase_inspiration = ChaseInspiration(owner=p1, controller=p1)
        chase_inspiration.chosen_targets = [target]

        set_board_state(game, 0, battlefield=[target])
        set_board_state(game, 1, hand=[hostile_spell], mana={ManaType.WHITE: 1})

        chase_inspiration.on_resolve(game)
        p2._script.append(target)

        with pytest.raises(CastingError, match="target has hexproof"):
            cast_spell_paid(game, p2, hostile_spell)

        assert game.get_hand(p2).contains(hostile_spell)
        assert game.stack.is_empty()

    def test_no_target_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Thoughtful Adept",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p1).add(target)

        ChaseInspiration(owner=p1, controller=p1).on_resolve(game)

        assert target.power == 2
        assert target.toughness == 2
        assert Keyword.HEXPROOF not in target.keywords
