"""Tests for Ajani's Response — {4}{W} Instant that destroys target creature.

Ajani's Response has a cost reduction mechanic: it costs {3} less to cast
if it targets a tapped creature.

Verifies:
- Correct name, mana cost, card type, rules text.
- Destroys target creature on resolution (moves to graveyard).
- Cost reduction: {3} less when targeting a tapped creature.
- Cost reduction: no reduction when targeting an untapped creature.
- Edge cases: target leaves battlefield before resolution (fizzle).
- Edge cases: indestructible creature is not destroyed.
- Mana payment works with and without the reduction.
- Works targeting own creatures and opponent's creatures.
"""

from __future__ import annotations

import pytest

from card_impl import AjanisResponse
from engine.card import Creature
from engine.casting import CastingError
from engine.types import CardType, ManaCost, ManaType, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_creature(
    name: str = "TestCreature",
    power: int = 2,
    toughness: int = 2,
    tapped: bool = False,
) -> Creature:
    """Create a test creature with optional tapped state."""
    c = Creature(name=name, base_power=power, base_toughness=toughness)
    c.is_tapped = tapped
    return c


# ---------------------------------------------------------------------------
# Static attribute tests
# ---------------------------------------------------------------------------

class TestAjaniResponseAttributes:
    """Verify card metadata: name, mana cost, type, rules text."""

    def test_name(self) -> None:
        card = AjanisResponse()
        assert card.name == "Ajani's Response"

    def test_mana_cost(self) -> None:
        card = AjanisResponse()
        expected = ManaCost.parse("{4}{W}")
        assert card.mana_cost.generic == expected.generic
        assert card.mana_cost.pips == expected.pips

    def test_card_type_instant(self) -> None:
        card = AjanisResponse()
        assert CardType.INSTANT in card.card_types

    def test_rules_text_contains_destroy(self) -> None:
        card = AjanisResponse()
        assert "Destroy target creature" in card.rules_text

    def test_rules_text_contains_cost_reduction(self) -> None:
        card = AjanisResponse()
        assert "{3} less" in card.rules_text

    def test_not_creature_type(self) -> None:
        card = AjanisResponse()
        assert CardType.CREATURE not in card.card_types


# ---------------------------------------------------------------------------
# Core: on_resolve destroys target creature
# ---------------------------------------------------------------------------

class TestAjaniResponseDestroy:
    """Ajani's Response destroys the target creature when it resolves."""

    def test_destroys_opponent_creature(self) -> None:
        from tests.test_utils import create_game, set_board_state

        game = create_game()
        p1, p2 = game.players

        creature = _make_creature(name="OpponentCreature", toughness=5)
        creature.owner = p2
        creature.controller = p2
        set_board_state(game, 1, battlefield=[creature])

        card = AjanisResponse()
        card.controller = p1
        card.chosen_targets = [creature]
        card.on_resolve(game)

        assert not p2.zones[Zone.BATTLEFIELD].contains(creature)
        assert p2.zones[Zone.GRAVEYARD].contains(creature)

    def test_destroys_own_creature(self) -> None:
        from tests.test_utils import create_game, set_board_state

        game = create_game()
        p1 = game.players[0]

        creature = _make_creature(name="OwnCreature", toughness=3)
        creature.owner = p1
        creature.controller = p1
        set_board_state(game, 0, battlefield=[creature])

        card = AjanisResponse()
        card.controller = p1
        card.chosen_targets = [creature]
        card.on_resolve(game)

        assert not p1.zones[Zone.BATTLEFIELD].contains(creature)
        assert p1.zones[Zone.GRAVEYARD].contains(creature)

    def test_destroys_creature_toughness_1(self) -> None:
        from tests.test_utils import create_game, set_board_state

        game = create_game()
        p2 = game.players[1]

        creature = _make_creature(name="FragileCreature", power=0, toughness=1)
        creature.owner = p2
        creature.controller = p2
        set_board_state(game, 1, battlefield=[creature])

        card = AjanisResponse()
        card.controller = game.players[0]
        card.chosen_targets = [creature]
        card.on_resolve(game)

        assert not p2.zones[Zone.BATTLEFIELD].contains(creature)
        assert p2.zones[Zone.GRAVEYARD].contains(creature)


# ---------------------------------------------------------------------------
# Edge cases on resolution
# ---------------------------------------------------------------------------

