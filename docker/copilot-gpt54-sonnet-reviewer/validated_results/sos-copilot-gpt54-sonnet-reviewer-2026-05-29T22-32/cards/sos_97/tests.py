"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from types import MethodType

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import LoyaltyAbilityInstance, activate_ability, clear_loyalty_tracking
from engine.card import Creature, Planeswalker, Sorcery
from engine.types import CardType, ManaCost, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state


def _ability_by_cost(card: RalZarekGuestLecturer, loyalty_cost: int):
    for ability in card.get_loyalty_abilities():
        if ability.loyalty_cost == loyalty_cost:
            return ability
    raise AssertionError(f"Missing loyalty ability with cost {loyalty_cost}")


def _bind_choose(player, answers: list[object]) -> None:
    remaining = iter(answers)

    def choose(self, options, description: str):
        return next(remaining)

    player.choose = MethodType(choose, player)


def _bind_choose_yes_no(player, answers: list[bool]) -> None:
    remaining = iter(answers)

    def choose_yes_no(self, prompt: str) -> bool:
        return next(remaining)

    player.choose_yes_no = MethodType(choose_yes_no, player)


def _bind_choose_target(player, chosen_targets: list[object]) -> None:
    remaining = iter(chosen_targets)

    def choose_target(self, options, requirement):
        return next(remaining)

    player.choose_target = MethodType(choose_target, player)


def _bind_choose_card(player, chosen_card, *, expected_options=None) -> None:
    def choose_card(self, cards, description: str):
        if expected_options is not None:
            assert set(cards) == set(expected_options)
        return chosen_card

    player.choose_card = MethodType(choose_card, player)


def _bind_choose_order(player, ordered_cards: list[object], *, expected_cards=None) -> None:
    def choose_order(self, objects, description: str):
        if expected_cards is not None:
            assert list(objects) == list(expected_cards)
        return list(ordered_cards)

    player.choose_order = MethodType(choose_order, player)


def _set_library(player, cards: list[object]) -> None:
    library = player.zones[Zone.LIBRARY]
    for existing in library.get_all():
        library.remove(existing)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


def _make_spell(name: str, mana_cost: str = "{1}") -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse(mana_cost))


def _make_creature(name: str, mana_cost: str) -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse(mana_cost),
        base_power=2,
        base_toughness=2,
    )


def _set_sorcery_speed(game) -> None:
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0


def _runtime_loyalty_ability(card: RalZarekGuestLecturer, loyalty_cost: int) -> LoyaltyAbilityInstance:
    ability = _ability_by_cost(card, loyalty_cost)
    return LoyaltyAbilityInstance(
        source=card,
        controller=card.controller,
        loyalty_cost=ability.loyalty_cost,
        effect=ability.effect,
        description=ability.description,
        target_requirements=ability.target_requirements,
        min_targets=ability.min_targets,
        max_targets=ability.max_targets,
        target_description=ability.target_description,
    )


class TestRalZarekGuestLecturerProperties:
    """Static characteristics from the card spec."""

    def test_is_a_legendary_planeswalker_ral_with_three_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert isinstance(card, Planeswalker)
        assert CardType.PLANESWALKER in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Ral" in card.subtypes
        assert card.starting_loyalty == 3
        assert card.loyalty == 3

    def test_name_and_mana_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")


