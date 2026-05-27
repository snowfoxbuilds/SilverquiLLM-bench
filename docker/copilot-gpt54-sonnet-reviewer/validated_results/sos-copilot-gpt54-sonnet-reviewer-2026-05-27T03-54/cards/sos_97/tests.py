"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import LoyaltyAbilityInstance, activate_ability, clear_loyalty_tracking
from engine.card import Creature, Instant, Planeswalker
from engine.types import CardType, Color, ManaCost, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state


def _make_sorcery_speed_game(*, scripts=None):
    clear_loyalty_tracking()
    game = create_game(scripts=scripts)
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0
    return game


def _set_targets(source, *targets) -> None:
    source.chosen_targets = list(targets)
    source._resolve_targets = list(targets)
    source._resolve_target = targets[0] if targets else None


def _activate_and_resolve_loyalty_ability(game, source, ability_index: int) -> None:
    loyalty_ability = source.get_loyalty_abilities()[ability_index]
    activate_ability(
        game,
        source.controller,
        LoyaltyAbilityInstance(
            source=source,
            controller=source.controller,
            loyalty_cost=loyalty_ability.loyalty_cost,
            effect=loyalty_ability.effect,
            description=loyalty_ability.description,
        ),
    )
    stack_obj = game.stack.pop()
    stack_obj.on_resolve(game)


