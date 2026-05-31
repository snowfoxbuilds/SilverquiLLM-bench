"""Tests for sos_97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Instant, LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class TestRalZarekProperties:
    def test_name(self) -> None:
        assert RalZarekGuestLecturer(owner=None).name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        assert RalZarekGuestLecturer(owner=None).mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_is_planeswalker(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert CardType.PLANESWALKER in card.card_types

    def test_starting_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.starting_loyalty == 3
        assert card.loyalty == 3

    def test_legendary_supertype(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtype_ral(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert "Ral" in card.subtypes

    def test_has_four_loyalty_abilities(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert len(abilities) == 4

    def test_loyalty_costs(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        costs = [a.loyalty_cost for a in card.get_loyalty_abilities()]
        assert +1 in costs
        assert -1 in costs
        assert -2 in costs
        assert -7 in costs


class TestRalZarekSurveil:
    """+1: Surveil 2."""

    def test_surveil_puts_cards_in_graveyard_when_chosen(self) -> None:
        game = create_game(scripts=[[True, True], []])
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        c1 = Instant(name="Card1", owner=p1)
        c2 = Instant(name="Card2", owner=p1)
        p1.zones[Zone.LIBRARY].add(c1)
        p1.zones[Zone.LIBRARY].add(c2)
        abilities = card.get_loyalty_abilities()
        plus1 = next(a for a in abilities if a.loyalty_cost == +1)
        plus1.effect(game)
        # Both cards go to graveyard (True = put in GY).
        gy = game.get_graveyard(p1)
        assert gy.contains(c1) or gy.contains(c2)

    def test_surveil_keeps_card_on_top_when_declined(self) -> None:
        game = create_game(scripts=[[False, False], []])
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        c1 = Instant(name="Card1", owner=p1)
        c2 = Instant(name="Card2", owner=p1)
        p1.zones[Zone.LIBRARY].add(c1)
        p1.zones[Zone.LIBRARY].add(c2)
        abilities = card.get_loyalty_abilities()
        plus1 = next(a for a in abilities if a.loyalty_cost == +1)
        plus1.effect(game)
        lib = p1.zones[Zone.LIBRARY]
        gy = game.get_graveyard(p1)
        assert not gy.contains(c1) and not gy.contains(c2)


class TestRalZarekMinus1:
    """-1: Any number of target players each discard a card."""

    def test_target_player_discards_card(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        hand_card = Instant(name="Bolt", owner=p2, controller=p2)
        set_board_state(game, 1, hand=[hand_card])
        abilities = card.get_loyalty_abilities()
        minus1 = next(a for a in abilities if a.loyalty_cost == -1)
        card.chosen_targets = [p2]
        minus1.effect(game)
        assert game.get_graveyard(p2).contains(hand_card)
        assert not game.get_hand(p2).contains(hand_card)


class TestRalZarekMinus2:
    """-2: Return target creature card with MV ≤ 3 from graveyard to battlefield."""

    def test_returns_small_creature_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        creature = Creature(name="Small Bear", base_power=2, base_toughness=2,
                            owner=p1, controller=p1)
        from engine.types import ManaCost as MC
        creature.mana_cost = MC.parse("{1}{G}")  # MV=2 ≤ 3
        set_board_state(game, 0, graveyard=[creature])
        abilities = card.get_loyalty_abilities()
        minus2 = next(a for a in abilities if a.loyalty_cost == -2)
        card._resolve_target = creature
        minus2.effect(game)
        assert game.get_battlefield(p1).contains(creature)
        assert not game.get_graveyard(p1).contains(creature)

    def test_does_not_return_creature_with_mv_over_3(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        big_creature = Creature(name="Big Bear", base_power=4, base_toughness=4,
                                owner=p1, controller=p1)
        from engine.types import ManaCost as MC
        big_creature.mana_cost = MC.parse("{3}{G}")  # MV=4 > 3
        set_board_state(game, 0, graveyard=[big_creature])
        abilities = card.get_loyalty_abilities()
        minus2 = next(a for a in abilities if a.loyalty_cost == -2)
        card._resolve_target = big_creature
        minus2.effect(game)
        # Should NOT move to battlefield.
        assert game.get_graveyard(p1).contains(big_creature)


class TestRalZarekMinus7:
    """-7: Flip 5 coins, target opponent skips their next X turns."""

    def test_opponent_gets_turns_to_skip(self) -> None:
        """After -7, the opponent has turns_to_skip set (≥ 0)."""
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        abilities = card.get_loyalty_abilities()
        minus7 = next(a for a in abilities if a.loyalty_cost == -7)
        card._resolve_target = p2
        minus7.effect(game)
        # turns_to_skip is set (value is 0–5 depending on coin flips).
        assert hasattr(p2, "turns_to_skip")
        assert 0 <= p2.turns_to_skip <= 5
