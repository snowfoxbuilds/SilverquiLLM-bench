"""Tests for sos_245 — Witherbloom, the Balancer.

Covers:
- Static card properties (name, mana cost, P/T, type, subtype, supertype)
- Flying and Deathtouch keywords
- Affinity for creatures cost reduction on Witherbloom itself
- Cost reduction is 0 with no creatures controlled
- Cost reduction equals creature count up to generic cap
- Cost reduction is capped at generic portion of mana cost (6)
- Opponent's creatures do not count toward cost reduction
- Grant of affinity for creatures to instants/sorceries while Witherbloom is in play
"""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
)
from test_utils import create_game, set_board_state


class TestWitherbloomTheBalancerProperties:
    """Static card data must match the sos_245 spec."""

    def test_name(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"

    def test_mana_cost_generic(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.mana_cost is not None
        assert card.mana_cost.generic == 6

    def test_mana_cost_black_pip(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.mana_cost is not None
        assert card.mana_cost.pips.get(ManaType.BLACK, 0) == 1

    def test_mana_cost_green_pip(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.mana_cost is not None
        assert card.mana_cost.pips.get(ManaType.GREEN, 0) == 1

    def test_mana_cost_cmc(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.mana_cost is not None
        assert card.mana_cost.cmc == 8

    def test_base_power(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_power == 5

    def test_base_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_toughness == 5

    def test_is_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_is_legendary(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtype_includes_dragon(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert "Dragon" in card.subtypes or "Elder Dragon" in card.subtypes

    def test_has_flying(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_deathtouch(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.DEATHTOUCH in card.keywords


class TestWitherbloomCostReduction:
    """cost_reduction() returns 1 per creature controlled, capped at 6."""

    def test_no_creatures_gives_zero_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 0

    def test_one_creature_gives_reduction_of_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[bear])
        assert card.cost_reduction(game) == 1

    def test_three_creatures_gives_reduction_of_three(self) -> None:
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

    def test_five_creatures_gives_reduction_of_five(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            Creature(name=f"Bear {i}", owner=p1, controller=p1,
                     base_power=2, base_toughness=2)
            for i in range(5)
        ]
        set_board_state(game, 0, battlefield=creatures)
        assert card.cost_reduction(game) == 5

    def test_cost_reduction_capped_at_six(self) -> None:
        """Reduction cannot exceed the generic portion of {6}{B}{G} = 6."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Create 10 creatures — more than the generic cost of 6
        creatures = [
            Creature(name=f"Bear {i}", owner=p1, controller=p1,
                     base_power=2, base_toughness=2)
            for i in range(10)
        ]
        set_board_state(game, 0, battlefield=creatures)
        # Should not exceed 6 (the generic portion)
        assert card.cost_reduction(game) <= 6

    def test_opponent_creatures_do_not_count(self) -> None:
        """Opponent's creatures should not reduce the cost."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        opp_creature = Creature(name="Opponent Bear", owner=p2, controller=p2,
                                base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[opp_creature])
        assert card.cost_reduction(game) == 0

    def test_non_creature_permanents_do_not_count(self) -> None:
        """Only creatures count for affinity; non-creature permanents are ignored."""
        from engine.card import Enchantment
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        enchantment = Enchantment(name="Some Aura", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[enchantment])
        assert card.cost_reduction(game) == 0

    def test_get_cost_reduction_clamps_to_zero(self) -> None:
        """get_cost_reduction() never returns negative."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        result = get_cost_reduction(game, card, p1)
        assert result >= 0


class TestWitherbloomGrantsAffinityToSpells:
    """When Witherbloom is on the battlefield, instant/sorcery spells
    you cast have affinity for creatures (cost reduced by 1 per creature)."""

    def test_register_replacement_effects_registers_something(self) -> None:
        """Witherbloom must register a continuous/replacement effect for the grant."""
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        before = len(game.replacement_manager._effects)
        card.register_replacement_effects(game)
        after = len(game.replacement_manager._effects)
        assert after > before

    def test_instant_gets_cost_reduction_with_creatures_when_witherbloom_in_play(self) -> None:
        """An instant's effective cost should be reduced by creature count when
        Witherbloom is on the battlefield and effects are registered."""
        game = create_game()
        p1 = game.players[0]
        # Witherbloom enters battlefield
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Place 3 creatures on the battlefield
        creatures = [
            Creature(name=f"Bear {i}", owner=p1, controller=p1,
                     base_power=2, base_toughness=2)
            for i in range(3)
        ]
        set_board_state(game, 0, battlefield=creatures + [witherbloom])
        witherbloom.register_replacement_effects(game)
        # Create an instant with generic mana cost
        instant = Instant(name="Fireball", owner=p1, controller=p1)
        instant.mana_cost = ManaCost.parse("{5}")
        instant.controller = p1
        # The instant should get a cost reduction of 3 (one per creature)
        reduction = get_cost_reduction(game, instant, p1)
        assert reduction == 3

    def test_sorcery_gets_cost_reduction_with_creatures_when_witherbloom_in_play(self) -> None:
        """A sorcery's effective cost should be reduced by creature count when
        Witherbloom is on the battlefield."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        creatures = [
            Creature(name=f"Bear {i}", owner=p1, controller=p1,
                     base_power=2, base_toughness=2)
            for i in range(2)
        ]
        set_board_state(game, 0, battlefield=creatures + [witherbloom])
        witherbloom.register_replacement_effects(game)
        sorcery = Sorcery(name="Fireball Sorcery", owner=p1, controller=p1)
        sorcery.mana_cost = ManaCost.parse("{4}")
        sorcery.controller = p1
        reduction = get_cost_reduction(game, sorcery, p1)
        assert reduction == 2

    def test_instant_gets_no_reduction_without_creatures_even_with_witherbloom(self) -> None:
        """With no creatures, an instant still gets 0 cost reduction even if
        Witherbloom is on the battlefield."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[witherbloom])
        witherbloom.register_replacement_effects(game)
        instant = Instant(name="Counterspell", owner=p1, controller=p1)
        instant.mana_cost = ManaCost.parse("{3}{U}")
        instant.controller = p1
        reduction = get_cost_reduction(game, instant, p1)
        assert reduction == 0

    def test_instant_gets_no_reduction_without_witherbloom_in_play(self) -> None:
        """Without Witherbloom on the battlefield, instants do not get creature affinity."""
        game = create_game()
        p1 = game.players[0]
        # 3 creatures on the board, but no Witherbloom
        creatures = [
            Creature(name=f"Bear {i}", owner=p1, controller=p1,
                     base_power=2, base_toughness=2)
            for i in range(3)
        ]
        set_board_state(game, 0, battlefield=creatures)
        instant = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        instant.mana_cost = ManaCost.parse("{3}")
        instant.controller = p1
        reduction = get_cost_reduction(game, instant, p1)
        assert reduction == 0

    def test_spell_cost_reduction_capped_at_generic_portion(self) -> None:
        """Granted affinity reduction is capped at the spell's generic mana cost."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        # 10 creatures but instant only costs {2}
        creatures = [
            Creature(name=f"Bear {i}", owner=p1, controller=p1,
                     base_power=2, base_toughness=2)
            for i in range(10)
        ]
        set_board_state(game, 0, battlefield=creatures + [witherbloom])
        witherbloom.register_replacement_effects(game)
        instant = Instant(name="Cheap Instant", owner=p1, controller=p1)
        instant.mana_cost = ManaCost.parse("{2}")
        instant.controller = p1
        reduction = get_cost_reduction(game, instant, p1)
        # Capped at {2} generic — never negative
        assert reduction <= 2
        assert reduction >= 0