class TestRalZarekGuestLecturerProperties:
    """Static card data should match the SOS 97 spec."""

    def test_is_legendary_black_planeswalker_with_expected_cost_and_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert isinstance(card, Planeswalker)
        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert CardType.PLANESWALKER in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Ral"} <= card.subtypes
        assert card.starting_loyalty == 3
        assert card.loyalty == 3
        assert card.colors == {Color.BLACK}
        assert card.color_identity == {Color.BLACK}

    def test_rules_text_and_loyalty_abilities_match_the_spec(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()

        assert card.rules_text == (
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads."
        )
        assert [ability.loyalty_cost for ability in abilities] == [1, -1, -2, -7]
        assert [ability.description for ability in abilities] == [
            "+1: Surveil 2.",
            "−1: Any number of target players each discard a card.",
            "−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.",
            "−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
        ]


class TestRalZarekGuestLecturerLoyaltyAbilities:
    """Each loyalty ability should produce the observable result from the card spec."""

    def test_plus_one_surveils_two_cards(self) -> None:
        game = _make_sorcery_speed_game(scripts=([True, True], []))
        player = game.players[0]
        card = RalZarekGuestLecturer(owner=player, controller=player)
        bottom = Instant(name="Bottom Card", mana_cost=ManaCost.parse("{B}"))
        middle = Instant(name="Middle Card", mana_cost=ManaCost.parse("{B}"))
        top = Instant(name="Top Card", mana_cost=ManaCost.parse("{B}"))

        set_board_state(game, 0, battlefield=[card])
        library = game.get_library(player)
        library.add(bottom)
        library.add(middle)
        library.add(top)

        _activate_and_resolve_loyalty_ability(game, card, 0)

        assert card.loyalty == 4
        assert game.get_graveyard(player).contains(top)
        assert game.get_graveyard(player).contains(middle)
        assert library.get_all() == [bottom]

    def test_minus_one_can_target_zero_players_and_discards_nothing(self) -> None:
        game = _make_sorcery_speed_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        p1_card = Instant(name="P1 Card", mana_cost=ManaCost.parse("{B}"))
        p2_card = Instant(name="P2 Card", mana_cost=ManaCost.parse("{B}"))

        set_board_state(game, 0, battlefield=[card], hand=[p1_card])
        set_board_state(game, 1, hand=[p2_card])
        _set_targets(card)

        _activate_and_resolve_loyalty_ability(game, card, 1)

        assert card.loyalty == 2
        assert game.get_hand(p1).contains(p1_card)
        assert game.get_hand(p2).contains(p2_card)
        assert not game.get_graveyard(p1).contains(p1_card)
        assert not game.get_graveyard(p2).contains(p2_card)

    def test_minus_one_makes_each_targeted_player_discard_a_card(self) -> None:
        game = _make_sorcery_speed_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        p1_card = Instant(name="P1 Card", mana_cost=ManaCost.parse("{B}"))
        p2_card = Instant(name="P2 Card", mana_cost=ManaCost.parse("{B}"))

        set_board_state(game, 0, battlefield=[card], hand=[p1_card])
        set_board_state(game, 1, hand=[p2_card])
        _set_targets(card, p1, p2)

        _activate_and_resolve_loyalty_ability(game, card, 1)

        assert card.loyalty == 2
        assert not game.get_hand(p1).contains(p1_card)
        assert not game.get_hand(p2).contains(p2_card)
        assert game.get_graveyard(p1).contains(p1_card)
        assert game.get_graveyard(p2).contains(p2_card)

    def test_minus_two_returns_a_small_creature_from_your_graveyard_to_the_battlefield(self) -> None:
        game = _make_sorcery_speed_game()
        player = game.players[0]
        card = RalZarekGuestLecturer(owner=player, controller=player)
        target = Creature(
            name="Returned Adept",
            owner=player,
            controller=player,
            mana_cost=ManaCost.parse("{2}{B}"),
            base_power=3,
            base_toughness=2,
        )

        set_board_state(game, 0, battlefield=[card], graveyard=[target])
        _set_targets(card, target)

        _activate_and_resolve_loyalty_ability(game, card, 2)

        assert card.loyalty == 1
        assert game.get_battlefield(player).contains(target)
        assert not game.get_graveyard(player).contains(target)

    def test_minus_two_does_not_return_a_creature_with_mana_value_four_or_more(self) -> None:
        game = _make_sorcery_speed_game()
        player = game.players[0]
        card = RalZarekGuestLecturer(owner=player, controller=player)
        target = Creature(
            name="Too Expensive",
            owner=player,
            controller=player,
            mana_cost=ManaCost.parse("{3}{B}"),
            base_power=4,
            base_toughness=4,
        )

        set_board_state(game, 0, battlefield=[card], graveyard=[target])
        _set_targets(card, target)

        _activate_and_resolve_loyalty_ability(game, card, 2)

        assert card.loyalty == 1
        assert game.get_graveyard(player).contains(target)
        assert not game.get_battlefield(player).contains(target)

    def test_minus_two_does_not_return_a_creature_from_an_opponents_graveyard(self) -> None:
        game = _make_sorcery_speed_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = Creature(
            name="Enemy Adept",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}{B}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, graveyard=[target])
        _set_targets(card, target)

        _activate_and_resolve_loyalty_ability(game, card, 2)

        assert card.loyalty == 1
        assert game.get_graveyard(p2).contains(target)
        assert not game.get_battlefield(p1).contains(target)
        assert not game.get_battlefield(p2).contains(target)

    def test_minus_seven_records_five_coin_flips_and_sets_skips_to_heads_count(self) -> None:
        game = _make_sorcery_speed_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        results = [True, False, True, True, False]

        card.loyalty = 7
        set_board_state(game, 0, battlefield=[card])
        game.set_coin_flip_results(results)
        _set_targets(card, p2)

        _activate_and_resolve_loyalty_ability(game, card, 3)

        assert card.loyalty == 0
        assert card.last_coin_flip_results == results
        assert game.coin_flip_history[-5:] == results
        assert game.get_next_turns_to_skip(p2) == 3
        assert game.get_next_turns_to_skip(p1) == 0

    def test_minus_seven_skips_the_target_opponents_next_x_turns(self) -> None:
        game = _make_sorcery_speed_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)

        card.loyalty = 7
        set_board_state(game, 0, battlefield=[card])
        game.set_coin_flip_results([True, False, True, False, False])
        _set_targets(card, p2)

        _activate_and_resolve_loyalty_ability(game, card, 3)

        assert game.get_next_turns_to_skip(p2) == 2

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()
        assert game.active_player is p1
        assert game.get_next_turns_to_skip(p2) == 1

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()
        assert game.active_player is p1
        assert game.get_next_turns_to_skip(p2) == 0

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()
        assert game.active_player is p2

    def test_minus_seven_with_zero_heads_does_not_add_any_skipped_turns(self) -> None:
        game = _make_sorcery_speed_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = RalZarekGuestLecturer(owner=p1, controller=p1)
        results = [False, False, False, False, False]

        card.loyalty = 7
        set_board_state(game, 0, battlefield=[card])
        game.set_coin_flip_results(results)
        _set_targets(card, p2)

        _activate_and_resolve_loyalty_ability(game, card, 3)

        assert card.loyalty == 0
        assert card.last_coin_flip_results == results
        assert game.coin_flip_history[-5:] == results
        assert game.get_next_turns_to_skip(p2) == 0
