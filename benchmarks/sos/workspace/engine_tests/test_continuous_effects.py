"""Tests for engine/continuous_effects.py — Continuous effects and the 7-layer system.

Covers:
- Layer enum: all 7 layers with correct integer values.
- SubLayer enum: 7a–7d with correct string values.
- ContinuousEffect dataclass construction, default values, and _sort_key.
- EffectManager.add: auto-timestamp assignment, manual timestamp handling.
- EffectManager.remove: identity-based removal.
- EffectManager.remove_expired: permanent effects kept, EOT effects removed,
  turn-numbered expiry, mixed batch.
- EffectManager.apply_all: correct layer ordering, sublayer ordering for layer 7,
  timestamp ordering within same layer.
- Layer 4 (type-changing): effect changes card types.
- Layer 6 (ability granting): effect grants a keyword.
- Layer 7c (P/T modification): +2/+2 on a 2/2 → 4/4.
- Layer 7d (counters): +1/+1 counter effects applied via layer system.
- Multiple effects on same creature in correct order across layers.
- Duration-based expiry: effect expires after N turns.
- Permanent effects don't expire.
- Edge cases: no effects, already-removed effect, multiple layers combined.
- Query helpers: effects property, get_effects_for_layer, get_effects_by_source, clear.
- Duration constants: DURATION_PERMANENT and DURATION_END_OF_TURN values.
"""

from __future__ import annotations

import pytest

from engine.card import Creature
from engine.continuous_effects import (
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    ContinuousEffect,
    EffectManager,
    Layer,
    SubLayer,
)
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import CardType, Keyword


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def players() -> list[DeterministicPlayer]:
    """Create two DeterministicPlayers."""
    return [
        DeterministicPlayer("Alice", script=[]),
        DeterministicPlayer("Bob", script=[]),
    ]


@pytest.fixture()
def game(players: list[DeterministicPlayer]) -> GameState:
    """Create a GameState with two players."""
    return GameState(players)


@pytest.fixture()
def manager() -> EffectManager:
    """Create a fresh EffectManager."""
    return EffectManager()


def _make_creature(name: str = "Bear", power: int = 2, toughness: int = 2) -> Creature:
    """Create a simple creature with given stats."""
    return Creature(name=name, base_power=power, base_toughness=toughness)


# ---------------------------------------------------------------------------
# Layer enum
# ---------------------------------------------------------------------------


class TestLayerEnum:
    """Verify Layer enum members and their integer values."""

    def test_copy_layer_value(self):
        assert Layer.COPY == 1

    def test_control_layer_value(self):
        assert Layer.CONTROL == 2

    def test_text_layer_value(self):
        assert Layer.TEXT == 3

    def test_type_layer_value(self):
        assert Layer.TYPE == 4

    def test_color_layer_value(self):
        assert Layer.COLOR == 5

    def test_ability_layer_value(self):
        assert Layer.ABILITY == 6

    def test_power_toughness_layer_value(self):
        assert Layer.POWER_TOUGHNESS == 7

    def test_layer_count_is_seven(self):
        assert len(Layer) == 7

    def test_layers_are_ordered_by_value(self):
        """IntEnum values should be naturally sortable in layer order."""
        layers_sorted = sorted(Layer)
        assert layers_sorted == [
            Layer.COPY,
            Layer.CONTROL,
            Layer.TEXT,
            Layer.TYPE,
            Layer.COLOR,
            Layer.ABILITY,
            Layer.POWER_TOUGHNESS,
        ]


# ---------------------------------------------------------------------------
# SubLayer enum
# ---------------------------------------------------------------------------


class TestSubLayerEnum:
    """Verify SubLayer enum members and their string values."""

    def test_characteristic_defining_value(self):
        assert SubLayer.CHARACTERISTIC_DEFINING.value == "7a"

    def test_set_pt_value(self):
        assert SubLayer.SET_PT.value == "7b"

    def test_modify_pt_value(self):
        assert SubLayer.MODIFY_PT.value == "7c"

    def test_counters_value(self):
        assert SubLayer.COUNTERS.value == "7d"

    def test_sublayer_count_is_four(self):
        assert len(SubLayer) == 4


