"""Tests for SOS 4 — Together as One (Converge Sorcery).

Oracle text:
  Converge — Target player draws X cards, Together as One deals X damage to
  any target, and you gain X life, where X is the number of colors of mana
  spent to cast this spell.

Tests cover:
- Card properties (is Sorcery, name, mana cost)
- Converge mechanic: X derived from colors_spent on the card
- Draw effect: target player draws X cards from library
- Damage effect: deals X damage to any target (creature or player)
- Life gain effect: controller gains X life
- Edge cases: X=0 (colorless only), X=1 through X=5 colors
- Targeting: get_targets() returns specs for 2 targets (draw target: player,
  damage target: any creature or player)
"""

from __future__ import annotations

import pytest

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.game import draw_card
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helper: put X cards in a player's library
# ---------------------------------------------------------------------------

def _fill_library(game, player_index: int, count: int) -> None:
    """Add *count* dummy cards to a player's library for draw tests."""
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for i in range(count):
        dummy = Creature(name=f"Dummy_{i}", base_power=1, base_toughness=1)
        dummy.owner = player
        dummy.controller = player
        library.add(dummy)


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

class TestTogetherAsOneProperties:
    """Static card data must match the sos_4 spec."""

    def test_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)

    def test_card_type_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert CardType.SORCERY in card.card_types

    def test_name(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"

    def test_mana_cost(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}")

    def test_mana_cost_cmc(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.mana_cost.cmc == 6


# ---------------------------------------------------------------------------
# Targeting (get_targets)
# ---------------------------------------------------------------------------

class TestTogetherAsOneTargets:
    """Together as One has two explicit targets: a player for drawing and any
    target for damage."""

    def test_get_targets_returns_list(self) -> None:
        game = create_game()
        card = TogetherAsOne(owner=None)
        result = card.get_targets(game)
        assert isinstance(result, list)

    def test_get_targets_returns_two_requirements(self) -> None:
        """Needs a 'target player' for draw and 'any target' for damage."""
        game = create_game()
        card = TogetherAsOne(owner=None)
        result = card.get_targets(game)
        assert len(result) == 2

    def test_target_player_filter_accepts_player(self) -> None:
        """First target (for drawing) must accept players."""
        game = create_game()
        card = TogetherAsOne(owner=None)
        reqs = card.get_targets(game)
        draw_req = reqs[0]
        p1 = game.players[0]
        assert draw_req.filter_fn(p1) is True

    def test_damage_target_filter_accepts_player(self) -> None:
        """Second target (for damage) must accept players."""
        game = create_game()
        card = TogetherAsOne(owner=None)
        reqs = card.get_targets(game)
        dmg_req = reqs[1]
        p2 = game.players[1]
        assert dmg_req.filter_fn(p2) is True

    def test_damage_target_filter_accepts_creature(self) -> None:
        """Second target (for damage) must accept creatures."""
        game = create_game()
        p1 = game.players[0]
        card = TogetherAsOne(owner=None)
        reqs = card.get_targets(game)
        dmg_req = reqs[1]
        creature = Creature(name="Test Bear", base_power=2, base_toughness=2)
        creature.owner = p1
        creature.controller = p1
        assert dmg_req.filter_fn(creature) is True


# ---------------------------------------------------------------------------
# Converge: X == number of colors spent
# ---------------------------------------------------------------------------

class TestTogetherAsOneConverge:
    """X equals len(card.colors_spent) at resolution time."""

    def _make_spell(self, game, player_index: int, colors_spent: list) -> TogetherAsOne:
        """Build a spell with colors_spent pre-set, owned by player at index."""
        p = game.players[player_index]
        card = TogetherAsOne(owner=p, controller=p)
        card.colors_spent = colors_spent  # type: ignore[attr-defined]
        return card

    def test_x_equals_zero_draws_zero_cards(self) -> None:
        """X=0 → target player draws 0 cards (hand unchanged)."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        _fill_library(game, 1, 5)
        card = self._make_spell(game, 0, [])
        card.chosen_targets = [p1, p1]
        initial_hand = len(game.get_hand(p1).get_all())
        card.on_resolve(game)
        assert len(game.get_hand(p1).get_all()) == initial_hand

    def test_x_equals_zero_deals_zero_damage(self) -> None:
        """X=0 → 0 damage dealt to target creature."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = self._make_spell(game, 0, [])
        card.chosen_targets = [p0, creature]
        initial_damage = creature.damage_marked
        card.on_resolve(game)
        assert creature.damage_marked == initial_damage

    def test_x_equals_zero_controller_gains_zero_life(self) -> None:
        """X=0 → controller gains 0 life."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        card = self._make_spell(game, 0, [])
        card.chosen_targets = [p1, p1]
        initial_life = p0.life
        card.on_resolve(game)
        assert p0.life == initial_life

    def test_x_equals_one_draws_one_card(self) -> None:
        """X=1 → target player draws 1 card."""
        from engine.types import Color
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        _fill_library(game, 1, 5)
        card = self._make_spell(game, 0, [Color.WHITE])
        card.chosen_targets = [p1, p1]
        initial_hand = len(game.get_hand(p1).get_all())
        card.on_resolve(game)
        assert len(game.get_hand(p1).get_all()) == initial_hand + 1

    def test_x_equals_one_deals_one_damage_to_player(self) -> None:
        """X=1 → deal 1 damage to target player."""
        from engine.types import Color
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        _fill_library(game, 1, 5)
        card = self._make_spell(game, 0, [Color.WHITE])
        card.chosen_targets = [p0, p1]
        initial_life = p1.life
        card.on_resolve(game)
        assert p1.life == initial_life - 1

    def test_x_equals_one_controller_gains_one_life(self) -> None:
        """X=1 → controller gains 1 life."""
        from engine.types import Color
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        _fill_library(game, 1, 5)
        card = self._make_spell(game, 0, [Color.WHITE])
        card.chosen_targets = [p1, p1]
        initial_life = p0.life
        card.on_resolve(game)
        assert p0.life == initial_life + 1

    def test_x_equals_two_draws_two_cards(self) -> None:
        """X=2 → target player draws 2 cards."""
        from engine.types import Color
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        _fill_library(game, 1, 5)
        card = self._make_spell(game, 0, [Color.WHITE, Color.BLUE])
        card.chosen_targets = [p1, p1]
        initial_hand = len(game.get_hand(p1).get_all())
        card.on_resolve(game)
        assert len(game.get_hand(p1).get_all()) == initial_hand + 2

    def test_x_equals_two_deals_two_damage_to_creature(self) -> None:
        """X=2 → deal 2 damage to target creature."""
        from engine.types import Color
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        creature = Creature(name="Bear", base_power=2, base_toughness=5)
        set_board_state(game, 1, battlefield=[creature])
        _fill_library(game, 0, 5)
        card = self._make_spell(game, 0, [Color.WHITE, Color.BLACK])
        card.chosen_targets = [p0, creature]
        card.on_resolve(game)
        assert creature.damage_marked == 2

    def test_x_equals_two_controller_gains_two_life(self) -> None:
        """X=2 → controller gains 2 life."""
        from engine.types import Color
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        _fill_library(game, 1, 5)
        card = self._make_spell(game, 0, [Color.RED, Color.GREEN])
        card.chosen_targets = [p1, p1]
        initial_life = p0.life
        card.on_resolve(game)
        assert p0.life == initial_life + 2

    def test_x_equals_three_all_effects(self) -> None:
        """X=3 → draw 3, deal 3, gain 3."""
        from engine.types import Color
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        _fill_library(game, 1, 5)
        creature = Creature(name="Big Bear", base_power=4, base_toughness=10)
        set_board_state(game, 1, battlefield=[creature])
        # re-fill library since set_board_state clears it
        _fill_library(game, 1, 5)
        card = self._make_spell(game, 0, [Color.WHITE, Color.BLUE, Color.BLACK])
        card.chosen_targets = [p1, creature]
        initial_hand = len(game.get_hand(p1).get_all())
        initial_life = p0.life
        card.on_resolve(game)
        assert len(game.get_hand(p1).get_all()) == initial_hand + 3
        assert creature.damage_marked == 3
        assert p0.life == initial_life + 3

    def test_x_equals_five_all_effects(self) -> None:
        """X=5 → draw 5, deal 5, gain 5 (maximum colors)."""
        from engine.types import Color
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        _fill_library(game, 1, 10)
        card = self._make_spell(
            game, 0,
            [Color.WHITE, Color.BLUE, Color.BLACK, Color.RED, Color.GREEN]
        )
        card.chosen_targets = [p1, p1]
        initial_hand = len(game.get_hand(p1).get_all())
        initial_life = p0.life
        initial_p1_life = p1.life
        card.on_resolve(game)
        assert len(game.get_hand(p1).get_all()) == initial_hand + 5
        assert p1.life == initial_p1_life - 5
        assert p0.life == initial_life + 5


# ---------------------------------------------------------------------------
# Damage targets variety
# ---------------------------------------------------------------------------

class TestTogetherAsOneDamageTarget:
    """Damage may target any creature or player."""

    def test_damage_kills_creature_with_lethal(self) -> None:
        """X damage marks on a creature with equal toughness → SBA kills it."""
        from engine.types import Color
        from engine.state_based_actions import resolve_state_based_actions
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        creature = Creature(name="Fragile", base_power=2, base_toughness=3)
        set_board_state(game, 1, battlefield=[creature])
        _fill_library(game, 0, 5)
        card = TogetherAsOne(owner=p0, controller=p0)
        card.colors_spent = [Color.WHITE, Color.BLUE, Color.BLACK]  # type: ignore[attr-defined]
        card.chosen_targets = [p0, creature]
        card.on_resolve(game)
        # Creature has 3 damage marked on 3-toughness — check SBA kills it
        resolve_state_based_actions(game)
        bf = game.get_battlefield(p1).get_all()
        assert creature not in bf

    def test_damage_targets_opponent_player(self) -> None:
        """X=2 damage to opponent player reduces their life."""
        from engine.types import Color
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        _fill_library(game, 0, 5)
        card = TogetherAsOne(owner=p0, controller=p0)
        card.colors_spent = [Color.RED, Color.GREEN]  # type: ignore[attr-defined]
        card.chosen_targets = [p0, p1]
        card.on_resolve(game)
        assert p1.life == 20 - 2

    def test_damage_targets_self_player(self) -> None:
        """Damage target can be the casting player themselves ('any target')."""
        from engine.types import Color
        game = create_game()
        p0 = game.players[0]
        _fill_library(game, 0, 5)
        card = TogetherAsOne(owner=p0, controller=p0)
        card.colors_spent = [Color.RED]  # type: ignore[attr-defined]
        card.chosen_targets = [p0, p0]
        initial_life = p0.life
        # Life gain from converge also applies — net is +1 gain -1 damage
        card.on_resolve(game)
        # Gain 1 life AND take 1 damage: net unchanged from initial
        assert p0.life == initial_life + 1 - 1


# ---------------------------------------------------------------------------
# Draw goes to target player (not necessarily controller)
# ---------------------------------------------------------------------------

class TestTogetherAsOneDrawTarget:
    """The draw effect targets a specific player, not necessarily the controller."""

    def test_draws_go_to_target_player_not_controller(self) -> None:
        """If target player is opponent, cards go to opponent's hand."""
        from engine.types import Color
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        _fill_library(game, 1, 5)  # only p1 has library cards
        card = TogetherAsOne(owner=p0, controller=p0)
        card.colors_spent = [Color.BLUE, Color.WHITE]  # type: ignore[attr-defined]
        # Draw target = p1 (opponent), damage target = p1
        card.chosen_targets = [p1, p1]
        initial_p1_hand = len(game.get_hand(p1).get_all())
        initial_p0_hand = len(game.get_hand(p0).get_all())
        card.on_resolve(game)
        assert len(game.get_hand(p1).get_all()) == initial_p1_hand + 2
        # Controller's hand should NOT grow
        assert len(game.get_hand(p0).get_all()) == initial_p0_hand