class TestRalZarekGuestLecturerLoyaltyAbilities:
    """Card-specific loyalty ability contracts."""

    def test_exposes_four_loyalty_abilities_with_the_expected_costs(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()

        assert len(abilities) == 4
        assert [ability.loyalty_cost for ability in abilities] == [1, -1, -2, -7]
        assert "Surveil 2" in abilities[0].description
        assert "discard a card" in abilities[1].description
        assert "mana value 3 or less" in abilities[2].description
        assert "Flip five coins" in abilities[3].description

    def test_plus_one_surveils_two_and_can_put_the_top_card_into_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        bottom = _make_spell("Bottom Card")
        second = _make_spell("Second Card")
        top = _make_spell("Top Card")

        set_board_state(game, 0, battlefield=[ral])
        _set_library(p1, [bottom, second, top])
        _bind_choose_yes_no(p1, [True, False])

        _ability_by_cost(ral, 1).effect(game)

        assert game.get_graveyard(p1).contains(top)
        assert not game.get_graveyard(p1).contains(second)
        assert p1.zones[Zone.LIBRARY].get_all() == [bottom, second]

    def test_plus_one_can_reorder_multiple_kept_cards_on_top_of_your_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        bottom = _make_spell("Bottom Card")
        second = _make_spell("Second Card")
        top = _make_spell("Top Card")

        set_board_state(game, 0, battlefield=[ral])
        _set_library(p1, [bottom, second, top])
        _bind_choose_yes_no(p1, [False, False])
        _bind_choose_order(p1, [second, top], expected_cards=[top, second])

        _ability_by_cost(ral, 1).effect(game)

        assert len(game.get_graveyard(p1).get_all()) == 0
        assert p1.zones[Zone.LIBRARY].get_all() == [bottom, top, second]

    def test_minus_one_discards_one_card_for_each_targeted_player(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        p1_keep = _make_spell("P1 Keep")
        p1_discard = _make_spell("P1 Discard")
        p2_keep = _make_spell("P2 Keep")
        p2_discard = _make_spell("P2 Discard")

        set_board_state(game, 0, battlefield=[ral], hand=[p1_keep, p1_discard])
        set_board_state(game, 1, hand=[p2_keep, p2_discard])
        _bind_choose_card(p1, p1_discard, expected_options=[p1_keep, p1_discard])
        _bind_choose_card(p2, p2_discard, expected_options=[p2_keep, p2_discard])
        ral._resolve_targets = [p1, p2]

        _ability_by_cost(ral, -1).effect(game)

        assert game.get_graveyard(p1).contains(p1_discard)
        assert not game.get_hand(p1).contains(p1_discard)
        assert game.get_graveyard(p2).contains(p2_discard)
        assert not game.get_hand(p2).contains(p2_discard)

    def test_minus_one_exposes_any_number_of_target_players_and_puts_chosen_targets_on_the_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ability = _runtime_loyalty_ability(ral, -1)

        set_board_state(game, 0, battlefield=[ral])
        ral.loyalty = 7
        _set_sorcery_speed(game)
        clear_loyalty_tracking()
        _bind_choose(p1, [2])
        _bind_choose_target(p1, [p1, p2])

        requirements = ability.get_targets(game)
        activate_ability(game, p1, ability)
        stack_object = game.stack.peek()

        assert len(requirements) == 1
        assert requirements[0].description == "target player"
        assert requirements[0].zone is None
        assert ability.min_targets == 0
        assert ability.max_targets is None
        assert stack_object is not None
        assert stack_object.targets == [p1, p2]

    def test_minus_one_with_no_targets_is_a_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        card_in_hand = _make_spell("Still Here")

        set_board_state(game, 0, battlefield=[ral])
        set_board_state(game, 1, hand=[card_in_hand])
        ral._resolve_targets = []

        _ability_by_cost(ral, -1).effect(game)

        assert game.get_hand(p2).contains(card_in_hand)
        assert len(game.get_graveyard(p2).get_all()) == 0

    def test_minus_one_does_not_force_a_discard_from_a_targeted_player_with_no_cards(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[ral])
        set_board_state(game, 1, hand=[])
        ral._resolve_targets = [p2]

        _ability_by_cost(ral, -1).effect(game)

        assert len(game.get_hand(p2).get_all()) == 0
        assert len(game.get_graveyard(p2).get_all()) == 0

    def test_minus_two_returns_a_target_creature_card_with_mana_value_three_or_less_from_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = _make_creature("Returned Bear", "{2}{B}")

        set_board_state(game, 0, battlefield=[ral], graveyard=[target])
        ral._resolve_target = target

        _ability_by_cost(ral, -2).effect(game)

        assert game.get_battlefield(p1).contains(target)
        assert not game.get_graveyard(p1).contains(target)

    def test_minus_two_target_requirement_only_allows_your_own_creature_card_with_mana_value_three_or_less(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        your_legal_target = _make_creature("Your Legal Target", "{2}{B}")
        your_illegal_target = _make_creature("Your Illegal Target", "{3}{B}")
        opponent_target = _make_creature("Opponent Target", "{2}{B}")

        set_board_state(game, 0, battlefield=[ral], graveyard=[your_legal_target, your_illegal_target])
        set_board_state(game, 1, graveyard=[opponent_target])

        requirement = _ability_by_cost(ral, -2).get_targets(game)[0]

        assert requirement.zone == Zone.GRAVEYARD
        assert requirement.description == "target creature card with mana value 3 or less from your graveyard"
        assert requirement.filter_fn(your_legal_target) is True
        assert requirement.filter_fn(your_illegal_target) is False
        assert requirement.filter_fn(opponent_target) is False

    def test_minus_two_does_not_return_a_creature_card_with_mana_value_four_or_greater(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = _make_creature("Too Expensive", "{3}{B}")

        set_board_state(game, 0, battlefield=[ral], graveyard=[target])
        ral._resolve_target = target

        _ability_by_cost(ral, -2).effect(game)

        assert game.get_graveyard(p1).contains(target)
        assert not game.get_battlefield(p1).contains(target)

    def test_minus_seven_uses_scripted_coin_flips_to_set_target_opponents_skipped_turns(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ability = _runtime_loyalty_ability(ral, -7)

        set_board_state(game, 0, battlefield=[ral])
        ral.loyalty = 7
        _set_sorcery_speed(game)
        clear_loyalty_tracking()
        _bind_choose_target(p1, [p2])
        game.scripted_coin_flips = [True, False, True, False, True]

        activate_ability(game, p1, ability)
        stack_object = game.stack.peek()
        assert stack_object is not None
        assert stack_object.targets == [p2]

        stack_object.on_resolve(game)

        assert game.coin_flip_history[-5:] == [True, False, True, False, True]
        assert game.skipped_turns[1] == 3
        assert p2.turns_to_skip == 3

    def test_minus_seven_skip_turns_are_consumed_by_turn_rotation(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ability = _runtime_loyalty_ability(ral, -7)

        set_board_state(game, 0, battlefield=[ral])
        ral.loyalty = 7
        _set_sorcery_speed(game)
        clear_loyalty_tracking()
        _bind_choose_target(p1, [p2])
        game.scripted_coin_flips = [True, True, False, False, False]

        activate_ability(game, p1, ability)
        stack_object = game.stack.peek()
        assert stack_object is not None
        stack_object.on_resolve(game)

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()
        assert game.active_player is p1
        assert p2.turns_to_skip == 1

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()
        assert game.active_player is p1
        assert p2.turns_to_skip == 0

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()
        assert game.active_player is p2

    def test_has_a_minus_seven_ultimate_loyalty_ability(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        ability = _ability_by_cost(card, -7)

        assert ability.loyalty_cost == -7
        assert "skips their next X turns" in ability.description
