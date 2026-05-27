"""Tests for sos_245 — Witherbloom, the Balancer.

Card spec:
  Mana cost: {6}{B}{G}
  Type: Legendary Creature — Elder Dragon
  P/T: 5/5
  Keywords: Flying, Deathtouch
  Oracle text:
    Affinity for creatures (This spell costs {1} less to cast for each
    creature you control.)
    Flying, deathtouch
    Instant and sorcery spells you cast have affinity for creatures.
"""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestWitherbloomProperties:
    """Static card data should match the sos_245 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(WitherbloomTheBalancer(owner=None), Creature)

    def test_name(self) -> None:
        assert WitherbloomTheBalancer(owner=None).name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        assert WitherbloomTheBalancer(owner=None).mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_power(self) -> None:
        assert WitherbloomTheBalancer(owner=None).base_power == 5

    def test_toughness(self) -> None:
        assert WitherbloomTheBalancer(owner=None).base_toughness == 5

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in WitherbloomTheBalancer(owner=None).keywords

    def test_has_deathtouch(self) -> None:
        assert Keyword.DEATHTOUCH in WitherbloomTheBalancer(owner=None).keywords

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in WitherbloomTheBalancer(owner=None).supertypes

    def test_elder_dragon_subtypes(self) -> None:
        subtypes = WitherbloomTheBalancer(owner=None).subtypes
        assert "Elder" in subtypes
        assert "Dragon" in subtypes

    def test_is_black_and_green(self) -> None:
        from engine.types import Color
        colors = WitherbloomTheBalancer(owner=None).colors
        assert Color.BLACK in colors
        assert Color.GREEN in colors


# ---------------------------------------------------------------------------
# Own affinity for creatures — cost_reduction()
# ---------------------------------------------------------------------------

class TestWitherbloomAffinityForCreatures:
    """cost_reduction() returns the number of creatures the controller controls."""

    def test_no_creatures_no_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_no_controller_no_reduction(self) -> None:
        game = create_game()
        card = WitherbloomTheBalancer(owner=None)
        assert card.cost_reduction(game) == 0

    def test_one_creature_reduces_by_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creature = Creature(name="Bear", owner=p1, controller=p1,
                            base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[creature])
        assert card.cost_reduction(game) == 1

    def test_three_creatures_reduces_by_three(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            Creature(name=f"Bear {i}", owner=p1, controller=p1,
                     base_power=2, base_toughness=2)
            for i in range(3)
        ]
        set_board_state(game, 0, battlefield=creatures)
        assert card.cost_reduction(game) == 3

    def test_only_controllers_creatures_count(self) -> None:
        """Opponent's creatures on the battlefield do not count."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        opp_creature = Creature(name="Enemy", owner=p2, controller=p2,
                                base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[opp_creature])
        assert card.cost_reduction(game) == 0

    def test_non_creature_permanents_not_counted(self) -> None:
        """Non-creature permanents in the controller's battlefield don't count."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Add a land (non-creature) using a plain CardImpl; its card_types won't include CREATURE
        from engine.card import Land
        land = Land(name="Forest", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land])
        assert card.cost_reduction(game) == 0

    def test_max_reduction_capped_at_generic_cost(self) -> None:
        """Eight creatures would try to reduce {6}{B}{G} by 8, but generic
        portion is only 6, so the engine clamps at 6."""
        from engine.casting import get_cost_reduction
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            Creature(name=f"Bear {i}", owner=p1, controller=p1,
                     base_power=1, base_toughness=1)
            for i in range(8)
        ]
        set_board_state(game, 0, battlefield=creatures)
        # cost_reduction reports raw creature count (8),
        # but the casting pipeline clamps it to the generic portion (6).
        raw_reduction = card.cost_reduction(game)
        clamped = get_cost_reduction(game, card, p1)
        assert raw_reduction == 8
        assert clamped == 6  # cannot reduce below 0 generic mana


# ---------------------------------------------------------------------------
# Grants affinity for creatures to instants and sorceries
# ---------------------------------------------------------------------------

class TestWitherbloomGrantsAffinityToSpells:
    """When Witherbloom is on the battlefield, instant and sorcery spells
    the controller casts should benefit from affinity for creatures
    (i.e., their effective cost is reduced by the number of creatures
    the controller controls)."""

    def test_witherbloom_on_battlefield_reduces_instant_cost(self) -> None:
        """With 3 creatures on the battlefield and Witherbloom in play,
        an instant that costs {4} should be castable with only {1} mana."""
        game = create_game()
        p1 = game.players[0]

        # Put Witherbloom and 3 other creatures on the battlefield.
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        c1 = Creature(name="Bear1", owner=p1, controller=p1,
                      base_power=2, base_toughness=2)
        c2 = Creature(name="Bear2", owner=p1, controller=p1,
                      base_power=2, base_toughness=2)
        c3 = Creature(name="Bear3", owner=p1, controller=p1,
                      base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[witherbloom, c1, c2, c3])
        witherbloom.register_triggers(game)

        # Create a {4}-cost instant in hand.
        test_instant = Instant(name="Test Instant",
                               owner=p1, controller=p1,
                               mana_cost=ManaCost.parse("{4}"))
        set_board_state(game, 0, hand=[test_instant],
                        mana={ManaType.COLORLESS: 1})

        # 4 creatures on battlefield: effective cost {4} - 4 = {0}? Wait,
        # we have witherbloom + 3 bears = 4 creatures. So {4} - 4 = {0}.
        # With 1 colorless mana, castable only if cost is capped at {0}.
        # The test checks that the cast succeeds, proving affinity was applied.
        from test_utils import cast_spell
        cast_spell(game, 0, "Test Instant")
        # If we reach here without CastingError, the cost reduction applied.

    def test_witherbloom_reduces_sorcery_cost(self) -> None:
        """Same as above but for a sorcery spell."""
        from test_utils import cast_spell, advance_to_phase
        from engine.types import Phase

        game = create_game()
        p1 = game.players[0]

        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        c1 = Creature(name="Bear1", owner=p1, controller=p1,
                      base_power=2, base_toughness=2)
        c2 = Creature(name="Bear2", owner=p1, controller=p1,
                      base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[witherbloom, c1, c2])
        witherbloom.register_triggers(game)

        # 3 creatures total. Sorcery costs {3}. With 3 creatures, cost = {0}.
        test_sorcery = Sorcery(name="Test Sorcery",
                               owner=p1, controller=p1,
                               mana_cost=ManaCost.parse("{3}"))
        set_board_state(game, 0, hand=[test_sorcery],
                        mana={ManaType.COLORLESS: 0})

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        cast_spell(game, 0, "Test Sorcery")
        # No CastingError means cost was reduced to {0}.

    def test_witherbloom_itself_counts_as_one_creature_for_spell_reduction(self) -> None:
        """With only Witherbloom on the battlefield (1 creature), an instant
        that costs {2} is reduced to {1}."""
        game = create_game()
        p1 = game.players[0]

        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[witherbloom])
        witherbloom.register_triggers(game)

        # Witherbloom itself is 1 creature. An instant costing {2} needs
        # at least 2 creatures to go free. With only 1 creature, {1} mana needed.
        test_instant = Instant(name="Test Instant",
                               owner=p1, controller=p1,
                               mana_cost=ManaCost.parse("{2}"))
        set_board_state(game, 0, hand=[test_instant],
                        mana={ManaType.COLORLESS: 1})

        from test_utils import cast_spell
        cast_spell(game, 0, "Test Instant")
        # 1 creature → {2} - 1 = {1}, player has {1} mana. Should succeed.

    def test_opponent_casting_instant_not_reduced(self) -> None:
        """The affinity granted by Witherbloom only applies to the controller's
        own spells, not the opponent's."""
        import pytest
        from test_utils import TestSetupError

        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        c1 = Creature(name="Bear1", owner=p1, controller=p1,
                      base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[witherbloom, c1])
        witherbloom.register_triggers(game)

        # Opponent tries to cast {3} instant with only {1} mana.
        # With 2 creatures for p1 on board, if affinity were wrongly applied to
        # p2's spells, the cost would be {3}-2={1}, and p2 would cast successfully.
        # Correct behavior: p2's spells are NOT reduced, so cast fails.
        opp_instant = Instant(name="Opp Instant",
                              owner=p2, controller=p2,
                              mana_cost=ManaCost.parse("{3}"))
        set_board_state(game, 1, hand=[opp_instant],
                        mana={ManaType.COLORLESS: 1})

        with pytest.raises(TestSetupError):
            from test_utils import cast_spell
            cast_spell(game, 1, "Opp Instant")

    def test_creature_spell_not_granted_affinity(self) -> None:
        """The affinity-granting applies only to instants and sorceries,
        not to creature spells."""
        import pytest
        from test_utils import TestSetupError

        game = create_game()
        p1 = game.players[0]

        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        c1 = Creature(name="Bear1", owner=p1, controller=p1,
                      base_power=2, base_toughness=2)
        c2 = Creature(name="Bear2", owner=p1, controller=p1,
                      base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[witherbloom, c1, c2])
        witherbloom.register_triggers(game)

        # Create a creature spell costing {3}.  3 creatures on board — if affinity
        # were incorrectly granted, it'd be free.  With {1} mana, cast should fail.
        creature_spell = Creature(name="Big Creature",
                                  owner=p1, controller=p1,
                                  base_power=3, base_toughness=3,
                                  mana_cost=ManaCost.parse("{3}"))
        set_board_state(game, 0, hand=[creature_spell],
                        mana={ManaType.COLORLESS: 1})

        with pytest.raises(TestSetupError):
            from test_utils import cast_spell
            cast_spell(game, 0, "Big Creature")


# ---------------------------------------------------------------------------
# Flying — blocking restrictions
# ---------------------------------------------------------------------------

class TestWitherbloomFlying:
    """Flying restricts which creatures can block Witherbloom."""

    def test_ground_creature_cannot_block_witherbloom(self) -> None:
        from engine.combat import _can_block
        attacker = WitherbloomTheBalancer(owner=None)
        ground = Creature(name="Ground Bear", base_power=2, base_toughness=2)
        ground.keywords = Keyword(0)
        ground.is_tapped = False
        assert _can_block(ground, attacker) is False

    def test_flying_creature_can_block_witherbloom(self) -> None:
        from engine.combat import _can_block
        attacker = WitherbloomTheBalancer(owner=None)
        flier = Creature(name="Eagle", base_power=2, base_toughness=2)
        flier.keywords = Keyword.FLYING
        flier.is_tapped = False
        assert _can_block(flier, attacker) is True

    def test_reach_creature_can_block_witherbloom(self) -> None:
        from engine.combat import _can_block
        attacker = WitherbloomTheBalancer(owner=None)
        spider = Creature(name="Spider", base_power=1, base_toughness=4)
        spider.keywords = Keyword.REACH
        spider.is_tapped = False
        assert _can_block(spider, attacker) is True
