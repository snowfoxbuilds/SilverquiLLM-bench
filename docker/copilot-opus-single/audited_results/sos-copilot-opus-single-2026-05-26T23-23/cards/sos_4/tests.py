"""Tests for SOS 4 — Together as One.

Together as One is a {6} Sorcery with Converge:
"Target player draws X cards, Together as One deals X damage to any target,
and you gain X life, where X is the number of colors of mana spent to cast
this spell."

Tests cover:
- Static card properties (name, cost, type)
- Converge mechanic (colors_spent drives X)
- Card draw effect (target player draws X)
- Damage effect (any target takes X damage)
- Life gain effect (controller gains X life)
- Edge case: X=0 (no colors spent)
- Targeting requirements (two targets needed)
"""

from __future__ import annotations

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone
from test_utils import create_game


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


class TestTogetherAsOneConverge:
    """Converge: X equals the number of colors of mana spent to cast."""

    def test_colors_spent_defaults_to_zero(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.colors_spent == 0

    def test_colors_spent_can_be_set(self) -> None:
        card = TogetherAsOne(owner=None)
        card.colors_spent = 3
        assert card.colors_spent == 3


class TestTogetherAsOneTargeting:
    """get_targets() should advertise two targets: a player and any target."""

    def test_returns_target_requirements(self) -> None:
        game = create_game()
        card = TogetherAsOne(owner=None)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 2

    def test_first_target_is_player(self) -> None:
        """First target requirement should accept players (for card draw)."""
        game = create_game()
        card = TogetherAsOne(owner=None)
        reqs = card.get_targets(game)
        req = reqs[0]
        assert isinstance(req, TargetRequirement)
        # Player target should accept a player object
        assert req.filter_fn(game.players[0]) is True

    def test_second_target_is_any_target(self) -> None:
        """Second target requirement should accept creatures and players (any target)."""
        game = create_game()
        card = TogetherAsOne(owner=None)
        reqs = card.get_targets(game)
        req = reqs[1]
        assert isinstance(req, TargetRequirement)
        # 'any target' means creatures and players
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is True
        assert req.filter_fn(game.players[0]) is True


class TestTogetherAsOneResolution:
    """on_resolve applies all three effects based on colors_spent."""

    def test_draws_x_cards_for_target_player(self) -> None:
        """Target player draws X cards where X = colors_spent."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put cards in p2's library so they can draw
        from engine.card import CardImpl
        for i in range(5):
            lib_card = CardImpl(name=f"LibCard{i}", owner=p2)
            game.get_library(p2).add(lib_card)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        # Target player is p2 (first target), damage target is p1 (second target)
        card.chosen_targets = [p2, p1]
        hand_before = len(game.get_hand(p2).get_all())
        card.on_resolve(game)
        hand_after = len(game.get_hand(p2).get_all())
        assert hand_after - hand_before == 3

    def test_deals_x_damage_to_creature_target(self) -> None:
        """Together as One deals X damage to the second target (creature)."""
        game = create_game()
        p1 = game.players[0]

        bear = Creature(
            name="Bear", owner=p1, controller=p1,
            base_power=2, base_toughness=5,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p1, bear]
        card.on_resolve(game)
        assert bear.damage_taken == 3

    def test_deals_x_damage_to_player_target(self) -> None:
        """Together as One deals X damage to a player (any target)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 4
        card.chosen_targets = [p1, p2]
        card.on_resolve(game)
        # p2 starts at 20, takes 4 damage
        assert p2.life == 16

    def test_controller_gains_x_life(self) -> None:
        """The controller (you) gains X life."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p1, p2]
        card.on_resolve(game)
        # p1 starts at 20, gains 3 life
        assert p1.life == 23

    def test_zero_colors_spent_no_effect(self) -> None:
        """When X=0, no cards drawn, no damage, no life gained."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p2, p1]
        card.on_resolve(game)
        assert p1.life == 20  # no life gain
        assert p2.life == 20  # no damage to p2 (p1 was damage target)
        assert len(game.get_hand(p2).get_all()) == 0  # no draws

    def test_five_colors_all_effects(self) -> None:
        """Maximum converge with 5 colors: draw 5, deal 5, gain 5."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put cards in p1's library so they can draw
        from engine.card import CardImpl
        for i in range(5):
            lib_card = CardImpl(name=f"LibCard{i}", owner=p1)
            game.get_library(p1).add(lib_card)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 5
        card.chosen_targets = [p1, p2]
        card.on_resolve(game)
        # Controller (p1) gains 5 life
        assert p1.life == 25
        # Damage target (p2) takes 5 damage
        assert p2.life == 15
        # Target player (p1) draws 5 cards
        assert len(game.get_hand(p1).get_all()) == 5

    def test_no_targets_is_noop(self) -> None:
        """If chosen_targets is empty/unset, resolution must not crash."""
        game = create_game()
        p1 = game.players[0]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        # No targets chosen — should handle gracefully
        card.on_resolve(game)

    def test_damage_target_and_draw_target_can_differ(self) -> None:
        """Draw target and damage target can be different players."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        from engine.card import CardImpl
        for i in range(3):
            lib_card = CardImpl(name=f"LibCard{i}", owner=p2)
            game.get_library(p2).add(lib_card)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        # p2 draws, p2 also takes damage
        card.chosen_targets = [p2, p2]
        card.on_resolve(game)
        # p2 draws 2 (target player)
        assert len(game.get_hand(p2).get_all()) == 2
        # p2 takes 2 damage
        assert p2.life == 18
        # p1 (controller) gains 2 life
        assert p1.life == 22
