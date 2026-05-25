"""Tests for TODO item 16: Minimal engine extensions for SOS prototype mechanics.

Tests verify:
- ManaPool tracks colors of mana spent (last_payment_colors).
- cast_spell stores colors_spent on the card instance.
- Converge mechanic: colors_spent reflects the distinct colors used for payment.
- All 5 prototype cards can be instantiated without NotImplementedError.
- Existing engine tests remain unaffected.
"""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.engine.card import (
    CardImpl,
    Creature,
    Instant,
    Land,
    Planeswalker,
)
from benchmarks.sos.workspace.engine.casting import cast_spell, CastingError
from benchmarks.sos.workspace.engine.game_state import GameState
from benchmarks.sos.workspace.engine.mana import ManaPool
from benchmarks.sos.workspace.engine.player import DeterministicPlayer
from benchmarks.sos.workspace.engine.types import (
    CardType,
    Color,
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Supertype,
    Zone,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(
    p1_script: list | None = None,
    p2_script: list | None = None,
) -> GameState:
    """Create a minimal 2-player game state."""
    p1 = DeterministicPlayer("P1", p1_script or [])
    p2 = DeterministicPlayer("P2", p2_script or [])
    game = GameState([p1, p2])
    # Set to main phase with empty stack for sorcery-speed casting.
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    return game


# ---------------------------------------------------------------------------
# ManaPool.last_payment_colors tests
# ---------------------------------------------------------------------------

class TestManaPoolColorTracking:
    """Tests for mana color tracking on ManaPool."""

    def test_initial_last_payment_colors_empty(self) -> None:
        pool = ManaPool()
        assert pool.last_payment_colors == []

    def test_single_color_pip_payment(self) -> None:
        pool = ManaPool()
        pool.add(ManaType.WHITE, 1)
        cost = ManaCost(pips={ManaType.WHITE: 1})
        assert pool.pay(cost)
        assert pool.last_payment_colors == [Color.WHITE]

    def test_two_color_pips_payment(self) -> None:
        pool = ManaPool()
        pool.add(ManaType.WHITE, 1)
        pool.add(ManaType.BLUE, 1)
        cost = ManaCost(pips={ManaType.WHITE: 1, ManaType.BLUE: 1})
        assert pool.pay(cost)
        colors = pool.last_payment_colors
        assert Color.WHITE in colors
        assert Color.BLUE in colors
        assert len(colors) == 2

    def test_generic_paid_with_colored_mana(self) -> None:
        pool = ManaPool()
        pool.add(ManaType.RED, 3)
        cost = ManaCost(generic=3)
        assert pool.pay(cost)
        assert pool.last_payment_colors == [Color.RED]

    def test_generic_paid_with_colorless_no_colors(self) -> None:
        pool = ManaPool()
        pool.add(ManaType.COLORLESS, 3)
        cost = ManaCost(generic=3)
        assert pool.pay(cost)
        assert pool.last_payment_colors == []

    def test_mixed_generic_and_pips(self) -> None:
        """Pay {1}{W} with 1 White + 1 Green → colors = [Green, White]."""
        pool = ManaPool()
        pool.add(ManaType.WHITE, 1)
        pool.add(ManaType.GREEN, 1)
        cost = ManaCost(generic=1, pips={ManaType.WHITE: 1})
        assert pool.pay(cost)
        colors = pool.last_payment_colors
        assert Color.WHITE in colors
        assert Color.GREEN in colors

    def test_all_five_colors(self) -> None:
        """Pay {5} with one of each color → 5 distinct colors."""
        pool = ManaPool()
        for mt in [ManaType.WHITE, ManaType.BLUE, ManaType.BLACK, ManaType.RED, ManaType.GREEN]:
            pool.add(mt, 1)
        cost = ManaCost(generic=5)
        assert pool.pay(cost)
        assert len(pool.last_payment_colors) == 5

    def test_payment_failure_leaves_colors_unchanged(self) -> None:
        pool = ManaPool()
        pool.add(ManaType.WHITE, 1)
        # First successful payment
        cost1 = ManaCost(pips={ManaType.WHITE: 1})
        pool.pay(cost1)
        initial = pool.last_payment_colors
        # Failed payment — not enough mana
        cost2 = ManaCost(pips={ManaType.BLUE: 1})
        assert not pool.pay(cost2)
        # last_payment_colors should still reflect the previous successful payment
        assert pool.last_payment_colors == initial

    def test_last_payment_colors_returns_copy(self) -> None:
        pool = ManaPool()
        pool.add(ManaType.RED, 1)
        pool.pay(ManaCost(pips={ManaType.RED: 1}))
        colors1 = pool.last_payment_colors
        colors2 = pool.last_payment_colors
        assert colors1 == colors2
        assert colors1 is not colors2  # distinct list objects

    def test_converge_scenario_five_generic(self) -> None:
        """Simulate Rancorous Archaic: {5} paid with 5 different colors."""
        pool = ManaPool()
        pool.add(ManaType.WHITE, 1)
        pool.add(ManaType.BLUE, 1)
        pool.add(ManaType.BLACK, 1)
        pool.add(ManaType.RED, 1)
        pool.add(ManaType.GREEN, 1)
        cost = ManaCost(generic=5)
        assert pool.pay(cost)
        assert len(pool.last_payment_colors) == 5

    def test_converge_scenario_single_color(self) -> None:
        """Simulate Rancorous Archaic: {5} paid with 5 of the same color."""
        pool = ManaPool()
        pool.add(ManaType.GREEN, 5)
        cost = ManaCost(generic=5)
        assert pool.pay(cost)
        assert pool.last_payment_colors == [Color.GREEN]

    def test_generic_with_choices_tracks_colors(self) -> None:
        """When using explicit choices for generic, colors are tracked."""
        pool = ManaPool()
        pool.add(ManaType.RED, 2)
        pool.add(ManaType.BLUE, 1)
        cost = ManaCost(generic=2)
        assert pool.pay(cost, choices={ManaType.RED: 1, ManaType.BLUE: 1})
        colors = pool.last_payment_colors
        assert Color.RED in colors
        assert Color.BLUE in colors


# ---------------------------------------------------------------------------
# cast_spell stores colors_spent on card
# ---------------------------------------------------------------------------

class TestCastSpellColorsSpent:
    """Tests that cast_spell stores colors_spent on the card."""

    def test_colors_spent_stored_on_card(self) -> None:
        game = _make_game()
        player = game.players[0]
        card = Creature(
            name="Test Creature",
            mana_cost=ManaCost(generic=2, pips={ManaType.RED: 1}),
            base_power=2,
            base_toughness=2,
        )
        card.owner = player
        game.get_hand(player).add(card)
        player.mana_pool.add(ManaType.RED, 1)
        player.mana_pool.add(ManaType.GREEN, 2)
        cast_spell(game, player, card)
        assert hasattr(card, "colors_spent")
        assert Color.RED in card.colors_spent
        assert Color.GREEN in card.colors_spent

    def test_colors_spent_colorless_only(self) -> None:
        game = _make_game()
        player = game.players[0]
        card = Creature(
            name="Colorless Bot",
            mana_cost=ManaCost(generic=3),
            base_power=3,
            base_toughness=3,
        )
        card.owner = player
        game.get_hand(player).add(card)
        player.mana_pool.add(ManaType.COLORLESS, 3)
        cast_spell(game, player, card)
        assert card.colors_spent == []  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Prototype card instantiation tests
# ---------------------------------------------------------------------------

class TestPrototypeCardInstantiation:
    """Verify all 5 prototype cards can be instantiated."""

    def test_plains_instantiation(self) -> None:
        """Plains — basic land."""
        card = Land(
            name="Plains",
            supertypes={Supertype.BASIC},
            subtypes={"Plains"},
        )
        assert CardType.LAND in card.card_types
        assert Supertype.BASIC in card.supertypes
        assert card.name == "Plains"

    def test_eager_glyphmage_instantiation(self) -> None:
        """Eager Glyphmage — creature with ETB trigger."""
        card = Creature(
            name="Eager Glyphmage",
            mana_cost=ManaCost.parse("{3}{W}"),
            subtypes={"Cat", "Cleric"},
            base_power=2,
            base_toughness=2,
            rules_text="When this creature enters, create a 1/1 white and black Inkling creature token with flying.",
        )
        assert CardType.CREATURE in card.card_types
        assert card.base_power == 2
        assert card.mana_cost.cmc == 4

    def test_ajanis_response_instantiation(self) -> None:
        """Ajani's Response — instant with cost reduction."""
        card = Instant(
            name="Ajani's Response",
            mana_cost=ManaCost.parse("{4}{W}"),
            rules_text="This spell costs {3} less to cast if it targets a tapped creature.\nDestroy target creature.",
        )
        assert CardType.INSTANT in card.card_types
        assert card.mana_cost.cmc == 5

    def test_rancorous_archaic_instantiation(self) -> None:
        """Rancorous Archaic — creature with Converge."""
        card = Creature(
            name="Rancorous Archaic",
            mana_cost=ManaCost.parse("{5}"),
            subtypes={"Avatar"},
            keywords=Keyword.TRAMPLE | Keyword.REACH,
            base_power=5,
            base_toughness=5,
            rules_text="Trample, reach\nConverge — This creature enters with a +1/+1 counter on it for each color of mana spent to cast it.",
        )
        assert CardType.CREATURE in card.card_types
        assert Keyword.TRAMPLE in card.keywords
        assert Keyword.REACH in card.keywords
        assert card.mana_cost.cmc == 5

    def test_ral_zarek_instantiation(self) -> None:
        """Ral Zarek, Guest Lecturer — legendary planeswalker."""
        card = Planeswalker(
            name="Ral Zarek, Guest Lecturer",
            mana_cost=ManaCost.parse("{1}{B}{B}"),
            supertypes={Supertype.LEGENDARY},
            subtypes={"Ral"},
            starting_loyalty=4,
            rules_text="+1: Surveil 2.\n−1: Any number of target players each discard a card.\n−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.\n−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
        )
        assert CardType.PLANESWALKER in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert card.loyalty == 4
        assert card.starting_loyalty == 4


# ---------------------------------------------------------------------------
# Converge mechanic integration test
# ---------------------------------------------------------------------------

class TestConvergeMechanic:
    """Integration tests for the Converge mechanic using colors_spent."""

    def test_converge_counter_placement(self) -> None:
        """Simulate Rancorous Archaic entering with +1/+1 counters from Converge."""
        game = _make_game()
        player = game.players[0]

        card = Creature(
            name="Rancorous Archaic",
            mana_cost=ManaCost.parse("{5}"),
            subtypes={"Avatar"},
            keywords=Keyword.TRAMPLE | Keyword.REACH,
            base_power=5,
            base_toughness=5,
        )
        card.owner = player
        game.get_hand(player).add(card)

        # Pay with 3 different colors + 2 colorless
        player.mana_pool.add(ManaType.WHITE, 1)
        player.mana_pool.add(ManaType.RED, 1)
        player.mana_pool.add(ManaType.GREEN, 1)
        player.mana_pool.add(ManaType.COLORLESS, 2)

        cast_spell(game, player, card)

        # Verify colors_spent has 3 colors
        assert len(card.colors_spent) == 3  # type: ignore[attr-defined]
        assert Color.WHITE in card.colors_spent  # type: ignore[attr-defined]
        assert Color.RED in card.colors_spent  # type: ignore[attr-defined]
        assert Color.GREEN in card.colors_spent  # type: ignore[attr-defined]

        # Simulate Converge: add +1/+1 counters equal to colors spent
        card.plus_one_counters = len(card.colors_spent)  # type: ignore[attr-defined]
        assert card.power == 5 + 3
        assert card.toughness == 5 + 3

    def test_converge_zero_colors(self) -> None:
        """Converge with all colorless mana → 0 counters."""
        game = _make_game()
        player = game.players[0]

        card = Creature(
            name="Rancorous Archaic",
            mana_cost=ManaCost.parse("{5}"),
            base_power=5,
            base_toughness=5,
        )
        card.owner = player
        game.get_hand(player).add(card)

        player.mana_pool.add(ManaType.COLORLESS, 5)
        cast_spell(game, player, card)

        assert card.colors_spent == []  # type: ignore[attr-defined]
        card.plus_one_counters = len(card.colors_spent)  # type: ignore[attr-defined]
        assert card.power == 5
        assert card.toughness == 5


# ---------------------------------------------------------------------------
# _MANA_TO_COLOR mapping correctness
# ---------------------------------------------------------------------------

class TestManaToColorMapping:
    """Verify the internal _MANA_TO_COLOR mapping is complete and correct."""

    def test_all_five_colored_mana_types_mapped(self) -> None:
        from benchmarks.sos.workspace.engine.mana import _MANA_TO_COLOR
        assert _MANA_TO_COLOR[ManaType.WHITE] == Color.WHITE
        assert _MANA_TO_COLOR[ManaType.BLUE] == Color.BLUE
        assert _MANA_TO_COLOR[ManaType.BLACK] == Color.BLACK
        assert _MANA_TO_COLOR[ManaType.RED] == Color.RED
        assert _MANA_TO_COLOR[ManaType.GREEN] == Color.GREEN

    def test_colorless_not_in_mapping(self) -> None:
        from benchmarks.sos.workspace.engine.mana import _MANA_TO_COLOR
        assert ManaType.COLORLESS not in _MANA_TO_COLOR


# ---------------------------------------------------------------------------
# Additional edge cases for color tracking
# ---------------------------------------------------------------------------

class TestManaPoolColorTrackingEdgeCases:
    """Additional edge cases for mana color tracking."""

    def test_successive_payments_overwrite_colors(self) -> None:
        """Second successful payment replaces first payment's colors."""
        pool = ManaPool()
        pool.add(ManaType.RED, 2)
        pool.add(ManaType.BLUE, 1)

        pool.pay(ManaCost(pips={ManaType.RED: 1}))
        assert pool.last_payment_colors == [Color.RED]

        pool.pay(ManaCost(pips={ManaType.BLUE: 1}))
        assert pool.last_payment_colors == [Color.BLUE]

    def test_empty_does_not_clear_last_payment_colors(self) -> None:
        """Emptying the pool should not reset last_payment_colors."""
        pool = ManaPool()
        pool.add(ManaType.GREEN, 1)
        pool.pay(ManaCost(pips={ManaType.GREEN: 1}))
        assert pool.last_payment_colors == [Color.GREEN]
        pool.empty()
        assert pool.last_payment_colors == [Color.GREEN]

    def test_zero_cost_payment_yields_no_colors(self) -> None:
        """Paying a zero-cost spell should result in empty colors."""
        pool = ManaPool()
        pool.add(ManaType.RED, 1)
        # First pay something to set colors
        pool.pay(ManaCost(pips={ManaType.RED: 1}))
        assert pool.last_payment_colors == [Color.RED]
        # Now pay zero cost
        pool.add(ManaType.RED, 1)
        pool.pay(ManaCost())
        assert pool.last_payment_colors == []

    def test_colors_sorted_deterministically(self) -> None:
        """Colors should be sorted by enum value for determinism."""
        pool = ManaPool()
        pool.add(ManaType.GREEN, 1)
        pool.add(ManaType.WHITE, 1)
        pool.add(ManaType.RED, 1)
        cost = ManaCost(generic=3)
        pool.pay(cost)
        colors = pool.last_payment_colors
        assert colors == sorted(colors, key=lambda c: c.value)
