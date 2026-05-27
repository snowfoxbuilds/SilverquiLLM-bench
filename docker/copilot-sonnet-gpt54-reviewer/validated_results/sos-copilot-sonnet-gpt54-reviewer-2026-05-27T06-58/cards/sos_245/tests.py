"""Tests for SOS 245 — Witherbloom, the Balancer.

Card spec:
  Mana cost: {6}{B}{G} — Legendary Creature — Elder Dragon — 5/5
  Keywords: Deathtouch, Flying, Affinity (for creatures)
  Oracle text:
    1. "Affinity for creatures (This spell costs {1} less to cast for each
       creature you control.)"
    2. "Flying, deathtouch"
    3. "Instant and sorcery spells you cast have affinity for creatures."

Test coverage:
  - Static card properties (name, mana cost, P/T, supertypes, subtypes)
  - Deathtouch and Flying keywords present
  - cost_reduction() returns the creature count the controller controls
  - cost_reduction() counts only creatures, not other permanents
  - cost_reduction() counts only the controller's creatures, not the opponent's
  - cost_reduction() is 0 when the controller has no creatures
  - cost_reduction() result is not capped by generic cost at the card level
    (capping happens in get_cost_reduction in casting.py, not here)
  - Third ability: instants and sorceries the controller casts have affinity
    for creatures (cost reduction applied via get_cost_reduction pipeline)
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vanilla_creature(name: str = "Vanilla Bear") -> Creature:
    """Return a simple 2/2 creature with no special abilities."""
    return Creature(name=name, base_power=2, base_toughness=2)


class _SimpleInstant(Instant):
    """A plain instant with a {3} generic mana cost, no special abilities."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Test Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        super().__init__(**kwargs)


class _SimpleSorcery(Sorcery):
    """A plain sorcery with a {4} generic mana cost, no special abilities."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Test Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))
        super().__init__(**kwargs)


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------

class TestWitherbloomProperties:
    """Static card data must match the SOS 245 spec."""

    def test_is_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert WitherbloomTheBalancer(owner=None).name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_base_power(self) -> None:
        assert WitherbloomTheBalancer(owner=None).base_power == 5

    def test_base_toughness(self) -> None:
        assert WitherbloomTheBalancer(owner=None).base_toughness == 5

    def test_legendary_supertype(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_elder_dragon_subtypes(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_card_type_is_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert CardType.CREATURE in card.card_types


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------

class TestWitherbloomKeywords:
    """Witherbloom must have Flying and Deathtouch."""

    def test_has_flying(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_deathtouch(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.DEATHTOUCH in card.keywords


# ---------------------------------------------------------------------------
# Affinity for creatures — own cost reduction
# ---------------------------------------------------------------------------

class TestWitherbloomOwnCostReduction:
    """cost_reduction() counts creatures the controller controls."""

    def test_zero_creatures_gives_zero_reduction(self) -> None:
        """No creatures on battlefield → no reduction."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Battlefield has no creatures for p1
        assert card.cost_reduction(game) == 0

    def test_one_creature_gives_one_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[_make_vanilla_creature("Bear 1")])
        assert card.cost_reduction(game) == 1

    def test_three_creatures_gives_three_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [_make_vanilla_creature(f"Bear {i}") for i in range(3)]
        set_board_state(game, 0, battlefield=creatures)
        assert card.cost_reduction(game) == 3

    def test_six_creatures_gives_six_reduction(self) -> None:
        """6 creatures → 6 reduction, which exactly offsets the 6 generic mana."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [_make_vanilla_creature(f"Bear {i}") for i in range(6)]
        set_board_state(game, 0, battlefield=creatures)
        assert card.cost_reduction(game) == 6

    def test_eight_creatures_reported_correctly(self) -> None:
        """cost_reduction() reports raw creature count (capping to generic is done
        by get_cost_reduction in casting.py, not by the card itself)."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [_make_vanilla_creature(f"Bear {i}") for i in range(8)]
        set_board_state(game, 0, battlefield=creatures)
        # Raw reduction is 8 (clamping to generic=6 happens in casting.py)
        assert card.cost_reduction(game) == 8

    def test_opponent_creatures_do_not_count(self) -> None:
        """Creatures controlled by the opponent must not reduce the cost."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Only opponent (player 1 index=1) has creatures
        opponent_creatures = [_make_vanilla_creature(f"Enemy {i}") for i in range(3)]
        set_board_state(game, 1, battlefield=opponent_creatures)
        assert card.cost_reduction(game) == 0

    def test_non_creature_permanents_do_not_count(self) -> None:
        """Non-creature permanents must not be counted."""
        from engine.card import Enchantment, Artifact
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)

        # Place a non-creature enchantment and artifact on p1's battlefield
        enchantment = Enchantment(name="Test Enchantment", owner=p1, controller=p1)
        artifact = Artifact(name="Test Artifact", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[enchantment, artifact])
        assert card.cost_reduction(game) == 0

    def test_cost_reduction_when_controller_is_none(self) -> None:
        """If controller is None, cost_reduction must return 0 without raising."""
        game = create_game()
        card = WitherbloomTheBalancer(owner=None, controller=None)
        result = card.cost_reduction(game)
        assert result == 0

    def test_get_cost_reduction_is_clamped_to_generic(self) -> None:
        """The casting.py get_cost_reduction helper clamps to generic=6.
        With 8 creatures the effective reduction must be exactly 6."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [_make_vanilla_creature(f"Bear {i}") for i in range(8)]
        set_board_state(game, 0, battlefield=creatures)
        reduction = get_cost_reduction(game, card, p1)
        assert reduction == 6  # clamped to generic portion of {6}{B}{G}