# ---------------------------------------------------------------------------
# Duration constants
# ---------------------------------------------------------------------------


class TestDurationConstants:
    """Verify sentinel duration constants."""

    def test_permanent_is_minus_one(self):
        assert DURATION_PERMANENT == -1

    def test_end_of_turn_is_zero(self):
        assert DURATION_END_OF_TURN == 0


# ---------------------------------------------------------------------------
# ContinuousEffect dataclass
# ---------------------------------------------------------------------------


class TestContinuousEffect:
    """Verify ContinuousEffect construction and defaults."""

    def test_construction_with_all_fields(self):
        source = object()
        applied = []
        eff = ContinuousEffect(
            source=source,
            layer=Layer.ABILITY,
            sublayer=None,
            apply=lambda g: applied.append(g),
            timestamp=5,
            duration=DURATION_PERMANENT,
        )
        assert eff.source is source
        assert eff.layer == Layer.ABILITY
        assert eff.sublayer is None
        assert eff.timestamp == 5
        assert eff.duration == DURATION_PERMANENT

    def test_default_sublayer_is_none(self):
        eff = ContinuousEffect(source="s", layer=Layer.TYPE)
        assert eff.sublayer is None

    def test_default_timestamp_is_zero(self):
        eff = ContinuousEffect(source="s", layer=Layer.TYPE)
        assert eff.timestamp == 0

    def test_default_duration_is_permanent(self):
        eff = ContinuousEffect(source="s", layer=Layer.TYPE)
        assert eff.duration == DURATION_PERMANENT

    def test_default_apply_is_noop(self):
        """Default apply callable should not raise when invoked and should be callable."""
        eff = ContinuousEffect(source="s", layer=Layer.COPY)
        result = eff.apply(None)  # Should not raise
        assert callable(eff.apply)

    def test_sort_key_layer_ordering(self):
        """Effects in different layers should sort by layer value."""
        eff_type = ContinuousEffect(source="s", layer=Layer.TYPE, timestamp=1)
        eff_ability = ContinuousEffect(source="s", layer=Layer.ABILITY, timestamp=1)
        assert eff_type._sort_key() < eff_ability._sort_key()

    def test_sort_key_sublayer_ordering(self):
        """Within layer 7, sublayers should sort 7a < 7b < 7c < 7d."""
        eff_7a = ContinuousEffect(
            source="s", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.CHARACTERISTIC_DEFINING, timestamp=1,
        )
        eff_7b = ContinuousEffect(
            source="s", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.SET_PT, timestamp=1,
        )
        eff_7c = ContinuousEffect(
            source="s", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT, timestamp=1,
        )
        eff_7d = ContinuousEffect(
            source="s", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.COUNTERS, timestamp=1,
        )
        assert eff_7a._sort_key() < eff_7b._sort_key()
        assert eff_7b._sort_key() < eff_7c._sort_key()
        assert eff_7c._sort_key() < eff_7d._sort_key()

    def test_sort_key_timestamp_ordering_within_layer(self):
        """Within the same layer, earlier timestamps sort first."""
        early = ContinuousEffect(source="s", layer=Layer.TYPE, timestamp=1)
        late = ContinuousEffect(source="s", layer=Layer.TYPE, timestamp=5)
        assert early._sort_key() < late._sort_key()


# ---------------------------------------------------------------------------
# EffectManager — add
# ---------------------------------------------------------------------------


