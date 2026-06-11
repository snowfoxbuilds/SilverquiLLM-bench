"""Tests for SOS 194 — Hardened Academic."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_194.card_impl import HardenedAcademic
from benchmarks.sos.workspace.engine.card import ActivatedAbility, CardImpl, Creature
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.events import GraveyardLeavesTriggeredEvent
from benchmarks.sos.workspace.engine.game import deal_damage
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestHardenedAcademicProperties:
    """Static card data should match the SOS 194 spec."""

    def test_is_bird_cleric_with_flying_and_haste(self) -> None:
        card = HardenedAcademic(owner=None)

        assert isinstance(card, Creature)
        assert "Bird" in card.subtypes
        assert "Cleric" in card.subtypes
        assert Keyword.FLYING in card.keywords
        assert Keyword.HASTE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = HardenedAcademic(owner=None)

        assert card.name == "Hardened Academic"
        assert card.mana_cost == ManaCost.parse("{R}{W}")
        assert card.base_power == 2
        assert card.base_toughness == 1


class TestHardenedAcademicActivatedAbility:
    """Hardened Academic should discard for temporary lifelink."""

    def test_has_a_single_activated_ability(self) -> None:
        abilities = HardenedAcademic(owner=None).get_activated_abilities()

        assert len(abilities) == 1
        assert isinstance(abilities[0], ActivatedAbility)

    def test_activation_cost_discards_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = HardenedAcademic(owner=p1, controller=p1)
        discard_card = CardImpl(name="Spent Thesis", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], hand=[discard_card])
        p1._script.append(discard_card)
        ability = card.get_activated_abilities()[0]

        assert ability.cost(game, card) is True
        assert not game.get_hand(p1).contains(discard_card)
        assert game.get_graveyard(p1).contains(discard_card)

    def test_activation_cost_fails_without_a_card_to_discard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = HardenedAcademic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_activated_abilities()[0]

        assert ability.cost(game, card) is False

    def test_effect_grants_lifelink_until_end_of_turn(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = HardenedAcademic(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        ability = card.get_activated_abilities()[0]

        ability.effect(game)

        assert Keyword.LIFELINK in card.keywords
        deal_damage(game, card, p2, card.power)
        assert p1.life == 22
        assert p2.life == 18

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert Keyword.LIFELINK not in card.keywords


class TestHardenedAcademicGraveyardLeaves:
    """Hardened Academic should put counters on your creatures when your graveyard empties."""

    def test_registers_a_graveyard_leaves_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = HardenedAcademic(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is GraveyardLeavesTriggeredEvent

    def test_card_leaving_your_graveyard_locks_a_target_creature_you_control_and_puts_a_counter_on_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        academic = HardenedAcademic(owner=p1, controller=p1)
        target = Creature(
            name="Diligent Assistant",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        departed = CardImpl(name="Recovered Notes", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[academic, target], graveyard=[departed])
        academic.register_triggers(game)
        p1._script.append(target)

        move_to_zone(game, departed, Zone.GRAVEYARD, Zone.HAND)

        assert len(game.stack) == 1
        assert game.stack.peek().source is academic
        assert game.stack.peek().targets == [target]

        resolve_top(game)

        assert target.plus_one_counters == 1
        assert academic.plus_one_counters == 0

    def test_single_graveyard_leave_event_with_multiple_cards_puts_only_one_counter_on_the_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        academic = HardenedAcademic(owner=p1, controller=p1)
        target = Creature(
            name="Study Group Leader",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[academic, target])
        academic.register_triggers(game)
        p1._script.append(target)

        game.trigger_manager.fire_event(
            game,
            GraveyardLeavesTriggeredEvent(
                player=p1,
                cards=[CardImpl(name="First"), CardImpl(name="Second")],
                destination=Zone.EXILE,
            ),
        )

        assert len(game.stack) == 1

        resolve_top(game)

        assert target.plus_one_counters == 1

    def test_cards_leaving_an_opponents_graveyard_do_not_trigger_it(self) -> None:
        game = create_game()
        p1, p2 = game.players
        academic = HardenedAcademic(owner=p1, controller=p1)
        opponent_card = CardImpl(name="Opponent Notes", owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[academic])
        set_board_state(game, 1, graveyard=[opponent_card])
        academic.register_triggers(game)

        move_to_zone(game, opponent_card, Zone.GRAVEYARD, Zone.HAND)

        assert game.stack.is_empty()
