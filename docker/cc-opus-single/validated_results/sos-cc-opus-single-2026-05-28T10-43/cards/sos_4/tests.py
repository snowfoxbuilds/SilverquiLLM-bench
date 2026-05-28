"""Tests for SOS 4 — Together as One.

Together as One is a {6} Sorcery with Converge:
  "Target player draws X cards, Together as One deals X damage to any target,
   and you gain X life, where X is the number of colors of mana spent to cast
   this spell."

Tests cover:
- Static card properties (name, mana cost, type)
- Targeting requirements (target player + any target)
- Converge interaction: X = number of colors of mana spent
- Card draw, damage, and life gain for various X values
- Edge cases: X=0 (all colorless), damage to creatures, opponent as draw target
"""

from __future__ import annotations

import pytest

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------


class TestTogetherAsOneProperties:
    """Static card data should match the SOS 4 spec."""

    def test_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)

    def test_has_sorcery_card_type(self) -> None:
        card = TogetherAsOne(owner=None)
        assert CardType.SORCERY in card.card_types

    def test_name(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"

    def test_mana_cost(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}")


# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------


class TestTogetherAsOneTargeting:
    """Together as One requires two targets:
    1. Target player (draws X cards)
    2. Any target (receives X damage — player or creature)
    """

    def test_get_targets_returns_two_requirements(self) -> None:
        game = create_game()
        card = TogetherAsOne(owner=game.players[0])
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 2

    def test_first_target_is_a_player(self) -> None:
        """The first target requirement should accept players."""
        game = create_game()
        card = TogetherAsOne(owner=game.players[0])
        reqs = card.get_targets(game)
        req = reqs[0]
        assert isinstance(req, TargetRequirement)
        # A player should be a legal target for card draw
        assert req.filter_fn(game.players[0]) is True
        assert req.filter_fn(game.players[1]) is True

    def test_second_target_accepts_player(self) -> None:
        """The second target (any target) should accept a player."""
        game = create_game()
        card = TogetherAsOne(owner=game.players[0])
        reqs = card.get_targets(game)
        req = reqs[1]
        assert isinstance(req, TargetRequirement)
        assert req.filter_fn(game.players[0]) is True

    def test_second_target_accepts_creature(self) -> None:
        """The second target (any target) should accept a creature."""
        game = create_game()
        card = TogetherAsOne(owner=game.players[0])
        reqs = card.get_targets(game)
        req = reqs[1]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        assert req.filter_fn(bear) is True


# ---------------------------------------------------------------------------
# Converge: on_resolve with varying X
# ---------------------------------------------------------------------------


class TestTogetherAsOneConvergeZeroColors:
    """When X=0 (all colorless mana spent), no draw, no damage, no life gain."""

    def test_zero_colors_no_cards_drawn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        # Simulate 0 colors spent (all colorless)
        card.colors_spent = []
        card.chosen_targets = [p1, p2]
        hand_before = len(game.get_hand(p1).get_all())
        card.on_resolve(game)
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after == hand_before

    def test_zero_colors_no_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = []
        card.chosen_targets = [p1, p2]
        life_before = p2.life
        card.on_resolve(game)
        assert p2.life == life_before

    def test_zero_colors_no_life_gain(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = []
        card.chosen_targets = [p2, p2]
        life_before = p1.life
        card.on_resolve(game)
        assert p1.life == life_before


class TestTogetherAsOneConvergeResolve:
    """Resolution effects scale with the number of colors of mana spent."""

    def _setup_with_colors(self, num_colors: int):
        """Create a game and card with the given number of colors spent.

        Returns (game, p1, p2, card).
        """
        from engine.types import Color
        all_colors = [Color.WHITE, Color.BLUE, Color.BLACK, Color.RED, Color.GREEN]
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = all_colors[:num_colors]
        return game, p1, p2, card

    def test_one_color_draws_one_card(self) -> None:
        """With 1 color of mana spent, target player draws 1 card."""
        game, p1, p2, card = self._setup_with_colors(1)
        # Put cards in p1's library so they can be drawn
        dummy = Creature(name="Dummy", base_power=1, base_toughness=1)
        dummy.owner = p1
        p1.zones[Zone.LIBRARY].add(dummy)
        card.chosen_targets = [p1, p2]
        hand_before = len(game.get_hand(p1).get_all())
        card.on_resolve(game)
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after - hand_before == 1

    def test_one_color_deals_one_damage(self) -> None:
        """With 1 color, deal 1 damage to the damage target."""
        game, p1, p2, card = self._setup_with_colors(1)
        card.chosen_targets = [p1, p2]
        life_before = p2.life
        card.on_resolve(game)
        assert p2.life == life_before - 1

    def test_one_color_gains_one_life(self) -> None:
        """With 1 color, controller gains 1 life."""
        game, p1, p2, card = self._setup_with_colors(1)
        card.chosen_targets = [p2, p2]
        life_before = p1.life
        card.on_resolve(game)
        assert p1.life == life_before + 1

    def test_three_colors_draws_three_cards(self) -> None:
        """With 3 colors of mana spent, target player draws 3 cards."""
        game, p1, p2, card = self._setup_with_colors(3)
        # Ensure library has enough cards
        for i in range(5):
            d = Creature(name=f"Dummy{i}", base_power=1, base_toughness=1)
            d.owner = p1
            p1.zones[Zone.LIBRARY].add(d)
        card.chosen_targets = [p1, p2]
        hand_before = len(game.get_hand(p1).get_all())
        card.on_resolve(game)
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after - hand_before == 3

    def test_three_colors_deals_three_damage(self) -> None:
        """With 3 colors, deal 3 damage to damage target."""
        game, p1, p2, card = self._setup_with_colors(3)
        card.chosen_targets = [p1, p2]
        life_before = p2.life
        card.on_resolve(game)
        assert p2.life == life_before - 3

    def test_three_colors_gains_three_life(self) -> None:
        """With 3 colors, controller gains 3 life."""
        game, p1, p2, card = self._setup_with_colors(3)
        card.chosen_targets = [p2, p2]
        life_before = p1.life
        card.on_resolve(game)
        assert p1.life == life_before + 3

    def test_five_colors_draws_five_cards(self) -> None:
        """With 5 colors (WUBRG), target player draws 5 cards."""
        game, p1, p2, card = self._setup_with_colors(5)
        for i in range(10):
            d = Creature(name=f"Dummy{i}", base_power=1, base_toughness=1)
            d.owner = p1
            p1.zones[Zone.LIBRARY].add(d)
        card.chosen_targets = [p1, p2]
        hand_before = len(game.get_hand(p1).get_all())
        card.on_resolve(game)
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after - hand_before == 5

    def test_five_colors_deals_five_damage(self) -> None:
        """With 5 colors, deal 5 damage to damage target."""
        game, p1, p2, card = self._setup_with_colors(5)
        card.chosen_targets = [p1, p2]
        life_before = p2.life
        card.on_resolve(game)
        assert p2.life == life_before - 5

    def test_five_colors_gains_five_life(self) -> None:
        """With 5 colors, controller gains 5 life."""
        game, p1, p2, card = self._setup_with_colors(5)
        card.chosen_targets = [p2, p2]
        life_before = p1.life
        card.on_resolve(game)
        assert p1.life == life_before + 5


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestTogetherAsOneEdgeCases:
    """Edge cases for Together as One resolution."""

    def test_damage_to_creature(self) -> None:
        """X damage can be dealt to a creature (any target)."""
        from engine.types import Color
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        bear = Creature(
            name="Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=5,
        )
        game.get_battlefield(p2).add(bear)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = [Color.WHITE, Color.BLUE, Color.BLACK]
        card.chosen_targets = [p1, bear]
        damage_before = bear.damage_marked
        card.on_resolve(game)
        assert bear.damage_marked == damage_before + 3

    def test_opponent_draws_cards(self) -> None:
        """Target player can be the opponent -- they draw the cards."""
        from engine.types import Color
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put cards in p2's library
        for i in range(5):
            d = Creature(name=f"Opp{i}", base_power=1, base_toughness=1)
            d.owner = p2
            p2.zones[Zone.LIBRARY].add(d)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = [Color.WHITE, Color.BLUE]
        card.chosen_targets = [p2, p1]  # opponent draws, self takes damage
        hand_before = len(game.get_hand(p2).get_all())
        card.on_resolve(game)
        hand_after = len(game.get_hand(p2).get_all())
        assert hand_after - hand_before == 2

    def test_controller_gains_life_not_target_player(self) -> None:
        """'You gain X life' means the controller, regardless of targets."""
        from engine.types import Color
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        for i in range(3):
            d = Creature(name=f"D{i}", base_power=1, base_toughness=1)
            d.owner = p2
            p2.zones[Zone.LIBRARY].add(d)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = [Color.RED, Color.GREEN]
        # Target player is opponent, damage target is also opponent
        card.chosen_targets = [p2, p2]
        p1_life_before = p1.life
        p2_life_before = p2.life
        card.on_resolve(game)
        # Controller (p1) gains 2 life
        assert p1.life == p1_life_before + 2
        # Opponent (p2) takes 2 damage
        assert p2.life == p2_life_before - 2

    def test_no_targets_is_noop(self) -> None:
        """If chosen_targets is empty/unset, resolution must not raise."""
        game = create_game()
        p1 = game.players[0]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = [ManaType.WHITE]
        # No chosen_targets set -- should not crash
        card.on_resolve(game)

    def test_all_three_effects_happen_together(self) -> None:
        """Draw, damage, and life gain all happen in one resolution with X=2."""
        from engine.types import Color
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Library cards for p1 to draw
        for i in range(5):
            d = Creature(name=f"Draw{i}", base_power=1, base_toughness=1)
            d.owner = p1
            p1.zones[Zone.LIBRARY].add(d)

        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = [Color.WHITE, Color.BLUE]
        card.chosen_targets = [p1, p2]

        p1_hand_before = len(game.get_hand(p1).get_all())
        p1_life_before = p1.life
        p2_life_before = p2.life

        card.on_resolve(game)

        # p1 draws 2
        assert len(game.get_hand(p1).get_all()) - p1_hand_before == 2
        # p2 takes 2 damage
        assert p2.life == p2_life_before - 2
        # p1 gains 2 life
        assert p1.life == p1_life_before + 2