class TestEffectManagerAdd:
    """Verify EffectManager.add behaviour."""

    def test_add_increments_effect_count(self, manager: EffectManager):
        eff = ContinuousEffect(source="s", layer=Layer.TYPE)
        manager.add(eff)
        assert len(manager) == 1

    def test_add_auto_assigns_timestamp(self, manager: EffectManager):
        eff = ContinuousEffect(source="s", layer=Layer.TYPE, timestamp=0)
        manager.add(eff)
        assert eff.timestamp >= 1

    def test_add_auto_timestamps_are_monotonically_increasing(self, manager: EffectManager):
        eff1 = ContinuousEffect(source="s", layer=Layer.TYPE)
        eff2 = ContinuousEffect(source="s", layer=Layer.TYPE)
        manager.add(eff1)
        manager.add(eff2)
        assert eff1.timestamp < eff2.timestamp

    def test_add_manual_timestamp_preserved(self, manager: EffectManager):
        eff = ContinuousEffect(source="s", layer=Layer.TYPE, timestamp=42)
        manager.add(eff)
        assert eff.timestamp == 42

    def test_add_returns_the_effect(self, manager: EffectManager):
        eff = ContinuousEffect(source="s", layer=Layer.TYPE)
        result = manager.add(eff)
        assert result is eff

    def test_add_multiple_effects(self, manager: EffectManager):
        for _ in range(5):
            manager.add(ContinuousEffect(source="s", layer=Layer.TYPE))
        assert len(manager) == 5


# ---------------------------------------------------------------------------
# EffectManager — remove
# ---------------------------------------------------------------------------


class TestEffectManagerRemove:
    """Verify EffectManager.remove behaviour."""

    def test_remove_existing_effect(self, manager: EffectManager):
        eff = ContinuousEffect(source="s", layer=Layer.TYPE)
        manager.add(eff)
        result = manager.remove(eff)
        assert result is True
        assert len(manager) == 0

    def test_remove_nonexistent_effect_returns_false(self, manager: EffectManager):
        eff = ContinuousEffect(source="s", layer=Layer.TYPE)
        result = manager.remove(eff)
        assert result is False

    def test_remove_is_identity_based(self, manager: EffectManager):
        """Two effects with identical fields are distinct if different objects."""
        eff1 = ContinuousEffect(source="s", layer=Layer.TYPE)
        eff2 = ContinuousEffect(source="s", layer=Layer.TYPE)
        manager.add(eff1)
        manager.add(eff2)
        manager.remove(eff1)
        assert len(manager) == 1
        assert manager.effects[0] is eff2


# ---------------------------------------------------------------------------
# EffectManager — remove_expired
# ---------------------------------------------------------------------------


