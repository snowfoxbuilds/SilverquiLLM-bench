"""Tests for SOS 238 — Teacher's Pest.

{B}{G} Creature — Skeleton Pest, 1/1
Menace
Whenever this creature attacks, you gain 1 life.
{B}{G}: Return this card from your graveyard to the battlefield tapped.
"""

from __future__ import annotations

from cards.sos.sos_238.card_impl import TeachersPest
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game


class TestTeachersPestProperties:
    """Static card data should match the SOS 238 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(TeachersPest(owner=None), Creature)

    def test_name(self) -> None:
        assert TeachersPest(owner=None).name == "Teacher's Pest"

    def test_mana_cost(self) -> None:
        assert TeachersPest(owner=None).mana_cost == ManaCost.parse("{B}{G}")

    def test_power_toughness(self) -> None:
        card = TeachersPest(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 1

    def test_has_menace(self) -> None:
        card = TeachersPest(owner=None)
        assert Keyword.MENACE in card.keywords

    def test_subtypes(self) -> None:
        card = TeachersPest(owner=None)
        assert "Skeleton" in card.subtypes
        assert "Pest" in card.subtypes


class TestTeachersPestAttackTrigger:
    """Whenever this creature attacks, you gain 1 life."""

    def test_attack_trigger_gains_one_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TeachersPest(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        life_before = p1.life
        card.on_attack(game)
        assert p1.life == life_before + 1

    def test_multiple_attacks_gain_multiple_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TeachersPest(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        life_before = p1.life
        card.on_attack(game)
        card.on_attack(game)
        assert p1.life == life_before + 2


class TestTeachersPestGraveyardAbility:
    """{B}{G}: Return this card from your graveyard to the battlefield tapped."""

    def test_can_activate_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TeachersPest(owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(card)

        # Should be activatable from graveyard
        assert card.can_activate_graveyard_ability(game) is True

    def test_cannot_activate_from_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TeachersPest(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        assert card.can_activate_graveyard_ability(game) is False

    def test_returns_to_battlefield_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TeachersPest(owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(card)

        card.activate_graveyard_ability(game)

        # Card should be on battlefield
        bf_cards = game.get_battlefield(p1).get_all()
        assert card in bf_cards
        # Card should be tapped
        assert card.tapped is True

    def test_removed_from_graveyard_after_activation(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TeachersPest(owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(card)

        card.activate_graveyard_ability(game)

        gy_cards = p1.zones[Zone.GRAVEYARD].get_all()
        assert card not in gy_cards
