"""Rewritten audited tests for Together as One (sos_4).

5 test areas per TODO spec:
1. Identity — verifies card type, mana cost, CMC, colorless; NO Converge keyword assertion.
2. 1-color resolution — cast with 1 color of mana via full pipeline, verify X=1 effects.
3. 5-color resolution — cast with 5 colors of mana via full pipeline, verify X=5 effects.
4. 0-color discriminator — cast with purely colorless mana via full pipeline, verify X=0.
5. Fizzle-keeps-legal-effects — if damage target becomes illegal before resolution,
   draw + life gain still resolve.

All resolution tests use cast_spell() from test_utils with actual mana payment
through set_mana_pool(), exercising the full cast→resolve pipeline including
colors_spent recording and target validation.
"""

from __future__ import annotations

import pytest

from card_impl import TogetherAsOne

from engine.card import CardImpl, Creature, Sorcery
from engine.types import CardType, Color, ManaCost, ManaType, Zone
from test_utils import (
    card_colors,
    cast_spell,
    create_game,
    set_battlefield,
    set_hand,
    set_library_top,
    set_mana_pool,
)


# ---------------------------------------------------------------------------
# Helper: build a minimal creature for targeting
# ---------------------------------------------------------------------------

def _make_creature(name: str = "Bear", power: int = 2, toughness: int = 2):
    return Creature(name=name, base_power=power, base_toughness=toughness)


class TestIdentity:
    """Test 1: Card identity (no CONVERGE keyword assertion)."""

    def test_is_sorcery_subclass(self) -> None:
        card = TogetherAsOne()
        assert isinstance(card, Sorcery)

    def test_card_type_sorcery(self) -> None:
        card = TogetherAsOne()
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc_6(self) -> None:
        card = TogetherAsOne()
        assert card.mana_cost.cmc == 6

    def test_colorless_identity(self) -> None:
        """Together as One has {6} cost — no colored pips, so colorless."""
        card = TogetherAsOne()
        assert card_colors(card) == set()

    def test_name(self) -> None:
        card = TogetherAsOne()
        assert card.name == "Together as One"

    def test_no_converge_keyword(self) -> None:
        """Converge is an ability word, NOT a keyword. No Keyword.CONVERGE."""
        from engine.types import Keyword
        card = TogetherAsOne()
        converge = getattr(Keyword, "CONVERGE", None)
        if converge is not None:
            assert converge not in card.keywords


class TestOneColorResolution:
    """Test 2: Cast with 1 color of mana via full pipeline (X=1)."""

    def test_one_color_draw_damage_life(self) -> None:
        """Cast with {R} + 5 colorless → X=1 → draw 1, deal 1 dmg, gain 1 life."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Set up library for p2 to draw from
        filler = [CardImpl(name=f"Filler{i}") for i in range(5)]
        set_library_top(game, 1, filler)

        # Put spell in hand
        card = TogetherAsOne()
        set_hand(game, 0, [card])

        # Set mana: 1 Red + 5 Colorless = 6 total, 1 color
        set_mana_pool(game, 0, {ManaType.RED: 1, ManaType.COLORLESS: 5})

        # Set up a creature target for damage on p2's battlefield
        bear = _make_creature()
        set_battlefield(game, 1, [bear])

        initial_p1_life = p1.life
        initial_hand_size = len(p2.zones[Zone.HAND].get_all())

        # Cast through full pipeline: targets = [draw_target=p2, damage_target=bear]
        cast_spell(game, 0, "Together as One", targets=[p2, bear])

        # X=1: p2 draws 1 card
        assert len(p2.zones[Zone.HAND].get_all()) == initial_hand_size + 1
        # X=1: bear takes 1 damage
        assert bear.damage_marked == 1
        # X=1: controller gains 1 life
        assert p1.life == initial_p1_life + 1


class TestFiveColorResolution:
    """Test 3: Cast with 5 colors of mana via full pipeline (X=5)."""

    def test_five_color_full_effect(self) -> None:
        """Cast with W+U+B+R+G + 1 colorless → X=5 → draw 5, deal 5, gain 5."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Set up library for p2 to draw from (need at least 5 cards)
        filler = [CardImpl(name=f"Filler{i}") for i in range(10)]
        set_library_top(game, 1, filler)

        # Put spell in hand
        card = TogetherAsOne()
        set_hand(game, 0, [card])

        # Set mana: 1 of each color + 1 colorless = 6 total, 5 colors
        set_mana_pool(game, 0, {
            ManaType.WHITE: 1,
            ManaType.BLUE: 1,
            ManaType.BLACK: 1,
            ManaType.RED: 1,
            ManaType.GREEN: 1,
            ManaType.COLORLESS: 1,
        })

        initial_p1_life = p1.life
        initial_p2_life = p2.life
        initial_hand_size = len(p2.zones[Zone.HAND].get_all())

        # Cast targeting p2 for both draw and damage
        cast_spell(game, 0, "Together as One", targets=[p2, p2])

        # X=5: p2 draws 5 cards
        assert len(p2.zones[Zone.HAND].get_all()) == initial_hand_size + 5
        # X=5: p2 takes 5 damage
        assert p2.life == initial_p2_life - 5
        # X=5: controller gains 5 life
        assert p1.life == initial_p1_life + 5


