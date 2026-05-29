"""Tests for sos_4 — Together as One.

Converge sorcery: target player draws X cards, deals X damage to any target,
you gain X life, where X = number of colors of mana spent to cast this spell.

Test coverage:
- Static card properties (name, mana cost, type)
- get_targets() returns two TargetRequirements
- X=0: 0 damage, 0 cards drawn, 0 life gained
- X=1: 1 damage, 1 card drawn, 1 life gained
- X=5: 5 damage, 5 cards drawn, 5 life gained
- Damage targeting a creature (damage_marked)
- Damage targeting a player (life reduction)
- Target player (not caster) draws the cards
- Casting player gains life (not target player)
- Colorless mana does not count toward X
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_4.card_impl import TogetherAsOne
from engine.card import Creature, Sorcery
from engine.types import (
    CardType,
    Color,
    ManaCost,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


def _add_library_cards(game: Any, player_index: int, count: int) -> list[Any]:
    """Add `count` dummy cards to the given player's library for drawing."""
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    cards = []
    for i in range(count):
        c = Sorcery(name=f"LibraryCard_{i}", owner=player, controller=player)
        library.add(c)
        cards.append(c)
    return cards


class TestTogetherAsOneProperties:
    """Static card data should match the sos_4 spec."""

    def test_name(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.name == "Together as One"

    def test_mana_cost(self) -> None:
        card = TogetherAsOne(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}")

    def test_is_sorcery(self) -> None:
        card = TogetherAsOne(owner=None)
        assert isinstance(card, Sorcery)

    def test_has_sorcery_card_type(self) -> None:
        card = TogetherAsOne(owner=None)
        assert CardType.SORCERY in card.card_types


class TestTogetherAsOneTargets:
    """get_targets() should advertise two requirements: target player and any target."""

    def test_get_targets_returns_list(self) -> None:
        game = create_game()
        card = TogetherAsOne(owner=None)
        result = card.get_targets(game)
        assert isinstance(result, list)

    def test_get_targets_returns_two_requirements(self) -> None:
        game = create_game()
        card = TogetherAsOne(owner=None)
        reqs = card.get_targets(game)
        assert len(reqs) == 2

    def test_get_targets_are_target_requirements(self) -> None:
        game = create_game()
        card = TogetherAsOne(owner=None)
        reqs = card.get_targets(game)
        for req in reqs:
            assert isinstance(req, TargetRequirement)


class TestTogetherAsOneXEqualsZero:
    """When 0 colors of mana were spent (X=0): no effect."""

    def test_x_zero_no_damage_to_creature(self) -> None:
        """X=0 deals 0 damage — creature should be unharmed."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        creature = Creature(
            name="Goblin",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p2).add(creature)

        _add_library_cards(game, 0, 5)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = []  # no colors → X=0
        spell.chosen_targets = [p1, creature]
        before_damage = creature.damage_marked
        spell.on_resolve(game)

        assert creature.damage_marked == before_damage

    def test_x_zero_no_life_loss_to_player_target(self) -> None:
        """X=0 deals 0 damage — player target's life unchanged."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        _add_library_cards(game, 0, 5)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = []  # no colors → X=0
        spell.chosen_targets = [p1, p2]
        before_life = p2.life
        spell.on_resolve(game)

        assert p2.life == before_life

    def test_x_zero_no_cards_drawn(self) -> None:
        """X=0 draws 0 cards — target player's hand size unchanged."""
        game = create_game()
        p1 = game.players[0]

        _add_library_cards(game, 0, 5)
        creature = Creature(name="Bear", owner=p1, controller=p1,
                            base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(creature)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = []
        spell.chosen_targets = [p1, creature]
        before_hand_size = len(game.get_hand(p1).get_all())
        spell.on_resolve(game)

        assert len(game.get_hand(p1).get_all()) == before_hand_size

    def test_x_zero_no_life_gained_by_caster(self) -> None:
        """X=0 gains 0 life for the caster."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        _add_library_cards(game, 0, 5)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = []
        spell.chosen_targets = [p1, p2]
        before_life = p1.life
        spell.on_resolve(game)

        assert p1.life == before_life


class TestTogetherAsOneXEqualsOne:
    """When 1 color of mana was spent (X=1): 1 damage, 1 card, 1 life."""

    def test_x_one_deals_one_damage_to_creature(self) -> None:
        """X=1 deals 1 damage to the creature target."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        creature = Creature(
            name="Goblin",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=4,
        )
        game.get_battlefield(p2).add(creature)

        _add_library_cards(game, 0, 5)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.RED]  # one color → X=1
        spell.chosen_targets = [p1, creature]
        before_damage = creature.damage_marked
        spell.on_resolve(game)

        assert creature.damage_marked == before_damage + 1

    def test_x_one_deals_one_damage_to_player(self) -> None:
        """X=1 deals 1 damage to a player target."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        _add_library_cards(game, 0, 5)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.BLUE]
        spell.chosen_targets = [p1, p2]
        before_life = p2.life
        spell.on_resolve(game)

        assert p2.life == before_life - 1

    def test_x_one_draws_one_card(self) -> None:
        """X=1 draws 1 card for the target player."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        _add_library_cards(game, 0, 5)
        creature = Creature(name="Bear", owner=p2, controller=p2,
                            base_power=2, base_toughness=2)
        game.get_battlefield(p2).add(creature)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.GREEN]
        spell.chosen_targets = [p1, creature]
        before_hand_size = len(game.get_hand(p1).get_all())
        spell.on_resolve(game)

        assert len(game.get_hand(p1).get_all()) == before_hand_size + 1

    def test_x_one_gains_one_life_for_caster(self) -> None:
        """X=1 gains 1 life for the casting player."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        _add_library_cards(game, 0, 5)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.WHITE]
        spell.chosen_targets = [p1, p2]
        before_life = p1.life
        spell.on_resolve(game)

        assert p1.life == before_life + 1


class TestTogetherAsOneXEqualsFive:
    """When all 5 colors of mana are spent (X=5): full effect."""

    def test_x_five_deals_five_damage_to_creature(self) -> None:
        """X=5 deals 5 damage to creature target."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        creature = Creature(
            name="Dragon",
            owner=p2,
            controller=p2,
            base_power=5,
            base_toughness=10,
        )
        game.get_battlefield(p2).add(creature)

        _add_library_cards(game, 0, 10)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.WHITE, Color.BLUE, Color.BLACK, Color.RED, Color.GREEN]
        spell.chosen_targets = [p1, creature]
        before_damage = creature.damage_marked
        spell.on_resolve(game)

        assert creature.damage_marked == before_damage + 5

    def test_x_five_deals_five_damage_to_player(self) -> None:
        """X=5 deals 5 damage to player target."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        _add_library_cards(game, 0, 10)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.WHITE, Color.BLUE, Color.BLACK, Color.RED, Color.GREEN]
        spell.chosen_targets = [p1, p2]
        before_life = p2.life
        spell.on_resolve(game)

        assert p2.life == before_life - 5

    def test_x_five_draws_five_cards(self) -> None:
        """X=5 draws 5 cards for the target player."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        _add_library_cards(game, 0, 10)
        creature = Creature(name="Bear", owner=p2, controller=p2,
                            base_power=2, base_toughness=2)
        game.get_battlefield(p2).add(creature)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.WHITE, Color.BLUE, Color.BLACK, Color.RED, Color.GREEN]
        spell.chosen_targets = [p1, creature]
        before_hand_size = len(game.get_hand(p1).get_all())
        spell.on_resolve(game)

        assert len(game.get_hand(p1).get_all()) == before_hand_size + 5

    def test_x_five_gains_five_life_for_caster(self) -> None:
        """X=5 gains 5 life for the casting player."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        _add_library_cards(game, 0, 10)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.WHITE, Color.BLUE, Color.BLACK, Color.RED, Color.GREEN]
        spell.chosen_targets = [p1, p2]
        before_life = p1.life
        spell.on_resolve(game)

        assert p1.life == before_life + 5


class TestTogetherAsOneConvergeRules:
    """Converge-specific rules for X calculation."""

    def test_x_equals_number_of_distinct_colors(self) -> None:
        """Duplicate colors count only once for X."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        _add_library_cards(game, 0, 5)

        spell = TogetherAsOne(owner=p1, controller=p1)
        # Two colors → X=2, not 3 even if mana pool had 3 pips of same color
        spell.colors_spent = [Color.RED, Color.GREEN]
        spell.chosen_targets = [p1, p2]
        before_life_p1 = p1.life
        before_life_p2 = p2.life
        spell.on_resolve(game)

        assert p2.life == before_life_p2 - 2
        assert p1.life == before_life_p1 + 2

    def test_x_max_is_five_colors(self) -> None:
        """X is at most 5 (one per color), even if colors_spent lists all 5."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        _add_library_cards(game, 0, 10)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.WHITE, Color.BLUE, Color.BLACK, Color.RED, Color.GREEN]
        spell.chosen_targets = [p1, p2]
        before_life = p1.life
        spell.on_resolve(game)

        # Exactly 5 gained (the max)
        assert p1.life == before_life + 5

    def test_colorless_mana_does_not_count(self) -> None:
        """Colorless mana pips don't contribute to X (Converge counts colors only)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        _add_library_cards(game, 0, 5)

        spell = TogetherAsOne(owner=p1, controller=p1)
        # Even though {6} was paid, if all was colorless, colors_spent is empty
        spell.colors_spent = []  # colorless payment = X=0
        spell.chosen_targets = [p1, p2]
        before_life = p1.life
        before_p2_life = p2.life
        spell.on_resolve(game)

        assert p1.life == before_life  # 0 life gained
        assert p2.life == before_p2_life  # 0 damage dealt