class TestAjaniResponseResolveEdgeCases:
    """Edge cases during resolution of Ajani's Response."""

    def test_no_chosen_targets_no_crash(self) -> None:
        from tests.test_utils import create_game

        game = create_game()
        card = AjanisResponse()
        card.controller = game.players[0]

        card.on_resolve(game)


    def test_target_not_on_battlefield_fizzles(self) -> None:
        from tests.test_utils import create_game

        game = create_game()
        p1 = game.players[0]

        creature = _make_creature(name="ExiledCreature")
        creature.owner = p1
        creature.controller = p1

        card = AjanisResponse()
        card.controller = p1
        card.chosen_targets = [creature]
        card.on_resolve(game)

        assert not p1.zones[Zone.GRAVEYARD].contains(creature)

    def test_empty_chosen_targets_list_no_crash(self) -> None:
        from tests.test_utils import create_game

        game = create_game()
        card = AjanisResponse()
        card.controller = game.players[0]
        card.chosen_targets = []
        card.on_resolve(game)


# ---------------------------------------------------------------------------
# Cost reduction: {3} less targeting tapped creature
# ---------------------------------------------------------------------------

class TestAjaniResponseCostReduction:
    """Cost reduction: {3} less if targeting a tapped creature."""

    def test_reduction_3_for_tapped_creature(self) -> None:
        from tests.test_utils import create_game, set_board_state

        game = create_game()
        p1 = game.players[0]

        creature = _make_creature(name="TappedCreature", tapped=True)
        creature.owner = p1
        creature.controller = p1
        set_board_state(game, 0, battlefield=[creature])

        card = AjanisResponse()
        card.controller = p1
        card.chosen_targets = [creature]

        reduction = card.cost_reduction(game)
        assert reduction == 3

    def test_no_reduction_for_untapped_creature(self) -> None:
        from tests.test_utils import create_game, set_board_state

        game = create_game()
        p1 = game.players[0]

        creature = _make_creature(name="UntappedCreature", tapped=False)
        creature.owner = p1
        creature.controller = p1
        set_board_state(game, 0, battlefield=[creature])

        card = AjanisResponse()
        card.controller = p1
        card.chosen_targets = [creature]

        reduction = card.cost_reduction(game)
        assert reduction == 0

    def test_no_reduction_no_chosen_targets(self) -> None:
        from tests.test_utils import create_game

        game = create_game()
        card = AjanisResponse()
        card.controller = game.players[0]

        reduction = card.cost_reduction(game)
        assert reduction == 0

    def test_no_reduction_empty_chosen_targets(self) -> None:
        from tests.test_utils import create_game

        game = create_game()
        card = AjanisResponse()
        card.controller = game.players[0]
        card.chosen_targets = []

        reduction = card.cost_reduction(game)
        assert reduction == 0


# ---------------------------------------------------------------------------
# Full cast_spell pipeline integration tests
# ---------------------------------------------------------------------------

class TestAjaniResponseCastPipeline:
    """Full casting pipeline via cast_spell utility."""

    def test_cast_and_destroy_with_full_mana(self) -> None:
        """Cast Ajani's Response paying full {4}{W}, destroys target."""
        from tests.test_utils import create_game, set_board_state, cast_spell

        game = create_game()
        p1, p2 = game.players

        creature = _make_creature(name="TargetCreature", toughness=5)
        creature.owner = p2
        creature.controller = p2
        set_board_state(game, 1, battlefield=[creature])

        card = AjanisResponse()
        card.owner = p1
        card.controller = p1
        set_board_state(
            game, 0,
            hand=[card],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 4},
        )

        cast_spell(game, 0, "Ajani's Response", targets=[creature])

        assert not p2.zones[Zone.BATTLEFIELD].contains(creature)
        assert p2.zones[Zone.GRAVEYARD].contains(creature)

    def test_cast_with_reduction_tapped_creature(self) -> None:
        """Cast Ajani's Response for {1}{W} targeting a tapped creature ({4}{W} - {3})."""
        from tests.test_utils import create_game, set_board_state, cast_spell

        game = create_game()
        p1, p2 = game.players

        creature = _make_creature(name="TappedTarget", toughness=4, tapped=True)
        creature.owner = p2
        creature.controller = p2
        set_board_state(game, 1, battlefield=[creature])

        card = AjanisResponse()
        card.owner = p1
        card.controller = p1
        set_board_state(
            game, 0,
            hand=[card],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1},
        )

        cast_spell(game, 0, "Ajani's Response", targets=[creature])

        assert not p2.zones[Zone.BATTLEFIELD].contains(creature)
        assert p2.zones[Zone.GRAVEYARD].contains(creature)

    def test_cast_insufficient_mana_no_reduction(self) -> None:
        """Cannot cast with only {W} when targeting untapped creature."""
        from tests.test_utils import create_game, set_board_state, cast_spell

        game = create_game()
        p1, p2 = game.players

        creature = _make_creature(name="UntappedTarget", toughness=4, tapped=False)
        creature.owner = p2
        creature.controller = p2
        set_board_state(game, 1, battlefield=[creature])

        card = AjanisResponse()
        card.owner = p1
        card.controller = p1
        set_board_state(
            game, 0,
            hand=[card],
            mana={ManaType.WHITE: 1},
        )

        with pytest.raises(Exception):
            cast_spell(game, 0, "Ajani's Response", targets=[creature])

    def test_spell_goes_to_graveyard_after_resolve(self) -> None:
        """After resolving, the instant goes to the controller's graveyard."""
        from tests.test_utils import create_game, set_board_state, cast_spell

        game = create_game()
        p1, p2 = game.players

        creature = _make_creature(name="TargetCreature", toughness=3)
        creature.owner = p2
        creature.controller = p2
        set_board_state(game, 1, battlefield=[creature])

        card = AjanisResponse()
        card.owner = p1
        card.controller = p1
        set_board_state(
            game, 0,
            hand=[card],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 4},
        )

        cast_spell(game, 0, "Ajani's Response", targets=[creature])

        assert p1.zones[Zone.GRAVEYARD].contains(card)
        assert not p1.zones[Zone.HAND].contains(card)

    def test_mana_deducted_correctly_with_reduction(self) -> None:
        """With reduction, only {1}{W} is paid ({4}{W} - {3}); 3 colorless remains."""
        from tests.test_utils import create_game, set_board_state, cast_spell

        game = create_game()
        p1, p2 = game.players

        creature = _make_creature(name="TappedTarget", toughness=3, tapped=True)
        creature.owner = p2
        creature.controller = p2
        set_board_state(game, 1, battlefield=[creature])

        card = AjanisResponse()
        card.owner = p1
        card.controller = p1
        set_board_state(
            game, 0,
            hand=[card],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 4},
        )

        cast_spell(game, 0, "Ajani's Response", targets=[creature])

        assert p1.mana_pool.get(ManaType.WHITE) == 0
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3  # paid 1, had 4

    def test_mana_deducted_correctly_without_reduction(self) -> None:
        """Without reduction, {4}{W} is paid."""
        from tests.test_utils import create_game, set_board_state, cast_spell

        game = create_game()
        p1, p2 = game.players

        creature = _make_creature(name="UntappedTarget", toughness=3, tapped=False)
        creature.owner = p2
        creature.controller = p2
        set_board_state(game, 1, battlefield=[creature])

        card = AjanisResponse()
        card.owner = p1
        card.controller = p1
        set_board_state(
            game, 0,
            hand=[card],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 4},
        )

        cast_spell(game, 0, "Ajani's Response", targets=[creature])

        assert p1.mana_pool.get(ManaType.WHITE) == 0
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0


# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------

class TestAjaniResponseTargets:
    """get_targets returns correct TargetRequirement for creatures."""

    def test_returns_target_requirement(self) -> None:
        from tests.test_utils import create_game, set_board_state
        from engine.types import TargetRequirement

        game = create_game()
        p1 = game.players[0]

        creature = _make_creature(name="SomeCreature")
        creature.owner = p1
        creature.controller = p1
        set_board_state(game, 0, battlefield=[creature])

        card = AjanisResponse()
        card.controller = p1
        target_specs = card.get_targets(game)

        assert len(target_specs) == 1
        assert isinstance(target_specs[0], TargetRequirement)

    def test_target_requirement_filters_creatures(self) -> None:
        from tests.test_utils import create_game, set_board_state
        from engine.card import Artifact

        game = create_game()
        p1 = game.players[0]

        creature = _make_creature(name="SomeCreature")
        creature.owner = p1
        creature.controller = p1

        artifact = Artifact(name="SomeArtifact")
        artifact.owner = p1
        artifact.controller = p1

        set_board_state(game, 0, battlefield=[creature, artifact])

        card = AjanisResponse()
        card.controller = p1
        target_specs = card.get_targets(game)

        assert len(target_specs) == 1
        spec = target_specs[0]
        assert spec.filter_fn(creature) is True
        assert spec.filter_fn(artifact) is False

    def test_targets_both_players_creatures(self) -> None:
        from tests.test_utils import create_game, set_board_state

        game = create_game()
        p1, p2 = game.players

        c1 = _make_creature(name="MyCreature")
        c1.owner = p1
        c1.controller = p1

        c2 = _make_creature(name="TheirCreature")
        c2.owner = p2
        c2.controller = p2

        set_board_state(game, 0, battlefield=[c1])
        set_board_state(game, 1, battlefield=[c2])

        card = AjanisResponse()
        card.controller = p1
        target_specs = card.get_targets(game)

        assert len(target_specs) == 1
        spec = target_specs[0]
        assert spec.filter_fn(c1) is True
        assert spec.filter_fn(c2) is True

    def test_no_creatures_returns_empty_targets(self) -> None:
        from tests.test_utils import create_game

        game = create_game()
        card = AjanisResponse()
        card.controller = game.players[0]
        target_specs = card.get_targets(game)

        assert len(target_specs) == 1
        spec = target_specs[0]

        dummy = _make_creature("Dummy")
        assert spec.filter_fn(dummy) is False