class TestEffectManagerRemoveExpired:
    """Verify EffectManager.remove_expired behaviour."""

    def test_permanent_effects_not_removed(self, manager: EffectManager, game: GameState):
        eff = ContinuousEffect(source="s", layer=Layer.TYPE, duration=DURATION_PERMANENT)
        manager.add(eff)
        removed = manager.remove_expired(game)
        assert removed == 0
        assert len(manager) == 1

    def test_end_of_turn_effects_removed(self, manager: EffectManager, game: GameState):
        eff = ContinuousEffect(source="s", layer=Layer.TYPE, duration=DURATION_END_OF_TURN)
        manager.add(eff)
        removed = manager.remove_expired(game)
        assert removed == 1
        assert len(manager) == 0

    def test_turn_numbered_effect_not_expired_yet(self, manager: EffectManager, game: GameState):
        """Effect with duration=5 should remain when turn_number is 3."""
        game.turn_number = 3
        eff = ContinuousEffect(source="s", layer=Layer.TYPE, duration=5)
        manager.add(eff)
        removed = manager.remove_expired(game)
        assert removed == 0
        assert len(manager) == 1

    def test_turn_numbered_effect_expired(self, manager: EffectManager, game: GameState):
        """Effect with duration=3 should be removed when turn_number is 4."""
        game.turn_number = 4
        eff = ContinuousEffect(source="s", layer=Layer.TYPE, duration=3)
        manager.add(eff)
        removed = manager.remove_expired(game)
        assert removed == 1
        assert len(manager) == 0

    def test_turn_numbered_effect_exact_turn_stays(self, manager: EffectManager, game: GameState):
        """Effect with duration=3 should stay when turn_number is exactly 3."""
        game.turn_number = 3
        eff = ContinuousEffect(source="s", layer=Layer.TYPE, duration=3)
        manager.add(eff)
        removed = manager.remove_expired(game)
        assert removed == 0
        assert len(manager) == 1

    def test_mixed_batch_removal(self, manager: EffectManager, game: GameState):
        """Remove only expired effects from a mixed set."""
        game.turn_number = 5
        perm = ContinuousEffect(source="s", layer=Layer.TYPE, duration=DURATION_PERMANENT)
        eot = ContinuousEffect(source="s", layer=Layer.TYPE, duration=DURATION_END_OF_TURN)
        expired = ContinuousEffect(source="s", layer=Layer.TYPE, duration=3)
        still_active = ContinuousEffect(source="s", layer=Layer.TYPE, duration=10)
        manager.add(perm)
        manager.add(eot)
        manager.add(expired)
        manager.add(still_active)
        removed = manager.remove_expired(game)
        assert removed == 2
        assert len(manager) == 2

    def test_remove_expired_returns_count(self, manager: EffectManager, game: GameState):
        manager.add(ContinuousEffect(source="s", layer=Layer.TYPE, duration=DURATION_END_OF_TURN))
        manager.add(ContinuousEffect(source="s", layer=Layer.TYPE, duration=DURATION_END_OF_TURN))
        manager.add(ContinuousEffect(source="s", layer=Layer.TYPE, duration=DURATION_END_OF_TURN))
        removed = manager.remove_expired(game)
        assert removed == 3

    def test_remove_expired_no_effects(self, manager: EffectManager, game: GameState):
        """No effects to remove → returns 0."""
        removed = manager.remove_expired(game)
        assert removed == 0


# ---------------------------------------------------------------------------
# EffectManager — apply_all
# ---------------------------------------------------------------------------


