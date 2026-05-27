"""Tests for SOS 4 — Together as One.

Covers the Converge mechanic (colors_spent drives X) and the triple
effect on resolution: target player draws X cards, the spell deals X
damage to any target, and the controller gains X life.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------

class TestTogetherAsOneProperties:
    """Static card data must match the SOS 4 spec."""

    def test_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)

    def test_card_type_contains_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert CardType.SORCERY in card.card_types

    def test_name(self) -> None:
        assert TogetherAsOne(owner=None).name == "Together as One"

    def test_mana_cost(self) -> None:
        assert TogetherAsOne(owner=None).mana_cost == ManaCost.parse("{6}")

    def test_not_creature(self) -> None:
        card = TogetherAsOne(owner=None)
        assert not isinstance(card, Creature)
        assert CardType.CREATURE not in card.card_types

    def test_not_instant(self) -> None:
        card = TogetherAsOne(owner=None)
        assert CardType.INSTANT not in card.card_types


# ---------------------------------------------------------------------------
# Converge — colors_spent attribute
# ---------------------------------------------------------------------------

class TestTogetherAsOneConverge:
    """colors_spent initialises to 0 and on_resolve reads it for X.

    The cast pipeline writes colors_spent onto the card after mana payment.
    Tests bypass the cast pipeline and set it directly.
    """

    def test_colors_spent_defaults_to_zero(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.colors_spent == 0

    def test_zero_colors_no_life_gain(self) -> None:
        """When no colors are spent (X=0) controller gains no life."""
        game = create_game()
        p1 = game.players[0]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p1, p1]   # targets present but X=0
        before_life = p1.life
        card.on_resolve(game)
        assert p1.life == before_life

    def test_zero_colors_no_damage(self) -> None:
        """When X=0 the damage target receives no damage."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p2, p2]
        before_life = p2.life
        card.on_resolve(game)
        assert p2.life == before_life

    def test_zero_colors_no_cards_drawn(self) -> None:
        """When X=0 no cards are drawn by the target player."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Give p2 cards in library so a draw would be possible
        set_board_state(game, 1, hand=[], graveyard=[])
        from engine.card import CardImpl
        for _ in range(5):
            dummy = CardImpl(name="Dummy")
            p2.zones[Zone.LIBRARY].add(dummy)
        before_hand = len(p2.zones[Zone.HAND].get_all())
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 0
        card.chosen_targets = [p2, p1]
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == before_hand


# ---------------------------------------------------------------------------
# Resolution effects — each colour count
# ---------------------------------------------------------------------------

class TestTogetherAsOneDrawEffect:
    """Target player draws X cards where X = colors_spent."""

    def _seed_library(self, player, game, count: int = 10) -> None:
        """Put *count* dummy cards in the player's library."""
        from engine.card import CardImpl
        for i in range(count):
            dummy = CardImpl(name=f"Dummy{i}")
            player.zones[Zone.LIBRARY].add(dummy)

    def test_one_color_draws_one_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        self._seed_library(p2, game)
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 1
        card.chosen_targets = [p2, p2]   # [draw_target, damage_target]
        before = len(p2.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == before + 1

    def test_three_colors_draws_three_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        self._seed_library(p2, game)
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p2, p2]
        before = len(p2.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == before + 3

    def test_five_colors_draws_five_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        self._seed_library(p2, game, count=10)
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 5
        card.chosen_targets = [p2, p2]
        before = len(p2.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        assert len(p2.zones[Zone.HAND].get_all()) == before + 5

    def test_draw_target_can_be_controller(self) -> None:
        """Controller can target themselves to draw."""
        game = create_game()
        p1 = game.players[0]
        self._seed_library(p1, game)
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        card.chosen_targets = [p1, game.players[1]]  # p1 draws, p2 takes damage
        before = len(p1.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        assert len(p1.zones[Zone.HAND].get_all()) == before + 2


class TestTogetherAsOneDamageEffect:
    """The spell deals X damage to any target (player or creature)."""

    def test_one_color_deals_one_damage_to_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 1
        card.chosen_targets = [p2, p2]
        before_life = p2.life
        card.on_resolve(game)
        assert p2.life == before_life - 1

    def test_three_colors_deals_three_damage_to_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p2, p2]
        before_life = p2.life
        card.on_resolve(game)
        assert p2.life == before_life - 3

    def test_damage_can_target_creature(self) -> None:
        """X damage is marked on a creature target."""
        game = create_game()
        p1 = game.players[0]
        target_creature = Creature(
            name="Test Bear",
            owner=game.players[1],
            controller=game.players[1],
            base_power=2,
            base_toughness=4,
        )
        game.get_battlefield(game.players[1]).add(target_creature)
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        card.chosen_targets = [game.players[1], target_creature]
        card.on_resolve(game)
        assert target_creature.damage_marked == 2

    def test_damage_target_is_separate_from_draw_target(self) -> None:
        """Damage target and draw target are independently resolved."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # p1 draws, p2 takes damage
        from engine.card import CardImpl
        for i in range(5):
            p1.zones[Zone.LIBRARY].add(CardImpl(name=f"D{i}"))
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 2
        card.chosen_targets = [p1, p2]
        before_p2_life = p2.life
        before_p1_hand = len(p1.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        # p1 draws 2
        assert len(p1.zones[Zone.HAND].get_all()) == before_p1_hand + 2
        # p2 takes 2 damage
        assert p2.life == before_p2_life - 2


class TestTogetherAsOneLifeGainEffect:
    """Controller gains X life where X = colors_spent."""

    def test_one_color_gains_one_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 1
        card.chosen_targets = [p2, p2]
        before_life = p1.life
        card.on_resolve(game)
        assert p1.life == before_life + 1

    def test_three_colors_gains_three_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        card.chosen_targets = [p2, p2]
        before_life = p1.life
        card.on_resolve(game)
        assert p1.life == before_life + 3

    def test_five_colors_gains_five_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 5
        card.chosen_targets = [p2, p2]
        before_life = p1.life
        card.on_resolve(game)
        assert p1.life == before_life + 5

    def test_life_gain_accrues_to_controller_not_draw_target(self) -> None:
        """It's "you gain X life" — controller gains, not the draw target."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        from engine.card import CardImpl
        for i in range(5):
            p2.zones[Zone.LIBRARY].add(CardImpl(name=f"D{i}"))
        card = TogetherAsOne(owner=p1, controller=p1)
        card.colors_spent = 3
        # p2 is the draw target; p1 is the controller and should gain life
        card.chosen_targets = [p2, p2]
        before_p1 = p1.life
        before_p2 = p2.life
        card.on_resolve(game)
        assert p1.life == before_p1 + 3   # controller gained
        assert p2.life != before_p2 + 3   # draw target did NOT gain (may have lost from damage)


# ---------------------------------------------------------------------------
# Targeting declaration
# ---------------------------------------------------------------------------

class TestTogetherAsOneTargeting:
    """get_targets() must declare the spell's two target requirements."""

    def test_get_targets_returns_list(self) -> None:
        game = create_game()
        result = TogetherAsOne(owner=None).get_targets(game)
        assert isinstance(result, list)

    def test_get_targets_returns_two_requirements(self) -> None:
        game = create_game()
        reqs = TogetherAsOne(owner=None).get_targets(game)
        assert len(reqs) == 2

    def test_each_requirement_is_target_requirement(self) -> None:
        game = create_game()
        reqs = TogetherAsOne(owner=None).get_targets(game)
        for req in reqs:
            assert isinstance(req, TargetRequirement)

    def test_first_target_accepts_player(self) -> None:
        """First requirement is 'target player' — must accept a Player."""
        game = create_game()
        req = TogetherAsOne(owner=None).get_targets(game)[0]
        player = game.players[0]
        assert req.filter_fn(player) is True

    def test_first_target_rejects_creature(self) -> None:
        """First requirement (player draw) must not accept a bare creature."""
        game = create_game()
        req = TogetherAsOne(owner=None).get_targets(game)[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        assert req.filter_fn(creature) is False

    def test_second_target_accepts_player(self) -> None:
        """Second requirement is 'any target' — must accept a player."""
        game = create_game()
        req = TogetherAsOne(owner=None).get_targets(game)[1]
        player = game.players[0]
        assert req.filter_fn(player) is True

    def test_second_target_accepts_creature(self) -> None:
        """Second requirement is 'any target' — must also accept a creature."""
        game = create_game()
        req = TogetherAsOne(owner=None).get_targets(game)[1]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is True

    def test_first_requirement_zone_is_appropriate(self) -> None:
        """Player targets have no battlefield zone requirement — check not LIBRARY."""
        game = create_game()
        req = TogetherAsOne(owner=None).get_targets(game)[0]
        # Zone should not be LIBRARY (players aren't in a zone like LIBRARY)
        assert req.zone != Zone.LIBRARY