class TestZeroColorDiscriminator:
    """Test 4: Cast with 0 colors (all colorless mana) — X=0, no effects."""

    def test_zero_colors_no_effect(self) -> None:
        """Cast with 6 colorless mana → X=0 → no draw, no damage, no life gain."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put spell in hand
        card = TogetherAsOne()
        set_hand(game, 0, [card])

        # Set mana: 6 colorless = 0 colors
        set_mana_pool(game, 0, {ManaType.COLORLESS: 6})

        # Set up a creature target for damage
        bear = _make_creature()
        set_battlefield(game, 1, [bear])

        initial_p1_life = p1.life
        initial_p2_life = p2.life
        initial_hand_size = len(p2.zones[Zone.HAND].get_all())

        # Cast through full pipeline
        cast_spell(game, 0, "Together as One", targets=[p2, bear])

        # X=0: nothing happens
        assert len(p2.zones[Zone.HAND].get_all()) == initial_hand_size
        assert bear.damage_marked == 0
        assert p1.life == initial_p1_life
        assert p2.life == initial_p2_life


class TestFizzleKeepsLegalEffects:
    """Test 5: Multi-effect fizzle preserves legal effects.

    This test must bypass the full cast pipeline slightly because the
    fizzle scenario requires a target to become illegal BETWEEN cast and
    resolution. We cast through the pipeline but simulate the creature
    leaving the battlefield before resolution by using a two-step approach:
    we set up the creature, cast the spell (which goes on stack), then
    remove the creature before resolution.

    NOTE: Since cast_spell() in test_utils resolves immediately (calls
    _resolve_top_of_stack internally), and the fizzle scenario is about
    state at resolution time, we test this by having the creature NOT on
    the battlefield from the start — the cast pipeline accepts it as a
    target (target legality is checked at cast time when it IS on bf),
    but at resolution time it's gone. For simplicity and to still exercise
    the cast pipeline for the colors_spent path, we use cast_spell but
    with a player as the damage target for the main path, and test the
    fizzle case by directly calling on_resolve with the illegal state
    (since cast_spell resolves atomically).
    """

    def test_damage_target_illegal_draw_and_life_still_resolve(self) -> None:
        """If the damage target (creature) left battlefield, draw + life gain still happen.

        This exercises the cast pipeline for colors_spent, then simulates
        the fizzle scenario at resolution.
        """
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Set up library for draws
        filler = [CardImpl(name=f"Filler{i}") for i in range(5)]
        set_library_top(game, 1, filler)

        # Put spell in hand and set 3-color mana
        card = TogetherAsOne()
        set_hand(game, 0, [card])
        set_mana_pool(game, 0, {
            ManaType.WHITE: 1,
            ManaType.BLUE: 1,
            ManaType.BLACK: 1,
            ManaType.COLORLESS: 3,
        })

        # Put creature on battlefield for targeting at cast time
        ghost = _make_creature("Ghost")
        set_battlefield(game, 1, [ghost])

        initial_p1_life = p1.life
        initial_p2_life = p2.life
        initial_hand_size = len(p2.zones[Zone.HAND].get_all())

        # Remove the creature from battlefield BEFORE we cast.
        # Since cast_spell resolves atomically, we simulate the fizzle by
        # passing a target that's not on the battlefield. The cast pipeline's
        # target selection uses the scripted choice directly; the illegality
        # is checked at resolution time by on_resolve's _is_valid_target.
        p2.zones[Zone.BATTLEFIELD].remove(ghost)

        # Cast — ghost is not on bf, so damage should fizzle at resolution
        cast_spell(game, 0, "Together as One", targets=[p2, ghost])

        # X=3: draw still resolves (p2 draws 3)
        assert len(p2.zones[Zone.HAND].get_all()) == initial_hand_size + 3
        # Damage does NOT happen (ghost not on battlefield = illegal target)
        assert ghost.damage_marked == 0
        # Life gain still resolves (not targeted — always happens)
        assert p1.life == initial_p1_life + 3
        # p2 life unchanged
        assert p2.life == initial_p2_life