class TestEffectManagerApplyAll:
    """Verify EffectManager.apply_all ordering and execution."""

    def test_apply_all_empty_no_error(self, manager: EffectManager, game: GameState):
        """Applying with no effects should not raise and leave effect count unchanged."""
        manager.apply_all(game)  # should not raise
        assert len(manager) == 0

    def test_apply_all_calls_each_effect(self, manager: EffectManager, game: GameState):
        calls = []
        for i in range(3):
            eff = ContinuousEffect(
                source="s", layer=Layer.TYPE,
                apply=lambda g, idx=i: calls.append(idx),
            )
            manager.add(eff)
        manager.apply_all(game)
        assert len(calls) == 3

    def test_apply_all_layer_ordering(self, manager: EffectManager, game: GameState):
        """Effects should be applied in ascending layer order."""
        order = []
        eff_ability = ContinuousEffect(
            source="s", layer=Layer.ABILITY,
            apply=lambda g: order.append("ability"),
        )
        eff_type = ContinuousEffect(
            source="s", layer=Layer.TYPE,
            apply=lambda g: order.append("type"),
        )
        eff_pt = ContinuousEffect(
            source="s", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=lambda g: order.append("pt"),
        )
        # Add in reverse order to prove sorting works
        manager.add(eff_pt)
        manager.add(eff_ability)
        manager.add(eff_type)
        manager.apply_all(game)
        assert order == ["type", "ability", "pt"]

    def test_apply_all_timestamp_ordering_within_layer(self, manager: EffectManager, game: GameState):
        """Within the same layer, earlier timestamps should be applied first."""
        order = []
        eff_late = ContinuousEffect(
            source="s", layer=Layer.ABILITY,
            apply=lambda g: order.append("late"),
        )
        eff_early = ContinuousEffect(
            source="s", layer=Layer.ABILITY,
            apply=lambda g: order.append("early"),
        )
        # Add late first, early second — but early gets earlier timestamp
        manager.add(eff_early)
        manager.add(eff_late)
        manager.apply_all(game)
        assert order == ["early", "late"]

    def test_apply_all_sublayer_ordering_within_layer_7(self, manager: EffectManager, game: GameState):
        """Within layer 7, sublayers should be applied 7a → 7b → 7c → 7d."""
        order = []
        eff_7d = ContinuousEffect(
            source="s", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.COUNTERS,
            apply=lambda g: order.append("7d"),
        )
        eff_7a = ContinuousEffect(
            source="s", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.CHARACTERISTIC_DEFINING,
            apply=lambda g: order.append("7a"),
        )
        eff_7c = ContinuousEffect(
            source="s", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=lambda g: order.append("7c"),
        )
        eff_7b = ContinuousEffect(
            source="s", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.SET_PT,
            apply=lambda g: order.append("7b"),
        )
        # Add in scrambled order
        manager.add(eff_7d)
        manager.add(eff_7a)
        manager.add(eff_7c)
        manager.add(eff_7b)
        manager.apply_all(game)
        assert order == ["7a", "7b", "7c", "7d"]

    def test_apply_all_cross_layer_and_timestamp(self, manager: EffectManager, game: GameState):
        """Effects across layers and with different timestamps sort correctly."""
        order = []
        # Layer 6, timestamp assigned second
        eff_ability2 = ContinuousEffect(
            source="s", layer=Layer.ABILITY,
            apply=lambda g: order.append("ability2"),
        )
        # Layer 4, timestamp assigned first
        eff_type = ContinuousEffect(
            source="s", layer=Layer.TYPE,
            apply=lambda g: order.append("type"),
        )
        # Layer 6, timestamp assigned first
        eff_ability1 = ContinuousEffect(
            source="s", layer=Layer.ABILITY,
            apply=lambda g: order.append("ability1"),
        )
        # Add order: type (ts=1), ability1 (ts=2), ability2 (ts=3)
        manager.add(eff_type)
        manager.add(eff_ability1)
        manager.add(eff_ability2)
        manager.apply_all(game)
        # Layer 4 first, then layer 6 in timestamp order
        assert order == ["type", "ability1", "ability2"]


# ---------------------------------------------------------------------------
# Layer 4 — Type-changing effects
# ---------------------------------------------------------------------------


class TestLayer4TypeChanging:
    """Verify type-changing effects applied in layer 4."""

    def test_add_card_type(self, manager: EffectManager, game: GameState):
        """Effect adds Artifact type to a creature."""
        creature = _make_creature()

        def add_artifact_type(g):
            creature.card_types.add(CardType.ARTIFACT)

        eff = ContinuousEffect(
            source="enchantment", layer=Layer.TYPE,
            apply=add_artifact_type,
        )
        manager.add(eff)

        assert CardType.ARTIFACT not in creature.card_types
        manager.apply_all(game)
        assert CardType.ARTIFACT in creature.card_types

    def test_remove_card_type(self, manager: EffectManager, game: GameState):
        """Effect removes creature type, leaving only other types."""
        creature = _make_creature()
        creature.card_types.add(CardType.ARTIFACT)

        def remove_creature_type(g):
            creature.card_types.discard(CardType.CREATURE)

        eff = ContinuousEffect(
            source="enchantment", layer=Layer.TYPE,
            apply=remove_creature_type,
        )
        manager.add(eff)
        manager.apply_all(game)
        assert CardType.CREATURE not in creature.card_types
        assert CardType.ARTIFACT in creature.card_types


# ---------------------------------------------------------------------------
# Layer 6 — Ability granting/removing
# ---------------------------------------------------------------------------


