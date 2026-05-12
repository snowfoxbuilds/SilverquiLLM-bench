"""Tests for Rancorous Archaic implementation.

Tests basic properties, converge mechanic (converge counters based on colors
of mana spent), trample combat, and reach blocking.
"""

from __future__ import annotations

import pytest

from card_impl import RancorousArchaic

from engine.card import Creature
from engine.types import CardType, Color, Keyword, ManaType


# ---------------------------------------------------------------------------
# Basic properties
# ---------------------------------------------------------------------------

@pytest.mark.basic
class TestRancorousArchaicBasicProperties:
    """Basic property tests for Rancorous Archaic."""

    def test_is_creature(self) -> None:
        card = RancorousArchaic()
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = RancorousArchaic()
        assert card.name == "Rancorous Archaic"

    def test_card_types(self) -> None:
        card = RancorousArchaic()
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        card = RancorousArchaic()
        assert card.mana_cost.cmc == 5

    def test_subtype_avatar(self) -> None:
        card = RancorousArchaic()
        assert "Avatar" in card.subtypes

    def test_base_power(self) -> None:
        card = RancorousArchaic()
        assert card.base_power == 2

    def test_base_toughness(self) -> None:
        card = RancorousArchaic()
        assert card.base_toughness == 2


# ---------------------------------------------------------------------------
# Keyword tests
# ---------------------------------------------------------------------------

@pytest.mark.ability
class TestRancorousArchaicKeywords:
    """Keyword ability tests for Rancorous Archaic."""

    def test_has_trample(self) -> None:
        card = RancorousArchaic()
        assert Keyword.TRAMPLE in card.keywords

    def test_has_reach(self) -> None:
        card = RancorousArchaic()
        assert Keyword.REACH in card.keywords


# ---------------------------------------------------------------------------
# Converge — core ability tests via cast_spell
# ---------------------------------------------------------------------------

