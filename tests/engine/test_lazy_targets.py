"""Tests for lazy target filter evaluation (TODO item 14).

Verifies that ``get_targets()`` filter functions evaluate object
properties at call time (lazy), not at the time the filter was created
(snapshot).  This prevents stale target lists when game state changes
between filter creation and filter evaluation.
"""

from __future__ import annotations

from typing import Any

import pytest

from engine.card import Creature, Instant
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game() -> GameState:
    """Create a minimal 2-player GameState."""
    p1 = DeterministicPlayer("Alice", [])
    p2 = DeterministicPlayer("Bob", [])
    game = GameState([p1, p2])
    return game


def _make_creature(
    name: str = "Bear",
    power: int = 2,
    toughness: int = 2,
    **kwargs: Any,
) -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse("{1}{G}"),
        base_power=power,
        base_toughness=toughness,
        **kwargs,
    )


class _CreatureTargetSpell(Instant):
    """A test spell that targets a creature on the battlefield using lazy filter."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Test Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list[Any]:
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLazyTargetFilter:
    """filter_fn should evaluate properties at call time, not snapshot time."""

    def test_filter_sees_creature_added_after_creation(self) -> None:
        """A creature added to the battlefield after get_targets() should
        still pass the filter if it satisfies the property check."""
        game = _make_game()
        p1, p2 = game.players

        # No creatures on battlefield when filter is created
        spell = _CreatureTargetSpell(owner=p1, controller=p1)
        target_reqs = spell.get_targets(game)
        assert len(target_reqs) == 1
        filter_fn = target_reqs[0].filter_fn

        # Now add a creature — lazy filter should accept it
        new_creature = _make_creature(name="Late Bear", owner=p2, controller=p2)
        game.get_battlefield(p2).add(new_creature)

        assert filter_fn(new_creature) is True

    def test_filter_rejects_non_creature_regardless_of_timing(self) -> None:
        """A non-creature object should fail the filter even if the filter
        was created before any game state changes."""
        game = _make_game()
        p1 = game.players[0]

        spell = _CreatureTargetSpell(owner=p1, controller=p1)
        target_reqs = spell.get_targets(game)
        filter_fn = target_reqs[0].filter_fn

        from engine.card import Artifact
        artifact = Artifact(name="Artifact", owner=p1, controller=p1)
        assert filter_fn(artifact) is False

    def test_keyword_based_filter_sees_updated_keywords(self) -> None:
        """If a creature gains/loses flying after filter creation, the
        filter should see the updated keywords."""
        from cards.fdn.fdn_214.card_impl import BrokenWings

        game = _make_game()
        p1, p2 = game.players

        creature = _make_creature(name="Bird", owner=p2, controller=p2)
        creature.keywords = Keyword.FLYING
        game.get_battlefield(p2).add(creature)

        spell = BrokenWings(owner=p1, controller=p1)
        target_reqs = spell.get_targets(game)
        # Find the filter
        filter_fn = target_reqs[0].filter_fn

        # Flying creature passes
        assert filter_fn(creature) is True

        # Remove flying — lazy filter should see the change
        creature.keywords = Keyword(0)
        assert filter_fn(creature) is False

    def test_power_based_filter_sees_updated_power(self) -> None:
        """If a creature's power changes after filter creation, the
        filter should see the updated power."""
        from cards.fdn.fdn_143.card_impl import MakeYourMove

        game = _make_game()
        p1, p2 = game.players

        creature = _make_creature(name="Pumped", owner=p2, controller=p2, power=3, toughness=3)
        game.get_battlefield(p2).add(creature)

        spell = MakeYourMove(owner=p1, controller=p1)
        target_reqs = spell.get_targets(game)
        filter_fn = target_reqs[0].filter_fn

        # Power 3 — not a valid target for MakeYourMove (needs >= 4 or artifact/enchantment)
        assert filter_fn(creature) is False

        # Pump power to 4 — should now pass
        creature.base_power = 4
        assert filter_fn(creature) is True

    def test_controller_based_filter_sees_controller_change(self) -> None:
        """BanishingLight targets 'nonland permanent an opponent controls'.
        If control of a permanent changes after filter creation, the filter
        should reflect the new controller."""
        from cards.fdn.fdn_138.card_impl import BanishingLight

        game = _make_game()
        p1, p2 = game.players

        creature = _make_creature(name="Stolen Bear", owner=p2, controller=p2)
        game.get_battlefield(p2).add(creature)

        spell = BanishingLight(owner=p1, controller=p1)
        target_reqs = spell.get_targets(game)
        assert len(target_reqs) == 1
        filter_fn = target_reqs[0].filter_fn

        # Creature controlled by opponent — valid target
        assert filter_fn(creature) is True

        # Transfer control to p1 — no longer an opponent's permanent
        creature.controller = p1
        assert filter_fn(creature) is False

    def test_toughness_change_after_filter_creation(self) -> None:
        """A creature whose toughness changes after filter creation should
        be evaluated with the current toughness value."""
        game = _make_game()
        p1, p2 = game.players

        creature = _make_creature(name="Fragile", owner=p2, controller=p2, power=1, toughness=1)
        game.get_battlefield(p2).add(creature)

        # Create a filter that checks toughness <= 2 (lazy)
        req = TargetRequirement(
            filter_fn=lambda obj: (
                CardType.CREATURE in getattr(obj, "card_types", set())
                and getattr(obj, "base_toughness", 0) <= 2
            ),
            description="creature with toughness 2 or less",
            zone=Zone.BATTLEFIELD,
        )
        filter_fn = req.filter_fn

        assert filter_fn(creature) is True

        # Pump toughness above threshold
        creature.base_toughness = 5
        assert filter_fn(creature) is False

    def test_filter_evaluates_current_card_types(self) -> None:
        """If a card gains or loses card types after filter creation,
        the lazy filter should see the updated card_types set."""
        game = _make_game()
        p1 = game.players[0]

        creature = _make_creature(name="Morphing", owner=p1, controller=p1)
        game.get_battlefield(p1).add(creature)

        spell = _CreatureTargetSpell(owner=p1, controller=p1)
        target_reqs = spell.get_targets(game)
        filter_fn = target_reqs[0].filter_fn

        # Creature passes
        assert filter_fn(creature) is True

        # Remove CREATURE type (simulating animation end or type change)
        original_types = creature.card_types
        creature.card_types = {CardType.ARTIFACT}
        assert filter_fn(creature) is False

        # Restore
        creature.card_types = original_types
        assert filter_fn(creature) is True

    def test_base_get_targets_returns_empty_list(self) -> None:
        """Cards with no targets defined should return an empty list
        (backward compatibility — default get_targets works)."""
        game = _make_game()
        p1 = game.players[0]

        from engine.card import Instant
        vanilla_spell = Instant(name="Opt", mana_cost=ManaCost.parse("{U}"), owner=p1, controller=p1)
        assert vanilla_spell.get_targets(game) == []

    def test_multiple_target_requirements_each_lazy(self) -> None:
        """When a spell returns multiple TargetRequirements, each filter_fn
        should independently evaluate properties at call time."""
        game = _make_game()
        p1, p2 = game.players

        creature_a = _make_creature(name="Alpha", owner=p2, controller=p2, power=3)
        creature_b = _make_creature(name="Beta", owner=p2, controller=p2, power=5)
        game.get_battlefield(p2).add(creature_a)
        game.get_battlefield(p2).add(creature_b)

        # Spell with two different filters
        req_small = TargetRequirement(
            filter_fn=lambda obj: (
                CardType.CREATURE in getattr(obj, "card_types", set())
                and getattr(obj, "base_power", 0) < 4
            ),
            description="creature with power less than 4",
            zone=Zone.BATTLEFIELD,
        )
        req_big = TargetRequirement(
            filter_fn=lambda obj: (
                CardType.CREATURE in getattr(obj, "card_types", set())
                and getattr(obj, "base_power", 0) >= 4
            ),
            description="creature with power 4 or greater",
            zone=Zone.BATTLEFIELD,
        )

        # Initial state: Alpha=3 power, Beta=5 power
        assert req_small.filter_fn(creature_a) is True
        assert req_small.filter_fn(creature_b) is False
        assert req_big.filter_fn(creature_a) is False
        assert req_big.filter_fn(creature_b) is True

        # Change Alpha's power to 6 — both filters should see it
        creature_a.base_power = 6
        assert req_small.filter_fn(creature_a) is False
        assert req_big.filter_fn(creature_a) is True

    def test_filter_on_creature_removed_from_battlefield(self) -> None:
        """A filter_fn should still correctly evaluate an object's properties
        even if the object has been removed from the battlefield (zone change).
        The filter checks object properties, not zone membership."""
        game = _make_game()
        p1, p2 = game.players

        creature = _make_creature(name="Doomed", owner=p2, controller=p2)
        game.get_battlefield(p2).add(creature)

        spell = _CreatureTargetSpell(owner=p1, controller=p1)
        target_reqs = spell.get_targets(game)
        filter_fn = target_reqs[0].filter_fn

        # Creature passes while on battlefield
        assert filter_fn(creature) is True

        # Remove from battlefield (dies) — filter still checks card_types
        game.get_battlefield(p2).remove(creature)
        # filter_fn checks card_types, not zone, so it still returns True
        assert filter_fn(creature) is True
