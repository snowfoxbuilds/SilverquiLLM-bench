"""Tests for SOS 134 — Thunderdrum Soloist.

A 1/3 Dwarf Bard for {1}{R} with Reach.
Opus — Whenever you cast an instant or sorcery spell, this creature deals
1 damage to each opponent. If five or more mana was spent to cast that spell,
this creature deals 3 damage to each opponent instead.
"""

from __future__ import annotations

from cards.sos.sos_134.card_impl import ThunderdrumSoloist
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestThunderdrumSoloistProperties:
    """Static card data should match the SOS 134 spec."""

    def test_is_creature(self) -> None:
        card = ThunderdrumSoloist(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = ThunderdrumSoloist(owner=None)
        assert card.name == "Thunderdrum Soloist"

    def test_mana_cost(self) -> None:
        card = ThunderdrumSoloist(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{R}")

    def test_power_toughness(self) -> None:
        card = ThunderdrumSoloist(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 3

    def test_has_reach(self) -> None:
        card = ThunderdrumSoloist(owner=None)
        assert Keyword.REACH in card.keywords


class TestThunderdrumSoloistOpus:
    """Opus trigger: damage to each opponent on instant/sorcery cast."""

    def test_deals_1_damage_on_cheap_spell(self) -> None:
        """Casting a spell with <5 mana deals 1 damage to each opponent."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = ThunderdrumSoloist(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        life_before = p2.life
        card.on_spell_cast(game, mana_spent=3)
        assert p2.life == life_before - 1

    def test_deals_3_damage_on_expensive_spell(self) -> None:
        """Casting a spell with 5+ mana deals 3 damage to each opponent."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = ThunderdrumSoloist(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        life_before = p2.life
        card.on_spell_cast(game, mana_spent=5)
        assert p2.life == life_before - 3

    def test_deals_3_damage_on_seven_mana_spell(self) -> None:
        """Verify 'five or more' — 7 mana should deal 3 damage."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = ThunderdrumSoloist(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        life_before = p2.life
        card.on_spell_cast(game, mana_spent=7)
        assert p2.life == life_before - 3

    def test_exactly_four_mana_deals_1_damage(self) -> None:
        """Boundary: 4 mana is less than 5, so only 1 damage."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = ThunderdrumSoloist(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        life_before = p2.life
        card.on_spell_cast(game, mana_spent=4)
        assert p2.life == life_before - 1

    def test_does_not_damage_controller(self) -> None:
        """Opus damages opponents only, not the controller."""
        game = create_game()
        p1 = game.players[0]
        card = ThunderdrumSoloist(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        life_before = p1.life
        card.on_spell_cast(game, mana_spent=5)
        assert p1.life == life_before