class TestLayer6AbilityGranting:
    """Verify ability granting/removing effects applied in layer 6."""

    def test_grant_keyword(self, manager: EffectManager, game: GameState):
        """Effect grants flying to a creature that doesn't have it."""
        creature = _make_creature()
        assert not (creature.keywords & Keyword.FLYING)

        def grant_flying(g):
            creature.keywords |= Keyword.FLYING

        eff = ContinuousEffect(
            source="enchantment", layer=Layer.ABILITY,
            apply=grant_flying,
        )
        manager.add(eff)
        manager.apply_all(game)
        assert creature.keywords & Keyword.FLYING

    def test_remove_keyword(self, manager: EffectManager, game: GameState):
        """Effect removes a keyword from a creature."""
        creature = _make_creature()
        creature.keywords |= Keyword.FLYING

        def remove_flying(g):
            creature.keywords &= ~Keyword.FLYING

        eff = ContinuousEffect(
            source="enchantment", layer=Layer.ABILITY,
            apply=remove_flying,
        )
        manager.add(eff)
        manager.apply_all(game)
        assert not (creature.keywords & Keyword.FLYING)

    def test_grant_multiple_keywords(self, manager: EffectManager, game: GameState):
        """Effect grants multiple keywords at once."""
        creature = _make_creature()

        def grant_keywords(g):
            creature.keywords |= Keyword.FLYING | Keyword.LIFELINK

        eff = ContinuousEffect(
            source="enchantment", layer=Layer.ABILITY,
            apply=grant_keywords,
        )
        manager.add(eff)
        manager.apply_all(game)
        assert creature.keywords & Keyword.FLYING
        assert creature.keywords & Keyword.LIFELINK


# ---------------------------------------------------------------------------
# Layer 7c — P/T modification (+N/+N effects)
# ---------------------------------------------------------------------------


class TestLayer7cPTModification:
    """Verify P/T modification effects in sublayer 7c."""

    def test_plus_two_plus_two_on_two_two(self, manager: EffectManager, game: GameState):
        """The canonical test: +2/+2 on a 2/2 creature → reads as 4/4."""
        creature = _make_creature(power=2, toughness=2)

        def buff(g):
            creature.modified_power += 2
            creature.modified_toughness += 2

        eff = ContinuousEffect(
            source="giant_growth", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=buff,
        )
        manager.add(eff)
        manager.apply_all(game)
        assert creature.power == 4
        assert creature.toughness == 4

    def test_negative_modification(self, manager: EffectManager, game: GameState):
        """A -1/-1 effect on a 3/3 → 2/2."""
        creature = _make_creature(power=3, toughness=3)

        def debuff(g):
            creature.modified_power -= 1
            creature.modified_toughness -= 1

        eff = ContinuousEffect(
            source="weakness", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=debuff,
        )
        manager.add(eff)
        manager.apply_all(game)
        assert creature.power == 2
        assert creature.toughness == 2

    def test_multiple_pt_modifications_stack(self, manager: EffectManager, game: GameState):
        """Two +1/+1 effects on a 2/2 → 4/4."""
        creature = _make_creature(power=2, toughness=2)

        def buff_one(g):
            creature.modified_power += 1
            creature.modified_toughness += 1

        def buff_two(g):
            creature.modified_power += 1
            creature.modified_toughness += 1

        eff1 = ContinuousEffect(
            source="s1", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT, apply=buff_one,
        )
        eff2 = ContinuousEffect(
            source="s2", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT, apply=buff_two,
        )
        manager.add(eff1)
        manager.add(eff2)
        manager.apply_all(game)
        assert creature.power == 4
        assert creature.toughness == 4


# ---------------------------------------------------------------------------
# Layer 7d — Counter-based P/T
# ---------------------------------------------------------------------------


