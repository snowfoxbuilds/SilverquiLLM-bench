"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

import types

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell as cast_spell_to_stack
from engine.events import AttacksTriggeredEvent
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Step,
    Supertype,
    Zone,
)
from test_utils import create_game, cast_spell, set_board_state


def _make_instant(name: str) -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse("{1}{U}"))


def _make_sorcery(name: str) -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse("{2}{U}"))


def _bind_cast_choices(
    player,
    *,
    should_cast: bool,
    chosen_card=None,
    expected_cards: list | None = None,
) -> None:
    def choose_yes_no(self, prompt: str) -> bool:
        return should_cast

    def choose_card(self, cards, description: str):
        if expected_cards is not None:
            assert set(cards) == set(expected_cards)
        return chosen_card

    def choose_target(self, options, requirement):
        return chosen_card

    player.choose_yes_no = types.MethodType(choose_yes_no, player)
    player.choose_card = types.MethodType(choose_card, player)
    player.choose_target = types.MethodType(choose_target, player)


class TestTheDawningArchaicProperties:
    """Static characteristics from the card spec."""

    def test_is_legendary_creature_avatar(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes

    def test_name_and_mana_cost(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"
        assert card.mana_cost == ManaCost.parse("{10}")

    def test_power_toughness_and_reach(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7
        assert card.base_toughness == 7
        assert Keyword.REACH in card.keywords


class TestTheDawningArchaicCostReduction:
    """The self-cost reduction counts only your instants and sorceries."""

    def test_counts_only_your_instant_and_sorcery_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]

        own_instant = _make_instant("Own Instant")
        own_sorcery = _make_sorcery("Own Sorcery")
        own_creature = Creature(name="Own Bear", base_power=2, base_toughness=2)
        opponent_instant = _make_instant("Opponent Instant")

        set_board_state(
            game,
            0,
            graveyard=[own_instant, own_sorcery, own_creature],
        )
        set_board_state(game, 1, graveyard=[opponent_instant])

        card = TheDawningArchaic(owner=p1, controller=p1)
        assert card.cost_reduction(game) == 2

    def test_ten_or_more_spell_cards_reduce_the_cost_to_zero(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        graveyard_spells = [_make_instant(f"Spell {n}") for n in range(12)]

        set_board_state(game, 0, hand=[archaic], graveyard=graveyard_spells)

        cast_spell(game, 0, "The Dawning Archaic")

        assert game.get_battlefield(p1).contains(archaic)


class TestTheDawningArchaicAttackTrigger:
    """Attack trigger contract for casting a spell from your graveyard."""

    def test_registers_one_attack_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)

        archaic.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(archaic)
        assert len(triggers) == 1
        assert triggers[0].event_type is AttacksTriggeredEvent

    def test_other_creatures_attacking_do_not_trigger_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        other = Creature(name="Other Attacker", owner=p1, controller=p1, base_power=2, base_toughness=2)

        archaic.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=other, attacker=other),
        )

        assert game.stack.is_empty()

    def test_attack_trigger_is_a_noop_when_no_instant_or_sorcery_is_in_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        graveyard_creature = Creature(
            name="Graveyard Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )

        set_board_state(game, 0, battlefield=[archaic], graveyard=[graveyard_creature])
        archaic.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(graveyard_creature)

    def test_you_may_decline_to_cast_the_targeted_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        graveyard_spell = _make_sorcery("Declined Spell")

        set_board_state(game, 0, battlefield=[archaic], graveyard=[graveyard_spell])
        archaic.register_triggers(game)
        _bind_cast_choices(
            p1,
            should_cast=False,
            chosen_card=graveyard_spell,
            expected_cards=[graveyard_spell],
        )

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(graveyard_spell)

    def test_attack_trigger_casts_a_graveyard_sorcery_during_combat_without_paying_mana(self) -> None:
        game = create_game()
        game.phase = Phase.COMBAT
        game.step = Step.DECLARE_ATTACKERS
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        graveyard_sorcery = _make_sorcery("Recovered Sorcery")
        off_type_card = Creature(
            name="Off-Type Card",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            battlefield=[archaic],
            graveyard=[graveyard_sorcery, off_type_card],
            mana={},
        )
        archaic.register_triggers(game)
        _bind_cast_choices(
            p1,
            should_cast=True,
            chosen_card=graveyard_sorcery,
            expected_cards=[graveyard_sorcery],
        )

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert not game.stack.is_empty()
        assert game.stack.peek().source is graveyard_sorcery
        assert not game.get_graveyard(p1).contains(graveyard_sorcery)

    def test_spell_cast_with_the_trigger_is_exiled_instead_of_returning_to_graveyard(self) -> None:
        game = create_game()
        game.phase = Phase.COMBAT
        game.step = Step.DECLARE_ATTACKERS
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        graveyard_sorcery = _make_sorcery("Exile Me Instead")

        set_board_state(game, 0, battlefield=[archaic], graveyard=[graveyard_sorcery])
        archaic.register_triggers(game)
        _bind_cast_choices(
            p1,
            should_cast=True,
            chosen_card=graveyard_sorcery,
            expected_cards=[graveyard_sorcery],
        )

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        trigger = game.stack.pop()
        trigger.on_resolve(game)
        spell_on_stack = game.stack.pop()
        spell_on_stack.on_resolve(game)

        assert game.get_exile(p1).contains(graveyard_sorcery)
        assert not game.get_graveyard(p1).contains(graveyard_sorcery)

    def test_only_the_spell_cast_with_the_trigger_gets_exiled_instead(self) -> None:
        game = create_game()
        game.phase = Phase.COMBAT
        game.step = Step.DECLARE_ATTACKERS
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        graveyard_sorcery = _make_sorcery("Triggered Spell")
        hand_instant = _make_instant("Normal Instant")

        set_board_state(
            game,
            0,
            battlefield=[archaic],
            hand=[hand_instant],
            graveyard=[graveyard_sorcery],
            mana={ManaType.BLUE: 2},
        )
        archaic.register_triggers(game)
        _bind_cast_choices(
            p1,
            should_cast=True,
            chosen_card=graveyard_sorcery,
            expected_cards=[graveyard_sorcery],
        )

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        cast_spell_to_stack(game, p1, hand_instant)
        normal_spell = game.stack.pop()
        normal_spell.on_resolve(game)
        triggered_spell = game.stack.pop()
        triggered_spell.on_resolve(game)

        assert game.get_graveyard(p1).contains(hand_instant)
        assert not game.get_exile(p1).contains(hand_instant)
        assert game.get_exile(p1).contains(graveyard_sorcery)

    def test_attack_trigger_chooses_target_when_put_on_stack_not_on_resolution(self) -> None:
        game = create_game()
        game.phase = Phase.COMBAT
        game.step = Step.DECLARE_ATTACKERS
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        first_spell = _make_sorcery("First Target")
        second_spell = _make_sorcery("Second Target")

        set_board_state(
            game,
            0,
            battlefield=[archaic],
            graveyard=[first_spell, second_spell],
        )
        archaic.register_triggers(game)
        _bind_cast_choices(
            p1,
            should_cast=True,
            chosen_card=first_spell,
            expected_cards=[first_spell, second_spell],
        )

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        trigger = game.stack.pop()
        assert trigger.targets == [first_spell]

        set_board_state(game, 0, battlefield=[archaic], graveyard=[second_spell])
        trigger.on_resolve(game)

        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(second_spell)
        assert not game.get_graveyard(p1).contains(first_spell)
