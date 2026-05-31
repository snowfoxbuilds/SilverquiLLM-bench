"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


def _creature_card(name: str, mana_cost: str = "{1}{B}") -> Creature:
    card = Creature(
        name=name,
        mana_cost=ManaCost.parse(mana_cost),
        base_power=2,
        base_toughness=2,
    )
    card.card_types = {CardType.CREATURE}
    return card


def _loyalty_ability(card: RalZarekGuestLecturer, index: int) -> LoyaltyAbility:
    return card.get_loyalty_abilities()[index]


def _set_library(player, cards: list[Creature]) -> None:
    library = player.zones[Zone.LIBRARY]
    for existing in library.get_all():
        library.remove(existing)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


class TestRalZarekGuestLecturerProperties:
    """Static card data and loyalty ability declarations should match the spec."""

    def test_is_legendary_planeswalker_named_and_costed(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert isinstance(card, Planeswalker)
        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_has_ral_subtype_and_starts_on_three_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert CardType.PLANESWALKER in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Ral"} <= card.subtypes
        assert card.starting_loyalty == 3
        assert card.loyalty == 3

    def test_declares_four_loyalty_abilities_in_printed_order(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()

        assert len(abilities) == 4
        assert all(isinstance(ability, LoyaltyAbility) for ability in abilities)
        assert [ability.loyalty_cost for ability in abilities] == [1, -1, -2, -7]
        assert "Surveil 2" in abilities[0].description
        assert "discard" in abilities[1].description
        assert "mana value 3 or less" in abilities[2].description
        assert "skip" in abilities[3].description


class TestRalZarekGuestLecturerSurveilAbility:
    """The +1 ability should surveil two cards from its controller's library."""

    def test_plus_one_can_put_the_top_card_into_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        bottom = _creature_card("Bottom")
        second = _creature_card("Second")
        top = _creature_card("Top")
        _set_library(p1, [bottom, second, top])
        p1._script.append(True)
        p1._script.append(False)

        _loyalty_ability(card, 0).effect(game)

        assert p1.zones[Zone.GRAVEYARD].contains(top)
        assert not p1.zones[Zone.GRAVEYARD].contains(second)
        assert p1.zones[Zone.LIBRARY].get_all() == [bottom, second]

    def test_plus_one_handles_a_library_with_only_one_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        lone = _creature_card("Lone Card")
        _set_library(p1, [lone])
        p1._script.append(True)

        _loyalty_ability(card, 0).effect(game)

        assert p1.zones[Zone.GRAVEYARD].contains(lone)
        assert len(p1.zones[Zone.LIBRARY].get_all()) == 0


class TestRalZarekGuestLecturerDiscardAbility:
    """The −1 ability should make each targeted player discard one card."""

    def test_minus_one_can_target_zero_players_and_do_nothing(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        hand_a = _creature_card("Hand A")
        hand_b = _creature_card("Hand B")
        set_board_state(game, 0, hand=[hand_a])
        set_board_state(game, 1, hand=[hand_b])
        card.chosen_targets = []
        card._resolve_targets = []

        _loyalty_ability(card, 1).effect(game)

        assert game.get_hand(p1).contains(hand_a)
        assert game.get_hand(p2).contains(hand_b)
        assert len(game.get_graveyard(p1).get_all()) == 0
        assert len(game.get_graveyard(p2).get_all()) == 0

    def test_minus_one_can_target_yourself_without_affecting_untargeted_players(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        keep = _creature_card("Keep")
        discard_me = _creature_card("Discard Me")
        opponent_card = _creature_card("Opponent Card")
        set_board_state(game, 0, hand=[keep, discard_me])
        set_board_state(game, 1, hand=[opponent_card])
        p1._script.append(discard_me)
        card.chosen_targets = [p1]
        card._resolve_targets = [p1]

        _loyalty_ability(card, 1).effect(game)

        assert game.get_graveyard(p1).contains(discard_me)
        assert game.get_hand(p1).contains(keep)
        assert not game.get_hand(p1).contains(discard_me)
        assert game.get_hand(p2).contains(opponent_card)

    def test_minus_one_makes_each_targeted_player_discard_a_card_of_their_choice(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        p1_keep = _creature_card("P1 Keep")
        p1_discard = _creature_card("P1 Discard")
        p2_keep = _creature_card("P2 Keep")
        p2_discard = _creature_card("P2 Discard")
        set_board_state(game, 0, hand=[p1_keep, p1_discard])
        set_board_state(game, 1, hand=[p2_keep, p2_discard])
        p1._script.append(p1_discard)
        p2._script.append(p2_discard)
        card.chosen_targets = [p1, p2]
        card._resolve_targets = [p1, p2]

        _loyalty_ability(card, 1).effect(game)

        assert game.get_graveyard(p1).contains(p1_discard)
        assert game.get_graveyard(p2).contains(p2_discard)
        assert game.get_hand(p1).contains(p1_keep)
        assert game.get_hand(p2).contains(p2_keep)

    def test_minus_one_skips_targeted_players_with_empty_hands(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        only_card = _creature_card("Only Card")
        set_board_state(game, 0, hand=[])
        set_board_state(game, 1, hand=[only_card])
        p2._script.append(only_card)
        card.chosen_targets = [p1, p2]
        card._resolve_targets = [p1, p2]

        _loyalty_ability(card, 1).effect(game)

        assert len(game.get_graveyard(p1).get_all()) == 0
        assert game.get_graveyard(p2).contains(only_card)


class TestRalZarekGuestLecturerReanimationAbility:
    """The −2 ability should return a small creature card from your graveyard."""

    def test_minus_two_returns_target_creature_card_with_mana_value_three_or_less(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = _creature_card("Returned Scholar", "{2}{B}")
        set_board_state(game, 0, graveyard=[target])
        card.chosen_targets = [target]
        card._resolve_target = target

        _loyalty_ability(card, 2).effect(game)

        assert game.get_battlefield(p1).contains(target)
        assert not game.get_graveyard(p1).contains(target)
        assert target.controller is p1

    def test_minus_two_does_not_return_a_creature_with_mana_value_four(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = _creature_card("Too Expensive", "{2}{B}{B}")
        set_board_state(game, 0, graveyard=[target])
        card.chosen_targets = [target]
        card._resolve_target = target

        _loyalty_ability(card, 2).effect(game)

        assert game.get_graveyard(p1).contains(target)
        assert not game.get_battlefield(p1).contains(target)

    def test_minus_two_does_not_return_a_creature_from_an_opponents_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = _creature_card("Opponent Creature", "{1}{B}")
        set_board_state(game, 1, graveyard=[target])
        card.chosen_targets = [target]
        card._resolve_target = target

        _loyalty_ability(card, 2).effect(game)

        assert game.get_graveyard(p2).contains(target)
        assert not game.get_battlefield(p1).contains(target)