class TestLayer7dCounters:
    """Verify counter effects in sublayer 7d."""

    def test_plus_one_counters_applied(self, manager: EffectManager, game: GameState):
        """Effect that applies +1/+1 counters to creature P/T."""
        creature = _make_creature(power=2, toughness=2)

        def apply_counters(g):
            creature.plus_one_counters += 2

        eff = ContinuousEffect(
            source="counter_source", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.COUNTERS,
            apply=apply_counters,
        )
        manager.add(eff)
        manager.apply_all(game)
        # power property = base_power + plus_one_counters - minus_one_counters
        assert creature.power == 4
        assert creature.toughness == 4

    def test_minus_one_counters_applied(self, manager: EffectManager, game: GameState):
        """Effect that applies -1/-1 counters to creature P/T."""
        creature = _make_creature(power=3, toughness=3)

        def apply_minus_counters(g):
            creature.minus_one_counters += 1

        eff = ContinuousEffect(
            source="wither", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.COUNTERS,
            apply=apply_minus_counters,
        )
        manager.add(eff)
        manager.apply_all(game)
        assert creature.power == 2
        assert creature.toughness == 2


# ---------------------------------------------------------------------------
# Multi-layer ordering: type + ability + P/T on same creature
# ---------------------------------------------------------------------------


class TestMultiLayerEffects:
    """Verify correct ordering when multiple layers affect the same creature."""

    def test_type_then_ability_then_pt(self, manager: EffectManager, game: GameState):
        """Type-changing (L4), ability grant (L6), and P/T mod (L7c) in order."""
        creature = _make_creature(power=1, toughness=1)
        order = []

        def change_type(g):
            creature.card_types.add(CardType.ARTIFACT)
            order.append("type")

        def grant_ability(g):
            creature.keywords |= Keyword.FLYING
            order.append("ability")

        def buff_pt(g):
            creature.modified_power += 2
            creature.modified_toughness += 2
            order.append("pt")

        # Add in scrambled order
        manager.add(ContinuousEffect(
            source="s", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT, apply=buff_pt,
        ))
        manager.add(ContinuousEffect(
            source="s", layer=Layer.TYPE, apply=change_type,
        ))
        manager.add(ContinuousEffect(
            source="s", layer=Layer.ABILITY, apply=grant_ability,
        ))

        manager.apply_all(game)

        # Verify order: type (4), ability (6), pt (7)
        assert order == ["type", "ability", "pt"]
        # Verify final state
        assert CardType.ARTIFACT in creature.card_types
        assert creature.keywords & Keyword.FLYING
        assert creature.power == 3
        assert creature.toughness == 3

    def test_layer_7c_before_7d(self, manager: EffectManager, game: GameState):
        """Within layer 7, 7c (modify P/T) applied before 7d (counters)."""
        creature = _make_creature(power=2, toughness=2)
        order = []

        def modify_pt(g):
            creature.modified_power += 1
            creature.modified_toughness += 1
            order.append("7c")

        def apply_counters(g):
            creature.plus_one_counters += 1
            order.append("7d")

        manager.add(ContinuousEffect(
            source="s", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.COUNTERS, apply=apply_counters,
        ))
        manager.add(ContinuousEffect(
            source="s", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT, apply=modify_pt,
        ))
        manager.apply_all(game)
        assert order == ["7c", "7d"]
        # base_power=3, plus_one_counters=1 → power=4
        assert creature.power == 4
        assert creature.toughness == 4


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


class TestEffectManagerQueryHelpers:
    """Verify query helper methods on EffectManager."""

    def test_effects_returns_shallow_copy(self, manager: EffectManager):
        eff = ContinuousEffect(source="s", layer=Layer.TYPE)
        manager.add(eff)
        effects = manager.effects
        assert effects == [eff]
        # Mutating the copy should not affect internal list
        effects.clear()
        assert len(manager) == 1

    def test_get_effects_for_layer(self, manager: EffectManager):
        eff_type = ContinuousEffect(source="s", layer=Layer.TYPE)
        eff_ability = ContinuousEffect(source="s", layer=Layer.ABILITY)
        manager.add(eff_type)
        manager.add(eff_ability)
        layer4_effects = manager.get_effects_for_layer(Layer.TYPE)
        assert len(layer4_effects) == 1
        assert layer4_effects[0] is eff_type

    def test_get_effects_by_source(self, manager: EffectManager):
        source_a = object()
        source_b = object()
        eff_a = ContinuousEffect(source=source_a, layer=Layer.TYPE)
        eff_b = ContinuousEffect(source=source_b, layer=Layer.TYPE)
        manager.add(eff_a)
        manager.add(eff_b)
        result = manager.get_effects_by_source(source_a)
        assert len(result) == 1
        assert result[0] is eff_a

    def test_clear_removes_all(self, manager: EffectManager):
        for _ in range(3):
            manager.add(ContinuousEffect(source="s", layer=Layer.TYPE))
        manager.clear()
        assert len(manager) == 0

    def test_len_reflects_current_count(self, manager: EffectManager):
        assert len(manager) == 0
        manager.add(ContinuousEffect(source="s", layer=Layer.TYPE))
        assert len(manager) == 1


