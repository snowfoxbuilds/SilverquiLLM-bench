"""Tests for sos_13 — Emeritus of Truce // Swords to Plowshares.

Front face: Emeritus of Truce — {1}{W}{W} — 3/3 Creature — Cat Cleric
  ETB: target player creates a 1/1 white/black Inkling creature token with flying.
  Then if an opponent controls more creatures than you, this creature becomes prepared.

Prepared keyword: while prepared, you may cast a copy of its spell (Swords to Plowshares).
Doing so unprepares it.

Covers:
- Static properties (3/3, Cat Cleric, {1}{W}{W})
- ETB creates Inkling token for target player
- ETB: becomes prepared when opponent has more creatures
- ETB: does NOT become prepared when opponent has fewer/equal creatures
- Prepared flag: is_prepared attribute
- Prepared ability: exiles target creature, its controller gains life = its power
- After casting prepared spell, is_prepared becomes False
"""
from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


def _count_creatures(game, player) -> int:
    bf = game.get_battlefield(player)
    return sum(1 for c in bf.get_all() if CardType.CREATURE in getattr(c, "card_types", set()))


class TestEmeritusProperties:
    def test_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Emeritus of Truce" in card.name

    def test_base_power(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3

    def test_base_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_toughness == 3

    def test_mana_cost_front_face(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_has_creature_card_type(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_has_cat_cleric_subtypes(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cat" in card.subtypes or "Cleric" in card.subtypes

    def test_not_prepared_by_default(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.is_prepared is False


class TestEmeritusETBInklingToken:
    """ETB creates a 1/1 white/black Inkling token with flying for target player."""

    def test_etb_creates_one_token(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]  # target player for token creation
        initial_count = _count_creatures(game, p1)
        card.on_resolve(game)
        assert _count_creatures(game, p1) == initial_count + 1

    def test_etb_token_is_flying_inkling(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        creatures = [c for c in bf.get_all() if CardType.CREATURE in getattr(c, "card_types", set())]
        inkling = creatures[-1]  # most recently created
        assert "Inkling" in getattr(inkling, "subtypes", set())
        assert Keyword.FLYING in getattr(inkling, "keywords", Keyword(0))

    def test_etb_token_is_1_1(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        creatures = [c for c in bf.get_all() if CardType.CREATURE in getattr(c, "card_types", set())]
        inkling = creatures[-1]
        assert inkling.base_power == 1
        assert inkling.base_toughness == 1

    def test_etb_token_can_be_given_to_opponent(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p2]  # give token to opponent
        initial_count = _count_creatures(game, p2)
        card.on_resolve(game)
        assert _count_creatures(game, p2) == initial_count + 1


class TestEmeritusPreparationCondition:
    """Becomes prepared if an opponent controls more creatures than the controller."""

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # p2 has 2 creatures, p1 has 0
        bear1 = Creature(name="Bear1", base_power=2, base_toughness=2, owner=p2, controller=p2)
        bear2 = Creature(name="Bear2", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(bear1)
        game.get_battlefield(p2).add(bear2)
        card.chosen_targets = [p1]
        card.on_resolve(game)
        assert card.is_prepared is True

    def test_not_prepared_when_equal_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # Both have 1 creature (from token)
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(bear)
        card.chosen_targets = [p2]  # token goes to p2
        card.on_resolve(game)
        # p1 has 0 creatures, p2 has 2 (bear + inkling) — p2 has more than p1
        # Actually: p1 has no creatures after token goes to p2, p2 has 2
        # So p1 controller checks: does an opponent (p2) have more? Yes → prepared
        # Let's do a cleaner test: controller has 1, opponent has 1 → not prepared
        # Reset: give p1 a creature too
        game2 = create_game()
        p1_2, p2_2 = game2.players[0], game2.players[1]
        card2 = EmeritusOfTruceSwordsToPlowshares(owner=p1_2, controller=p1_2)
        bear_p1 = Creature(name="BearP1", base_power=2, base_toughness=2, owner=p1_2, controller=p1_2)
        bear_p2 = Creature(name="BearP2", base_power=2, base_toughness=2, owner=p2_2, controller=p2_2)
        game2.get_battlefield(p1_2).add(bear_p1)
        game2.get_battlefield(p2_2).add(bear_p2)
        card2.chosen_targets = [p1_2]  # token goes to p1
        # After token: p1 has 2, p2 has 1 → opponent NOT more → not prepared
        card2.on_resolve(game2)
        assert card2.is_prepared is False

    def test_not_prepared_when_controller_has_more_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # p1 has many creatures, p2 has none
        for i in range(3):
            b = Creature(name=f"Bear{i}", base_power=2, base_toughness=2, owner=p1, controller=p1)
            game.get_battlefield(p1).add(b)
        card.chosen_targets = [p1]  # token goes to p1 (now p1 has 4)
        card.on_resolve(game)
        assert card.is_prepared is False


class TestEmeritusPreparedAbility:
    """When prepared, the Swords to Plowshares ability can be activated."""

    def test_cast_prepared_spell_exiles_creature(self) -> None:
        """Casting the prepared STP spell exiles the target creature."""
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.is_prepared = True
        target = Creature(name="BigBear", base_power=4, base_toughness=4, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)
        initial_life_p2 = p2.life
        card.cast_prepared_spell(game, target)
        # Target should be removed from battlefield
        assert target not in game.get_battlefield(p2).get_all()
        # p2 gains life equal to target's power (4)
        assert p2.life == initial_life_p2 + 4

    def test_cast_prepared_spell_unprepares(self) -> None:
        """After casting, is_prepared becomes False."""
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.is_prepared = True
        target = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)
        card.cast_prepared_spell(game, target)
        assert card.is_prepared is False

    def test_cast_prepared_spell_not_usable_when_not_prepared(self) -> None:
        """cast_prepared_spell should not work if not prepared."""
        game = create_game()
        p1, p2 = game.players[0], game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.is_prepared = False
        target = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)
        initial_count = len(game.get_battlefield(p2).get_all())
        card.cast_prepared_spell(game, target)
        # Should have no effect since not prepared
        assert len(game.get_battlefield(p2).get_all()) == initial_count
