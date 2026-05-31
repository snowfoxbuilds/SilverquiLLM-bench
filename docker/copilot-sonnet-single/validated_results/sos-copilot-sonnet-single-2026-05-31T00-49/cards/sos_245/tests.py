"""Tests for sos_245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class TestWitherbloomProperties:
    def test_name(self) -> None:
        assert WitherbloomTheBalancer(owner=None).name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        assert WitherbloomTheBalancer(owner=None).mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_is_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_legendary(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_power_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_deathtouch(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.DEATHTOUCH in card.keywords


class TestWitherbloomSelfAffinityReduction:
    """Affinity for creatures: costs {1} less per creature controlled."""

    def test_cost_reduction_zero_no_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[])
        assert card.cost_reduction(game) == 0

    def test_cost_reduction_one_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear])
        assert card.cost_reduction(game) == 1

    def test_cost_reduction_three_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        bears = [Creature(name=f"Bear{i}", base_power=2, base_toughness=2,
                          owner=p1, controller=p1) for i in range(3)]
        set_board_state(game, 0, battlefield=bears)
        assert card.cost_reduction(game) == 3

    def test_cost_reduction_ignores_opponent_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        opp_bear = Creature(name="OppBear", base_power=2, base_toughness=2,
                            owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[])
        set_board_state(game, 1, battlefield=[opp_bear])
        assert card.cost_reduction(game) == 0


class TestWitherbloomSpellAffinityReduction:
    """Instants/sorceries cast by controller get affinity for creatures."""

    def test_get_spell_cost_reduction_for_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        bears = [Creature(name=f"Bear{i}", base_power=2, base_toughness=2,
                          owner=p1, controller=p1) for i in range(2)]
        for bear in bears:
            game.get_battlefield(p1).add(bear)
        spell = Instant(name="Bolt", owner=p1, controller=p1)
        reduction = card.get_spell_cost_reduction(game, spell, p1)
        assert reduction == 3  # 2 bears + witherbloom itself

    def test_get_spell_cost_reduction_for_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        spell = Sorcery(name="Ramp", owner=p1, controller=p1)
        # Witherbloom itself is a creature.
        reduction = card.get_spell_cost_reduction(game, spell, p1)
        assert reduction == 1  # just witherbloom

    def test_no_reduction_for_creature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        creature_spell = Creature(name="Bear", base_power=2, base_toughness=2,
                                  owner=p1, controller=p1)
        reduction = card.get_spell_cost_reduction(game, creature_spell, p1)
        assert reduction == 0  # creature spells don't get affinity

    def test_no_reduction_for_opponent_casting(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        spell = Instant(name="Bolt", owner=p2, controller=p2)
        reduction = card.get_spell_cost_reduction(game, spell, p2)
        assert reduction == 0


class TestWitherbloomCastingPipelineIntegration:
    """get_spell_cost_reduction is picked up by the casting pipeline."""

    def test_casting_pipeline_uses_witherbloom_reduction(self) -> None:
        from engine.casting import get_cost_reduction
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        # Spell with generic mana that can be reduced.
        spell = Instant(name="Costly Bolt", owner=p1, controller=p1)
        spell.mana_cost = ManaCost.parse("{5}")
        reduction = get_cost_reduction(game, spell, p1)
        # Witherbloom is the only creature → reduction = 1.
        assert reduction == 1