# ---------------------------------------------------------------------------
# Third ability — instants and sorceries the controller casts have affinity
# ---------------------------------------------------------------------------

class TestWitherbloomGrantsAffinityToSpells:
    """When Witherbloom is on the battlefield, instants and sorceries the
    controller casts should have their cost reduced by the number of creatures
    the controller controls (affinity for creatures)."""

    def _setup_witherbloom_in_play(
        self, game: Any, player_index: int
    ) -> WitherbloomTheBalancer:
        """Place Witherbloom on the battlefield and register its effects."""
        p = game.players[player_index]
        wb = WitherbloomTheBalancer(owner=p, controller=p)
        game.get_battlefield(p).add(wb)
        wb.register_triggers(game)
        return wb

    def test_instant_gets_no_reduction_without_witherbloom(self) -> None:
        """A plain instant has 0 cost reduction when Witherbloom is not in play."""
        game = create_game()
        p1 = game.players[0]
        instant = _SimpleInstant(owner=p1, controller=p1)
        creatures = [_make_vanilla_creature(f"Bear {i}") for i in range(3)]
        set_board_state(game, 0, battlefield=creatures)
        reduction = get_cost_reduction(game, instant, p1)
        assert reduction == 0

    def test_instant_gets_reduction_equal_to_creature_count(self) -> None:
        """With Witherbloom in play and 3 creatures, an instant costs {3} less."""
        game = create_game()
        p1 = game.players[0]
        wb = self._setup_witherbloom_in_play(game, 0)
        # Three additional creatures besides Witherbloom itself
        other_creatures = [_make_vanilla_creature(f"Bear {i}") for i in range(3)]
        set_board_state(game, 0, battlefield=[wb] + other_creatures)
        instant = _SimpleInstant(owner=p1, controller=p1)
        reduction = get_cost_reduction(game, instant, p1)
        # 4 creatures total (Witherbloom + 3 bears), instant has {3} generic
        # clamped to min(4, 3) = 3
        assert reduction == 3

    def test_sorcery_gets_reduction_equal_to_creature_count(self) -> None:
        """With Witherbloom in play and 2 creatures, a sorcery costs {2} less."""
        game = create_game()
        p1 = game.players[0]
        wb = self._setup_witherbloom_in_play(game, 0)
        other_creatures = [_make_vanilla_creature(f"Bear {i}") for i in range(2)]
        set_board_state(game, 0, battlefield=[wb] + other_creatures)
        sorcery = _SimpleSorcery(owner=p1, controller=p1)
        reduction = get_cost_reduction(game, sorcery, p1)
        # 3 creatures total, sorcery has {4} generic, reduction = min(3, 4) = 3
        assert reduction == 3

    def test_opponent_spell_does_not_benefit_from_witherbloom(self) -> None:
        """Witherbloom's affinity grant applies only to its controller's spells."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Witherbloom is under p1's control
        wb = self._setup_witherbloom_in_play(game, 0)
        set_board_state(game, 0, battlefield=[wb])
        # p2 casts an instant — should get no reduction from p1's Witherbloom
        instant = _SimpleInstant(owner=p2, controller=p2)
        reduction = get_cost_reduction(game, instant, p2)
        assert reduction == 0

    def test_instant_reduction_clamped_to_generic(self) -> None:
        """Reduction can't exceed the generic mana of the spell being cast."""
        game = create_game()
        p1 = game.players[0]
        wb = self._setup_witherbloom_in_play(game, 0)
        # 10 creatures — more than the instant's {3} generic
        other_creatures = [_make_vanilla_creature(f"Bear {i}") for i in range(10)]
        set_board_state(game, 0, battlefield=[wb] + other_creatures)
        instant = _SimpleInstant(owner=p1, controller=p1)
        reduction = get_cost_reduction(game, instant, p1)
        # Clamped to the instant's generic cost of 3
        assert reduction == 3

    def test_non_instant_sorcery_does_not_get_granted_affinity(self) -> None:
        """Non-instant, non-sorcery spells should NOT benefit from the grant.
        (Witherbloom grants affinity only to instant and sorcery spells.)"""
        game = create_game()
        p1 = game.players[0]
        wb = self._setup_witherbloom_in_play(game, 0)
        # Use a plain Creature spell (non-instant, non-sorcery)
        other_creatures = [_make_vanilla_creature(f"Bear {i}") for i in range(3)]
        set_board_state(game, 0, battlefield=[wb] + other_creatures)
        # A creature card with generic cost — should NOT get affinity grant
        creature_spell = Creature(
            name="Creature Spell",
            mana_cost=ManaCost.parse("{4}"),
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        reduction = get_cost_reduction(game, creature_spell, p1)
        assert reduction == 0
