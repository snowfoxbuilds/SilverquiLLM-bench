"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Planeswalker, Sorcery
from engine.types import CardType, Color, ManaCost, Phase, Step, Supertype, Zone
from test_utils import create_game


class TrainingCreature(Creature):
    """Simple creature used for reanimation and library setup."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Training Creature")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)


class LargeTrainingCreature(Creature):
    """Creature whose mana value is too large for the -2 ability."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Large Training Creature")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)


class HandFodder(Sorcery):
    """Simple card used to populate hands and libraries."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Hand Fodder")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)


def _set_effect_targets(card, *targets) -> None:
    """Seed the existing target backdoors used by current planeswalker cards."""

    card.chosen_targets = list(targets)
    card._resolve_targets = list(targets)
    card._resolve_target = targets[0] if targets else None


class TestRalZarekGuestLecturerProperties:
    """Static card data should match the SOS 97 spec."""

    def test_is_planeswalker(self) -> None:
        assert isinstance(RalZarekGuestLecturer(owner=None), Planeswalker)

    def test_name(self) -> None:
        assert RalZarekGuestLecturer(owner=None).name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        assert RalZarekGuestLecturer(owner=None).mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_is_legendary_ral(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Ral" in card.subtypes

    def test_starts_on_three_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.starting_loyalty == 3
        assert card.loyalty == 3

    def test_is_black(self) -> None:
        assert RalZarekGuestLecturer(owner=None).colors == {Color.BLACK}

    def test_declares_four_loyalty_abilities_in_oracle_order(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()

        assert [ability.loyalty_cost for ability in abilities] == [1, -1, -2, -7]
        assert "Surveil 2" in abilities[0].description
        assert "target players each discard a card" in abilities[1].description
        assert "mana value 3 or less" in abilities[2].description
        assert "skips their next X turns" in abilities[3].description


class TestRalZarekGuestLecturerSurveil:
    """The +1 ability should surveil 2."""

    def test_plus_one_can_put_both_looked_at_cards_into_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        bottom = HandFodder(name="Bottom Card", owner=p1, controller=p1)
        looked_one = HandFodder(name="Looked One", owner=p1, controller=p1)
        looked_two = HandFodder(name="Looked Two", owner=p1, controller=p1)

        p1.zones[Zone.LIBRARY].add(bottom)
        p1.zones[Zone.LIBRARY].add(looked_one)
        p1.zones[Zone.LIBRARY].add(looked_two)
        p1.choose_yes_no = lambda prompt: True

        walker.get_loyalty_abilities()[0].effect(game)

        assert p1.zones[Zone.GRAVEYARD].contains(looked_one)
        assert p1.zones[Zone.GRAVEYARD].contains(looked_two)
        assert p1.zones[Zone.LIBRARY].contains(bottom)
        assert len(p1.zones[Zone.LIBRARY]) == 1

    def test_plus_one_is_a_noop_with_empty_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)

        walker.get_loyalty_abilities()[0].effect(game)

        assert len(p1.zones[Zone.LIBRARY]) == 0
        assert len(p1.zones[Zone.GRAVEYARD]) == 0


class TestRalZarekGuestLecturerDiscard:
    """The -1 ability should make each targeted player discard a card."""

    def test_minus_one_with_no_targets_is_a_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        p1_card = HandFodder(name="P1 Card", owner=p1, controller=p1)
        p2_card = HandFodder(name="P2 Card", owner=p2, controller=p2)

        p1.zones[Zone.HAND].add(p1_card)
        p2.zones[Zone.HAND].add(p2_card)
        _set_effect_targets(walker)

        walker.get_loyalty_abilities()[1].effect(game)

        assert p1.zones[Zone.HAND].contains(p1_card)
        assert p2.zones[Zone.HAND].contains(p2_card)
        assert len(p1.zones[Zone.GRAVEYARD]) == 0
        assert len(p2.zones[Zone.GRAVEYARD]) == 0

    def test_minus_one_makes_each_targeted_player_discard_a_card(self) -> None:
        game = create_game()
        p1, p2 = game.players
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        p1_keep = HandFodder(name="P1 Keep", owner=p1, controller=p1)
        p1_discard = HandFodder(name="P1 Discard", owner=p1, controller=p1)
        p2_keep = HandFodder(name="P2 Keep", owner=p2, controller=p2)
        p2_discard = HandFodder(name="P2 Discard", owner=p2, controller=p2)

        p1.zones[Zone.HAND].add(p1_keep)
        p1.zones[Zone.HAND].add(p1_discard)
        p2.zones[Zone.HAND].add(p2_keep)
        p2.zones[Zone.HAND].add(p2_discard)
        p1.choose_card = lambda cards, description: p1_discard
        p2.choose_card = lambda cards, description: p2_discard
        _set_effect_targets(walker, p1, p2)

        walker.get_loyalty_abilities()[1].effect(game)

        assert p1.zones[Zone.GRAVEYARD].contains(p1_discard)
        assert p2.zones[Zone.GRAVEYARD].contains(p2_discard)
        assert p1.zones[Zone.HAND].contains(p1_keep)
        assert p2.zones[Zone.HAND].contains(p2_keep)

    def test_minus_one_ignores_targeted_players_with_empty_hands(self) -> None:
        game = create_game()
        p1, p2 = game.players
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        p2_card = HandFodder(name="P2 Card", owner=p2, controller=p2)

        p2.zones[Zone.HAND].add(p2_card)
        p2.choose_card = lambda cards, description: p2_card
        _set_effect_targets(walker, p1, p2)

        walker.get_loyalty_abilities()[1].effect(game)

        assert len(p1.zones[Zone.GRAVEYARD]) == 0
        assert p2.zones[Zone.GRAVEYARD].contains(p2_card)
        assert len(p2.zones[Zone.HAND]) == 0


class TestRalZarekGuestLecturerReanimation:
    """The -2 ability should reanimate a small creature from your graveyard."""

    def test_minus_two_returns_a_mana_value_three_creature_from_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = TrainingCreature(owner=p1, controller=p1)

        p1.zones[Zone.GRAVEYARD].add(target)
        _set_effect_targets(walker, target)

        walker.get_loyalty_abilities()[2].effect(game)

        assert p1.zones[Zone.BATTLEFIELD].contains(target)
        assert not p1.zones[Zone.GRAVEYARD].contains(target)

    def test_minus_two_does_not_return_a_creature_with_mana_value_four(self) -> None:
        game = create_game()
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = LargeTrainingCreature(owner=p1, controller=p1)

        p1.zones[Zone.GRAVEYARD].add(target)
        _set_effect_targets(walker, target)

        walker.get_loyalty_abilities()[2].effect(game)

        assert p1.zones[Zone.GRAVEYARD].contains(target)
        assert not p1.zones[Zone.BATTLEFIELD].contains(target)

    def test_minus_two_cannot_reanimate_from_an_opponents_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)
        target = TrainingCreature(owner=p2, controller=p2)

        p2.zones[Zone.GRAVEYARD].add(target)
        _set_effect_targets(walker, target)

        walker.get_loyalty_abilities()[2].effect(game)

        assert p2.zones[Zone.GRAVEYARD].contains(target)
        assert not p1.zones[Zone.BATTLEFIELD].contains(target)
        assert not p2.zones[Zone.BATTLEFIELD].contains(target)


class TestRalZarekGuestLecturerUltimate:
    """The -7 ability should deterministically queue and consume skipped turns."""

    def test_minus_seven_queues_target_opponents_skipped_turns_equal_to_heads(self) -> None:
        game = create_game()
        p1, p2 = game.players
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)

        game.coin_flip_results = [True, False, True, True, False]
        _set_effect_targets(walker, p2)

        walker.get_loyalty_abilities()[3].effect(game)

        assert game.skipped_turns == [1, 1, 1]
        assert game.queued_skipped_turns_for(p2) == 3
        assert game.queued_skipped_turns_for(p1) == 0

    def test_minus_seven_with_all_tails_queues_no_skipped_turns(self) -> None:
        game = create_game()
        p1, p2 = game.players
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)

        game.coin_flip_results = [False, False, False, False, False]
        _set_effect_targets(walker, p2)

        walker.get_loyalty_abilities()[3].effect(game)

        assert game.skipped_turns == []
        assert game.queued_skipped_turns_for(p2) == 0

    def test_minus_seven_skipped_turns_are_consumed_by_future_turn_changes(self) -> None:
        game = create_game()
        p1, p2 = game.players
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)

        game.coin_flip_results = [True, True, False, False, True]
        _set_effect_targets(walker, p2)

        walker.get_loyalty_abilities()[3].effect(game)

        seen_active_players = []
        for _ in range(4):
            game.phase = Phase.ENDING
            game.step = Step.CLEANUP
            game.priority_player_index = game.active_player_index
            game.advance_phase()
            seen_active_players.append(game.active_player)

        assert seen_active_players == [p1, p1, p1, p2]
        assert game.queued_skipped_turns_for(p2) == 0

    def test_minus_seven_does_nothing_if_target_is_not_an_opponent(self) -> None:
        game = create_game()
        p1 = game.players[0]
        walker = RalZarekGuestLecturer(owner=p1, controller=p1)

        game.coin_flip_results = [True, True, True, True, True]
        _set_effect_targets(walker, p1)

        walker.get_loyalty_abilities()[3].effect(game)

        assert game.skipped_turns == []
        assert game.coin_flip_results == [True, True, True, True, True]
