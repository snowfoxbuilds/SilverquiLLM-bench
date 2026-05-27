"""Tests for SOS 4 — Together as One.

Verifies:
- Static card properties (name, mana cost, card type).
- Converge mechanic: ``colors_spent`` attribute defaults to 0 and drives X.
- Targeting: get_targets() declares requirements for a player and any target.
- Resolution effects: target player draws X cards, any target receives X
  damage, and the controller gains X life.
- Edge cases: X=0 (no colors spent) is a no-op; X=5 (all colors) applies
  maximum effects.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helper — populate a player's library with dummy cards for draw tests
# ---------------------------------------------------------------------------

def _populate_library(game, player_index: int, count: int) -> None:
    """Put *count* dummy Sorcery cards into a player's library."""
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for i in range(count):
        dummy = Sorcery(name=f"Dummy Card {i}", owner=player, controller=player)
        library.add(dummy)


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestTogetherAsOneProperties:
    """Static card data should match the SOS 4 spec."""

    def test_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"

    def test_mana_cost(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}")

    def test_card_type_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert CardType.SORCERY in card.card_types


# ---------------------------------------------------------------------------
# Converge — colors_spent attribute
# ---------------------------------------------------------------------------

class TestTogetherAsOneConverge:
    """Converge: colors_spent drives the value of X.

    The cast pipeline writes colors_spent from the payer's
    mana_pool.last_payment_colors; we set it directly to test the
    on_resolve logic in isolation (same pattern as FDN 205).
    """

    def test_colors_spent_defaults_to_zero(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.colors_spent == 0

    def test_x_equals_zero_when_no_colors_spent(self) -> None:
        """X=0 should result in no draws, no damage, and no life change."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        # Use p2 as the draw target; any target = p2 as well
        card.chosen_targets = [p2, p2]

        before_life_p1 = p1.life
        before_life_p2 = p2.life
        before_hand_p2 = len(p2.zones[Zone.HAND].get_all())

        card.on_resolve(game)

        assert p1.life == before_life_p1, "Controller should not gain life when X=0"
        assert p2.life == before_life_p2, "Target should not take damage when X=0"
        assert len(p2.zones[Zone.HAND].get_all()) == before_hand_p2, "Target should not draw when X=0"


# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------

class TestTogetherAsOneTargeting:
    """get_targets() must declare requirements for player draw and any target."""

    def test_returns_list_of_target_requirements(self) -> None:
        game = create_game()
        reqs = TogetherAsOne(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) >= 1

    def test_each_requirement_is_target_requirement_instance(self) -> None:
        game = create_game()
        reqs = TogetherAsOne(owner=None).get_targets(game)
        for req in reqs:
            assert isinstance(req, TargetRequirement)

    def test_has_player_target(self) -> None:
        """One requirement must accept a player as a valid target."""
        game = create_game()
        p1 = game.players[0]
        reqs = TogetherAsOne(owner=None).get_targets(game)
        # At least one req must accept a player
        assert any(req.filter_fn(p1) for req in reqs), (
            "No TargetRequirement accepts a player as target"
        )

    def test_has_any_target_requirement(self) -> None:
        """One requirement must accept either a player or a creature."""
        game = create_game()
        p2 = game.players[1]
        creature = Creature(
            name="Test Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        reqs = TogetherAsOne(owner=None).get_targets(game)
        accepts_creature = any(req.filter_fn(creature) for req in reqs)
        accepts_player = any(req.filter_fn(p2) for req in reqs)
        assert accepts_creature or accepts_player, (
            "No TargetRequirement accepts a player or creature for 'any target'"
        )


# ---------------------------------------------------------------------------
# Resolution — draws X cards
# ---------------------------------------------------------------------------

class TestTogetherAsOneDrawCards:
    """Target player draws X cards (X = colors_spent)."""

    def test_target_player_draws_correct_number_of_cards(self) -> None:
        """With colors_spent=3, the targeted player draws 3 cards."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        _populate_library(game, 1, 5)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p2, p2]  # draw target = p2, damage target = p2

        before = len(p2.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        after = len(p2.zones[Zone.HAND].get_all())
        assert after - before == 3

    def test_controller_draws_when_controller_is_target(self) -> None:
        """When the controller is the draw target, they draw X cards."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        _populate_library(game, 0, 5)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        card.chosen_targets = [p1, p2]  # draw target = p1, damage target = p2

        before = len(p1.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        after = len(p1.zones[Zone.HAND].get_all())
        assert after - before == 2

    def test_five_colors_draws_five_cards(self) -> None:
        """X=5 (maximum Converge) draws 5 cards."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        _populate_library(game, 0, 7)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 5
        card.chosen_targets = [p1, p2]

        before = len(p1.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        after = len(p1.zones[Zone.HAND].get_all())
        assert after - before == 5


# ---------------------------------------------------------------------------
# Resolution — deals X damage to any target
# ---------------------------------------------------------------------------

class TestTogetherAsOneDamage:
    """Together as One deals X damage to any target."""

    def test_deals_damage_to_target_player(self) -> None:
        """X=3 deals 3 damage to target player."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p1, p2]  # draw=p1, damage=p2

        before_life = p2.life
        card.on_resolve(game)
        assert p2.life == before_life - 3

    def test_deals_damage_to_target_creature(self) -> None:
        """X=2 deals 2 damage to a target creature."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        creature = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p2).add(creature)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        card.chosen_targets = [p1, creature]  # draw=p1, damage=creature

        card.on_resolve(game)
        assert creature.damage_marked == 2

    def test_zero_colors_deals_no_damage_to_player(self) -> None:
        """X=0 deals 0 damage (no life loss to target)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p1, p2]

        before_life = p2.life
        card.on_resolve(game)
        assert p2.life == before_life

    def test_five_colors_deals_five_damage(self) -> None:
        """X=5 deals 5 damage to target."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 5
        card.chosen_targets = [p1, p2]

        before_life = p2.life
        card.on_resolve(game)
        assert p2.life == before_life - 5


# ---------------------------------------------------------------------------
# Resolution — controller gains X life
# ---------------------------------------------------------------------------

class TestTogetherAsOneLifeGain:
    """The casting player (you) gains X life."""

    def test_controller_gains_x_life(self) -> None:
        """With colors_spent=3, controller gains 3 life."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p2, p2]

        before_life = p1.life
        card.on_resolve(game)
        assert p1.life == before_life + 3

    def test_zero_colors_no_life_gain(self) -> None:
        """X=0 means controller gains 0 life."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p2, p2]

        before_life = p1.life
        card.on_resolve(game)
        assert p1.life == before_life

    def test_five_colors_gains_five_life(self) -> None:
        """X=5 (maximum) controller gains 5 life."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 5
        card.chosen_targets = [p2, p2]

        before_life = p1.life
        card.on_resolve(game)
        assert p1.life == before_life + 5

    def test_life_gain_only_affects_controller_not_target(self) -> None:
        """Life gain goes to the controller (you), not the draw target or damage target."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        # damage target = p2 (loses life), draw target = p2
        card.chosen_targets = [p2, p2]

        before_p2_life = p2.life
        before_p1_life = p1.life
        card.on_resolve(game)

        # p1 gains 2 life, p2 loses 2 life
        assert p1.life == before_p1_life + 2
        assert p2.life == before_p2_life - 2


# ---------------------------------------------------------------------------
# Combined resolution — all three effects apply simultaneously
# ---------------------------------------------------------------------------

class TestTogetherAsOneAllEffects:
    """All three effects (draw, damage, life gain) apply on the same resolve."""

    def test_all_effects_apply_with_two_colors(self) -> None:
        """X=2: player draws 2, creature gets 2 damage, controller gains 2 life."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        _populate_library(game, 1, 5)

        creature = Creature(
            name="Damage Target",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
        )
        game.get_battlefield(p2).add(creature)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        card.chosen_targets = [p2, creature]  # draw target = p2, damage target = creature

        before_p1_life = p1.life
        before_p2_hand = len(p2.zones[Zone.HAND].get_all())

        card.on_resolve(game)

        assert p2.zones[Zone.HAND].get_all().__len__() - before_p2_hand == 2, "p2 should draw 2 cards"
        assert creature.damage_marked == 2, "creature should receive 2 damage"
        assert p1.life == before_p1_life + 2, "p1 should gain 2 life"
