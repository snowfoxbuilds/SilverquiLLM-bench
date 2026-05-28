"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction, resolve_top
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import (
    TestSetupError as SetupError,
    cast_spell,
    create_game,
    declare_attackers,
    set_board_state,
)


class GraveyardSpark(Instant):
    """Simple instant used to exercise graveyard-cast behavior."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Graveyard Spark")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        super().__init__(**kwargs)
        self.times_resolved = 0

    def on_resolve(self, game) -> None:
        self.times_resolved += 1


class GraveyardRitual(Sorcery):
    """Simple sorcery used to exercise graveyard-count behavior."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Graveyard Ritual")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        super().__init__(**kwargs)


class GraveyardBear(Creature):
    """Non-instant/sorcery card used to validate filtering."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Graveyard Bear")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)


class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(TheDawningArchaic(owner=None), Creature)

    def test_name(self) -> None:
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self) -> None:
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_is_legendary_avatar(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes

    def test_power_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.base_power == 7
        assert card.base_toughness == 7

    def test_has_reach(self) -> None:
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords


class TestTheDawningArchaicCostReduction:
    """The spell should cost less for each instant/sorcery in your graveyard."""

    def test_cost_reduction_counts_only_instants_and_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        instant_card = GraveyardSpark(owner=p1, controller=p1)
        sorcery_card = GraveyardRitual(owner=p1, controller=p1)
        creature_card = GraveyardBear(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            graveyard=[instant_card, sorcery_card, creature_card],
        )

        assert get_cost_reduction(game, card, p1) == 2

    def test_cost_reduction_is_clamped_to_printed_generic_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        graveyard = [GraveyardSpark(owner=p1, controller=p1) for _ in range(12)]
        set_board_state(game, 0, graveyard=graveyard)

        assert get_cost_reduction(game, card, p1) == 10

    def test_can_be_cast_with_reduced_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[card],
            graveyard=[
                GraveyardSpark(owner=p1, controller=p1),
                GraveyardRitual(owner=p1, controller=p1),
            ],
            mana={ManaType.COLORLESS: 8},
        )

        cast_spell(game, 0, "The Dawning Archaic")

        assert game.get_battlefield(p1).contains(card)

    def test_insufficient_mana_after_reduction_still_cannot_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[card],
            graveyard=[
                GraveyardSpark(owner=p1, controller=p1),
                GraveyardRitual(owner=p1, controller=p1),
            ],
            mana={ManaType.COLORLESS: 7},
        )

        with pytest.raises(SetupError):
            cast_spell(game, 0, "The Dawning Archaic")


class TestTheDawningArchaicAttackTrigger:
    """Attack trigger should free-cast a graveyard instant/sorcery."""

    def test_registers_attack_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TheDawningArchaic(owner=p1, controller=p1)

        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())

        assert after - before == 1
        trigger = game.trigger_manager.get_triggers_for_source(card)[0]
        assert trigger.event_type is AttacksTriggeredEvent
        assert trigger.controller is p1

    def test_attack_trigger_can_cast_target_spell_for_free_and_exiles_it_after_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        spell = GraveyardSpark(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])
        archaic.register_triggers(game)

        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: spell
        p1.choose_target = lambda options, requirement: spell
        p1.choose = (
            lambda options, description: spell
            if isinstance(options, list) and spell in options
            else None
        )

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        assert len(game.stack) == 1
        resolve_top(game)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
        assert not game.get_graveyard(p1).contains(spell)

        resolve_top(game)

        assert spell.times_resolved == 1
        assert game.get_exile(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)

    def test_attack_trigger_fires_from_normal_combat_declare_attackers_flow(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.summoning_sick = False
        spell = GraveyardSpark(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])
        archaic.register_triggers(game)

        p1.choose_target = lambda options, requirement: spell
        p1.choose_yes_no = lambda prompt: True

        declare_attackers(game, ["The Dawning Archaic"])

        assert archaic.is_attacking is True
        assert len(game.stack) == 1
        assert game.stack.peek().source is archaic
        assert game.stack.peek().targets == [spell]

        resolve_top(game)

        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
        assert not game.get_graveyard(p1).contains(spell)

        resolve_top(game)

        assert spell.times_resolved == 1
        assert game.get_exile(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)

    def test_attack_trigger_targets_only_legal_graveyard_instants_and_sorceries_when_stacked(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.summoning_sick = False
        spell = GraveyardSpark(owner=p1, controller=p1)
        creature_card = GraveyardBear(owner=p1, controller=p1)
        seen: dict[str, object] = {}

        set_board_state(
            game,
            0,
            battlefield=[archaic],
            graveyard=[spell, creature_card],
        )
        archaic.register_triggers(game)

        def choose_target(options, requirement):
            seen["options"] = list(options)
            seen["description"] = requirement.description
            seen["zone"] = requirement.zone
            return spell

        p1.choose_target = choose_target

        declare_attackers(game, ["The Dawning Archaic"])

        assert seen["options"] == [spell]
        assert seen["zone"] == Zone.GRAVEYARD
        assert "instant or sorcery" in seen["description"]
        assert game.stack.peek().targets == [spell]

    def test_attack_trigger_retains_target_chosen_when_trigger_is_put_on_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        archaic.summoning_sick = False
        first_spell = GraveyardSpark(owner=p1, controller=p1)
        second_spell = GraveyardRitual(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[archaic],
            graveyard=[first_spell, second_spell],
        )
        archaic.register_triggers(game)

        p1.choose_target = lambda options, requirement: first_spell
        declare_attackers(game, ["The Dawning Archaic"])

        assert game.stack.peek().targets == [first_spell]

        p1.choose_target = lambda options, requirement: second_spell
        p1.choose_yes_no = lambda prompt: True

        resolve_top(game)

        assert len(game.stack) == 1
        assert game.stack.peek().source is first_spell
        assert game.get_graveyard(p1).contains(second_spell)

    def test_attack_trigger_is_optional(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        spell = GraveyardSpark(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell])
        archaic.register_triggers(game)

        p1.choose_yes_no = lambda prompt: False
        p1.choose_card = lambda cards, description: spell
        p1.choose_target = lambda options, requirement: spell
        p1.choose = (
            lambda options, description: spell
            if isinstance(options, list) and spell in options
            else None
        )

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )
        resolve_top(game)

        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(spell)
        assert not game.get_exile(p1).contains(spell)

    def test_attack_trigger_does_not_cast_noninstant_or_nonsorcery_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        creature_card = GraveyardBear(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[archaic], graveyard=[creature_card])
        archaic.register_triggers(game)

        p1.choose_yes_no = lambda prompt: True
        p1.choose_card = lambda cards, description: creature_card
        p1.choose_target = lambda options, requirement: creature_card
        p1.choose = (
            lambda options, description: creature_card
            if isinstance(options, list) and creature_card in options
            else None
        )

        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        if not game.stack.is_empty():
            resolve_top(game)

        assert game.stack.is_empty()
        assert game.get_graveyard(p1).contains(creature_card)
        assert not game.get_exile(p1).contains(creature_card)
        assert not p1.zones[Zone.STACK].contains(creature_card)
        assert not game.get_battlefield(p1).contains(creature_card)