class TestTogetherAsOneSeparateTargets:
    """The draw target (player) and damage target (any target) are independent."""

    def test_opponent_draws_cards_not_caster(self) -> None:
        """Target player for drawing can be the opponent, not the caster."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        _add_library_cards(game, 1, 5)  # add to p2's library

        creature = Creature(name="Bear", owner=p1, controller=p1,
                            base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(creature)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.WHITE, Color.BLUE]  # X=2
        # Target player = p2 (draws), any target = creature on p1's side
        spell.chosen_targets = [p2, creature]

        before_p1_hand = len(game.get_hand(p1).get_all())
        before_p2_hand = len(game.get_hand(p2).get_all())
        spell.on_resolve(game)

        # p2 should draw 2, p1 should not draw
        assert len(game.get_hand(p2).get_all()) == before_p2_hand + 2
        assert len(game.get_hand(p1).get_all()) == before_p1_hand

    def test_caster_gains_life_not_target_player(self) -> None:
        """Life is gained by the casting player (you), not by the target player."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        _add_library_cards(game, 1, 5)  # library for p2 to draw from

        creature = Creature(name="Bear", owner=p1, controller=p1,
                            base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(creature)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.BLACK, Color.RED, Color.GREEN]  # X=3
        # p2 draws, but p1 (caster) gains life
        spell.chosen_targets = [p2, creature]

        before_p1_life = p1.life
        before_p2_life = p2.life
        spell.on_resolve(game)

        assert p1.life == before_p1_life + 3  # caster gains life
        # p2's life should not increase (only p1 gains)
        assert p2.life == before_p2_life

    def test_damage_target_is_creature_not_draw_player(self) -> None:
        """Damage goes to the second chosen target (creature), not the draw player."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        _add_library_cards(game, 0, 5)

        creature = Creature(
            name="Troll",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=8,
        )
        game.get_battlefield(p2).add(creature)

        spell = TogetherAsOne(owner=p1, controller=p1)
        spell.colors_spent = [Color.RED, Color.GREEN]  # X=2
        spell.chosen_targets = [p1, creature]

        before_creature_damage = creature.damage_marked
        before_p1_life = p1.life
        before_p2_life = p2.life
        spell.on_resolve(game)

        assert creature.damage_marked == before_creature_damage + 2
        # p2's life not reduced (creature took damage, not p2 as player)
        assert p2.life == before_p2_life