# ---------------------------------------------------------------------------
# GameState integration
# ---------------------------------------------------------------------------


class TestGameStateIntegration:
    """Verify that GameState has an EffectManager wired in."""

    def test_game_state_has_effect_manager(self, game: GameState):
        assert hasattr(game, "effect_manager")
        assert isinstance(game.effect_manager, EffectManager)

    def test_effect_manager_starts_empty(self, game: GameState):
        assert len(game.effect_manager) == 0

    def test_add_effect_to_game_effect_manager(self, game: GameState):
        eff = ContinuousEffect(source="s", layer=Layer.TYPE)
        game.effect_manager.add(eff)
        assert len(game.effect_manager) == 1

    def test_apply_all_through_game_effect_manager(self, game: GameState):
        """Full integration: add effect via game.effect_manager, apply_all, verify."""
        creature = _make_creature(power=2, toughness=2)

        def buff(g):
            creature.modified_power += 2
            creature.modified_toughness += 2

        eff = ContinuousEffect(
            source="aura", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT, apply=buff,
        )
        game.effect_manager.add(eff)
        game.effect_manager.apply_all(game)
        assert creature.power == 4
        assert creature.toughness == 4


# ---------------------------------------------------------------------------
# Duration-based end-to-end scenarios
# ---------------------------------------------------------------------------


class TestDurationScenarios:
    """End-to-end tests for duration-based effect expiry."""

    def test_eot_effect_applies_then_expires(self, manager: EffectManager, game: GameState):
        """EOT effect: applies during apply_all, then removed on cleanup."""
        creature = _make_creature(power=2, toughness=2)

        def buff(g):
            creature.modified_power += 3
            creature.modified_toughness += 3

        eff = ContinuousEffect(
            source="giant_growth", layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT, apply=buff,
            duration=DURATION_END_OF_TURN,
        )
        manager.add(eff)
        # Apply effects — buff should be active
        manager.apply_all(game)
        assert creature.power == 5

        # Simulate cleanup: remove expired
        removed = manager.remove_expired(game)
        assert removed == 1
        assert len(manager) == 0

    def test_turn_numbered_effect_stays_until_expiry(self, manager: EffectManager, game: GameState):
        """Effect with duration=3 stays on turns 1-3, removed on turn 4."""
        eff = ContinuousEffect(source="s", layer=Layer.TYPE, duration=3)
        manager.add(eff)

        game.turn_number = 1
        assert manager.remove_expired(game) == 0

        game.turn_number = 3
        assert manager.remove_expired(game) == 0
        assert len(manager) == 1

        game.turn_number = 4
        assert manager.remove_expired(game) == 1
        assert len(manager) == 0

    def test_permanent_effect_survives_many_turns(self, manager: EffectManager, game: GameState):
        """Permanent effect is never removed by remove_expired."""
        eff = ContinuousEffect(source="s", layer=Layer.TYPE, duration=DURATION_PERMANENT)
        manager.add(eff)

        for turn in range(1, 20):
            game.turn_number = turn
            manager.remove_expired(game)

        assert len(manager) == 1
