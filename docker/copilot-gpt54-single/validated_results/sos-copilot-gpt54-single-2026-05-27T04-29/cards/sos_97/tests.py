"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import LoyaltyAbilityInstance, activate_ability, clear_loyalty_tracking
from engine.card import Creature, Instant, Planeswalker, Sorcery
from engine.types import CardType, Color, ManaCost, Phase, Step, Supertype, Zone
from test_utils import create_game, set_board_state


class TestRalZarekGuestLecturerProperties:
    """Static characteristics and loyalty-ability surface from the spec."""

    def test_is_a_legendary_black_planeswalker_named_ral_zarek_guest_lecturer(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert isinstance(card, Planeswalker)
        assert CardType.PLANESWALKER in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Ral"} <= card.subtypes
        assert card.colors == {Color.BLACK}
        assert card.name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost_and_starting_loyalty_match_the_spec(self) -> None:
        card = RalZarekGuestLecturer(owner=None)

        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert card.starting_loyalty == 3
        assert card.loyalty == 3

    def test_has_four_loyalty_abilities_with_the_printed_costs(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()

        assert len(abilities) == 4
        assert [ability.loyalty_cost for ability in abilities] == [1, -1, -2, -7]
        assert "Surveil 2" in abilities[0].description
        assert "discard a card" in abilities[1].description
        assert "mana value 3 or less" in abilities[2].description
        assert "skips their next X turns" in abilities[3].description


class TestRalZarekGuestLecturerLoyaltyAbilities:
    """Resolution contracts for the printed loyalty abilities."""

    @staticmethod
    def _setup_game():
        clear_loyalty_tracking()
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ral])
        return game, p1, p2, ral

    @staticmethod
    def _resolve_loyalty_ability(game, player, source, ability_index: int) -> None:
        printed = source.get_loyalty_abilities()[ability_index]
        activate_ability(
            game,
            player,
            LoyaltyAbilityInstance(
                source=source,
                controller=player,
                loyalty_cost=printed.loyalty_cost,
                effect=printed.effect,
                description=printed.description,
            ),
        )
        game.stack.pop().on_resolve(game)

    def test_plus_one_surveils_two_cards_into_your_graveyard_when_you_choose_both(self) -> None:
        game, p1, _p2, ral = self._setup_game()
        bottom = Instant(name="Bottom Lesson", owner=p1, controller=p1)
        middle = Sorcery(name="Middle Lesson", owner=p1, controller=p1)
        top = Creature(
            name="Top Lesson",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )

        p1.zones[Zone.LIBRARY].add(bottom)
        p1.zones[Zone.LIBRARY].add(middle)
        p1.zones[Zone.LIBRARY].add(top)
        p1.choose_yes_no = lambda _prompt: True

        self._resolve_loyalty_ability(game, p1, ral, 0)

        assert game.get_graveyard(p1).contains(top)
        assert game.get_graveyard(p1).contains(middle)
        assert not game.get_graveyard(p1).contains(bottom)
        assert list(p1.zones[Zone.LIBRARY].get_all()) == [bottom]

    def test_plus_one_can_leave_both_surveilled_cards_on_top_of_the_library(self) -> None:
        game, p1, _p2, ral = self._setup_game()
        bottom = Instant(name="Bottom Lesson", owner=p1, controller=p1)
        middle = Sorcery(name="Middle Lesson", owner=p1, controller=p1)
        top = Creature(
            name="Top Lesson",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )

        p1.zones[Zone.LIBRARY].add(bottom)
        p1.zones[Zone.LIBRARY].add(middle)
        p1.zones[Zone.LIBRARY].add(top)
        p1.choose_yes_no = lambda _prompt: False

        self._resolve_loyalty_ability(game, p1, ral, 0)

        assert game.get_graveyard(p1).get_all() == []
        assert list(p1.zones[Zone.LIBRARY].get_all())[-2:] == [middle, top]

    def test_minus_one_makes_each_targeted_player_discard_one_card(self) -> None:
        game, p1, p2, ral = self._setup_game()
        p1_discard = Instant(name="Self Discard", owner=p1, controller=p1)
        p1_keep = Instant(name="Self Keep", owner=p1, controller=p1)
        p2_discard = Instant(name="Opp Discard", owner=p2, controller=p2)
        p2_keep = Instant(name="Opp Keep", owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[ral], hand=[p1_discard, p1_keep])
        set_board_state(game, 1, hand=[p2_discard, p2_keep])
        p1.choose_card = lambda _cards, _description: p1_discard
        p2.choose_card = lambda _cards, _description: p2_discard
        ral.chosen_targets = [p1, p2]
        ral._resolve_targets = [p1, p2]

        self._resolve_loyalty_ability(game, p1, ral, 1)

        assert game.get_graveyard(p1).contains(p1_discard)
        assert game.get_graveyard(p2).contains(p2_discard)
        assert game.get_hand(p1).contains(p1_keep)
        assert game.get_hand(p2).contains(p2_keep)
        assert not game.get_hand(p1).contains(p1_discard)
        assert not game.get_hand(p2).contains(p2_discard)

    def test_minus_one_with_no_target_players_is_a_noop(self) -> None:
        game, p1, p2, ral = self._setup_game()
        p1_card = Instant(name="Self Card", owner=p1, controller=p1)
        p2_card = Instant(name="Opp Card", owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[ral], hand=[p1_card])
        set_board_state(game, 1, hand=[p2_card])
        ral.chosen_targets = []
        ral._resolve_targets = []

        self._resolve_loyalty_ability(game, p1, ral, 1)

        assert game.get_hand(p1).contains(p1_card)
        assert game.get_hand(p2).contains(p2_card)
        assert game.get_graveyard(p1).get_all() == []
        assert game.get_graveyard(p2).get_all() == []

    def test_minus_two_returns_target_creature_card_with_mana_value_three_or_less(self) -> None:
        game, p1, _p2, ral = self._setup_game()
        target = Creature(
            name="Recovered Assistant",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{2}{B}"),
            base_power=2,
            base_toughness=2,
        )
        other = Creature(
            name="Stay Buried",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{3}{B}"),
            base_power=3,
            base_toughness=3,
        )

        set_board_state(game, 0, battlefield=[ral], graveyard=[target, other])
        ral.chosen_targets = [target]
        ral._resolve_target = target

        self._resolve_loyalty_ability(game, p1, ral, 2)

        assert game.get_battlefield(p1).contains(target)
        assert not game.get_graveyard(p1).contains(target)
        assert game.get_graveyard(p1).contains(other)

    def test_minus_two_does_not_return_a_creature_card_with_mana_value_four_or_more(self) -> None:
        game, p1, _p2, ral = self._setup_game()
        oversized = Creature(
            name="Too Expensive",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{3}{B}"),
            base_power=4,
            base_toughness=4,
        )

        set_board_state(game, 0, battlefield=[ral], graveyard=[oversized])
        ral.chosen_targets = [oversized]
        ral._resolve_target = oversized

        self._resolve_loyalty_ability(game, p1, ral, 2)

        assert game.get_graveyard(p1).contains(oversized)
        assert not game.get_battlefield(p1).contains(oversized)

    def test_minus_two_does_not_return_a_card_that_left_your_graveyard_before_resolution(self) -> None:
        game, p1, _p2, ral = self._setup_game()
        target = Creature(
            name="Missing Assistant",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{2}{B}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(game, 0, battlefield=[ral], hand=[target], graveyard=[])
        ral.chosen_targets = [target]
        ral._resolve_target = target

        self._resolve_loyalty_ability(game, p1, ral, 2)

        assert game.get_hand(p1).contains(target)
        assert not game.get_battlefield(p1).contains(target)
        assert game.get_graveyard(p1).get_all() == []

    def test_minus_seven_targets_only_an_opponent(self) -> None:
        game, p1, p2, ral = self._setup_game()

        requirements = ral.get_loyalty_target_requirements(game, 3)

        assert len(requirements) == 1
        assert requirements[0].zone == Zone.BATTLEFIELD
        assert requirements[0].description == "target opponent"
        assert requirements[0].filter_fn(p2) is True
        assert requirements[0].filter_fn(p1) is False

    def test_minus_seven_flips_five_scripted_coins_and_queues_that_many_skipped_turns(self) -> None:
        game, p1, p2, ral = self._setup_game()
        ral.loyalty = 7
        ral.chosen_targets = [p2]
        ral._resolve_target = p2
        game.set_scripted_coin_flips([True, False, True, False, True])

        self._resolve_loyalty_ability(game, p1, ral, 3)

        assert game.last_coin_flips == [True, False, True, False, True]
        assert game.coin_flip_history[-5:] == [True, False, True, False, True]
        assert game.coin_flip_results == []
        assert game.get_pending_skipped_turns(p2) == 3
        assert p2.skip_next_turns == 3

    def test_minus_seven_with_zero_heads_does_not_queue_any_skipped_turns(self) -> None:
        game, p1, p2, ral = self._setup_game()
        ral.loyalty = 7
        ral.chosen_targets = [p2]
        ral._resolve_target = p2
        game.set_scripted_coin_flips([False, False, False, False, False])

        self._resolve_loyalty_ability(game, p1, ral, 3)

        assert game.last_coin_flips == [False, False, False, False, False]
        assert game.coin_flip_history[-5:] == [False, False, False, False, False]
        assert game.get_pending_skipped_turns(p2) == 0
        assert getattr(p2, "skip_next_turns", 0) == 0

    def test_minus_seven_skip_turns_are_consumed_by_turn_progression(self) -> None:
        game, p1, p2, ral = self._setup_game()
        ral.loyalty = 7
        ral.chosen_targets = [p2]
        ral._resolve_target = p2
        game.set_scripted_coin_flips([True, True, False, False, False])

        self._resolve_loyalty_ability(game, p1, ral, 3)

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()

        assert game.turn_number == 2
        assert game.active_player is p1
        assert game.priority_player is p1
        assert game.get_pending_skipped_turns(p2) == 1

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()

        assert game.turn_number == 3
        assert game.active_player is p1
        assert game.priority_player is p1
        assert game.get_pending_skipped_turns(p2) == 0
        assert p2.skip_next_turns == 0

        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()

        assert game.turn_number == 4
        assert game.active_player is p2
        assert game.priority_player is p2