@pytest.mark.ability
class TestRancorousArchaicConverge:
    """Converge mechanic tests: +1/+1 counters based on colors spent."""

    def _get_battlefield_creature(self, game, player_idx, name):
        from engine.types import Zone
        bf = game.players[player_idx].zones[Zone.BATTLEFIELD]
        for c in bf.get_all():
            if getattr(c, "name", "") == name:
                return c
        return None

    def test_converge_zero_colors_colorless_only(self) -> None:
        from tests.test_utils import create_game, set_board_state, cast_spell
        game = create_game()
        card = RancorousArchaic()
        set_board_state(game, 0, hand=[card], mana={ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Rancorous Archaic")
        archaic = self._get_battlefield_creature(game, 0, "Rancorous Archaic")
        assert archaic.plus_one_counters == 0
        assert archaic.power == 2
        assert archaic.toughness == 2

    def test_converge_one_color(self) -> None:
        from tests.test_utils import create_game, set_board_state, cast_spell
        game = create_game()
        card = RancorousArchaic()
        set_board_state(game, 0, hand=[card], mana={ManaType.WHITE: 1, ManaType.COLORLESS: 4})
        cast_spell(game, 0, "Rancorous Archaic")
        archaic = self._get_battlefield_creature(game, 0, "Rancorous Archaic")
        assert archaic.plus_one_counters == 1
        assert archaic.power == 3
        assert archaic.toughness == 3

    def test_converge_two_colors(self) -> None:
        from tests.test_utils import create_game, set_board_state, cast_spell
        game = create_game()
        card = RancorousArchaic()
        set_board_state(game, 0, hand=[card], mana={ManaType.WHITE: 1, ManaType.RED: 1, ManaType.COLORLESS: 3})
        cast_spell(game, 0, "Rancorous Archaic")
        archaic = self._get_battlefield_creature(game, 0, "Rancorous Archaic")
        assert archaic.plus_one_counters == 2
        assert archaic.power == 4
        assert archaic.toughness == 4

    def test_converge_three_colors(self) -> None:
        from tests.test_utils import create_game, set_board_state, cast_spell
        game = create_game()
        card = RancorousArchaic()
        set_board_state(game, 0, hand=[card], mana={
            ManaType.WHITE: 1, ManaType.BLACK: 1, ManaType.GREEN: 1,
            ManaType.COLORLESS: 2,
        })
        cast_spell(game, 0, "Rancorous Archaic")
        archaic = self._get_battlefield_creature(game, 0, "Rancorous Archaic")
        assert archaic.plus_one_counters == 3
        assert archaic.power == 5
        assert archaic.toughness == 5

    def test_converge_five_colors(self) -> None:
        from tests.test_utils import create_game, set_board_state, cast_spell
        game = create_game()
        card = RancorousArchaic()
        set_board_state(game, 0, hand=[card], mana={
            ManaType.WHITE: 1, ManaType.BLUE: 1, ManaType.BLACK: 1,
            ManaType.RED: 1, ManaType.GREEN: 1,
        })
        cast_spell(game, 0, "Rancorous Archaic")
        archaic = self._get_battlefield_creature(game, 0, "Rancorous Archaic")
        assert archaic.plus_one_counters == 5
        assert archaic.power == 7
        assert archaic.toughness == 7

    def test_converge_colors_spent_attribute(self) -> None:
        from tests.test_utils import create_game, set_board_state, cast_spell
        game = create_game()
        card = RancorousArchaic()
        set_board_state(game, 0, hand=[card], mana={
            ManaType.WHITE: 1, ManaType.RED: 1, ManaType.COLORLESS: 3,
        })
        cast_spell(game, 0, "Rancorous Archaic")
        archaic = self._get_battlefield_creature(game, 0, "Rancorous Archaic")
        assert hasattr(archaic, "colors_spent")
        assert Color.WHITE in archaic.colors_spent
        assert Color.RED in archaic.colors_spent

    def test_converge_on_resolve_applies_counters(self) -> None:
        from tests.test_utils import create_game, set_board_state, cast_spell
        game = create_game()
        card = RancorousArchaic()
        set_board_state(game, 0, hand=[card], mana={
            ManaType.BLUE: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 3,
        })
        cast_spell(game, 0, "Rancorous Archaic")
        archaic = self._get_battlefield_creature(game, 0, "Rancorous Archaic")
        assert archaic.plus_one_counters == 2


# ---------------------------------------------------------------------------
# Trample combat tests
# ---------------------------------------------------------------------------

@pytest.mark.ability
class TestRancorousArchaicTrample:
    """Trample combat damage tests."""

    def test_trample_damage_through_blocker(self) -> None:
        from tests.test_utils import create_game, set_board_state, declare_attackers, declare_blockers
        from engine.combat import combat_damage_step
        from engine.types import Zone
        game = create_game(player2_life=20)
        archaic = RancorousArchaic()
        archaic.summoning_sick = False
        archaic.plus_one_counters = 3
        blocker = Creature(name="Wall", base_power=1, base_toughness=2)
        set_board_state(game, 0, battlefield=[archaic])
        set_board_state(game, 1, battlefield=[blocker])
        declare_attackers(game, ["Rancorous Archaic"])
        declare_blockers(game, {"Rancorous Archaic": ["Wall"]})
        defender_life_before = game.players[1].life
        combat_damage_step(game)
        assert game.players[1].life == defender_life_before - 3
        assert blocker.damage_marked == 2

    def test_trample_unblocked_damage_to_player(self) -> None:
        from tests.test_utils import create_game, set_board_state, declare_attackers
        from engine.combat import combat_damage_step
        from engine.types import Zone
        game = create_game(player2_life=20)
        archaic = RancorousArchaic()
        archaic.summoning_sick = False
        archaic.plus_one_counters = 2
        set_board_state(game, 0, battlefield=[archaic])
        declare_attackers(game, ["Rancorous Archaic"])
        combat_damage_step(game)
        assert game.players[1].life == 20 - 4

    def test_trample_small_blocker(self) -> None:
        from tests.test_utils import create_game, set_board_state, declare_attackers, declare_blockers
        from engine.combat import combat_damage_step
        game = create_game(player2_life=20)
        archaic = RancorousArchaic()
        archaic.summoning_sick = False
        archaic.plus_one_counters = 5
        blocker = Creature(name="Sprite", base_power=0, base_toughness=1)
        set_board_state(game, 0, battlefield=[archaic])
        set_board_state(game, 1, battlefield=[blocker])
        declare_attackers(game, ["Rancorous Archaic"])
        declare_blockers(game, {"Rancorous Archaic": ["Sprite"]})
        combat_damage_step(game)
        assert game.players[1].life == 20 - 6
        assert blocker.damage_marked == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

@pytest.mark.edge
class TestRancorousArchaicEdgeCases:
    """Edge case tests for Rancorous Archaic."""

    def test_instance_independence(self) -> None:
        c1 = RancorousArchaic()
        c2 = RancorousArchaic()
        c1.plus_one_counters = 5
        assert c2.plus_one_counters == 0

    def test_counters_affect_power_toughness(self) -> None:
        card = RancorousArchaic()
        card.plus_one_counters = 4
        assert card.power == 6
        assert card.toughness == 6

    def test_no_counters_on_fresh_instance(self) -> None:
        card = RancorousArchaic()
        assert card.plus_one_counters == 0
        assert card.minus_one_counters == 0

    def test_summoning_sickness_default(self) -> None:
        card = RancorousArchaic()
        assert card.summoning_sick is True

    def test_not_attacking_default(self) -> None:
        card = RancorousArchaic()
        assert card.is_attacking is False

    def test_not_tapped_default(self) -> None:
        card = RancorousArchaic()
        assert card.is_tapped is False

    def test_counters_property(self) -> None:
        card = RancorousArchaic()
        card.plus_one_counters = 3
        ctrs = card.counters
        assert ctrs.get("+1/+1", 0) == 3


# ---------------------------------------------------------------------------
# Interaction tests
# ---------------------------------------------------------------------------

@pytest.mark.interaction
class TestRancorousArchaicInteractions:
    """Interaction tests: reach, coexistence, combat state."""

    def test_reach_can_block_flying(self) -> None:
        from tests.test_utils import create_game, set_board_state, declare_attackers, declare_blockers
        from engine.types import Zone
        game = create_game()
        flyer = Creature(name="FlyingBird", base_power=3, base_toughness=2, keywords=Keyword.FLYING)
        flyer.summoning_sick = False
        archaic = RancorousArchaic()
        set_board_state(game, 0, battlefield=[flyer])
        set_board_state(game, 1, battlefield=[archaic])
        declare_attackers(game, ["FlyingBird"])
        declare_blockers(game, {"FlyingBird": ["Rancorous Archaic"]})
        assert archaic.is_blocking is True

    def test_coexists_with_other_permanents(self) -> None:
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        companion = Creature(name="Ally", base_power=2, base_toughness=2)
        archaic = RancorousArchaic()
        set_board_state(game, 0, battlefield=[archaic, companion])
        bf = game.players[0].zones[Zone.BATTLEFIELD].get_all()
        assert len(bf) == 2

    def test_card_enters_battlefield_via_cast(self) -> None:
        from tests.test_utils import create_game, set_board_state, cast_spell
        from engine.types import Zone
        game = create_game()
        card = RancorousArchaic()
        set_board_state(game, 0, hand=[card], mana={ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Rancorous Archaic")
        bf = game.players[0].zones[Zone.BATTLEFIELD].get_all()
        names = [getattr(c, "name", "") for c in bf]
        assert "Rancorous Archaic" in names
